# Copyright 2015 Rackspace US, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Classes and utilities for modeling and handling deployment targets."""

import logging

import eventlet

from chessboard import classes
from chessboard import schema
from chessboard import utils

API_POOL = eventlet.GreenPool()
LOG = logging.getLogger(__name__)


class SimpleSelector(object):

    """Simple component selector.

    This class exists to allow for future introduction of more advanced
    component selection algorithsm (ex. best match, lowest cost, etc...).

    Selects first component.
    """

    @staticmethod
    def select(selector, components):
        """Select first component."""
        for component in components:
            return component


class Environment(classes.ExtensibleDict):

    """Construct a target where deployments can be launched."""

    __schema__ = schema.ENVIRONMENT_SCHEMA

    def __init__(self, *args, **kwargs):
        """Create a new Environment."""
        super(Environment, self).__init__(*args, **kwargs)
        self.selector = SimpleSelector()

    @property
    def providers(self):
        """Return providers iterable."""
        return self.setdefault('providers', {})

    def get_provider(self, key):
        """Instantiate and return provider from environment definition."""
        provider = self.providers[key]
        class_name = (provider.get('class_name') or
                      'chessboard.providers.%s.Provider' % key)
        provider_class = utils.import_class(class_name)
        instance = provider_class(key=key, **provider)
        return instance

    def find_components(self, selector, context):
        """Resolve blueprint component into actual provider components.

        Examples of blueprint_entries:
        - type: application
          name: wordpress
          role: master
        - type: load-balancer
          interface: http
        - id: component_id
        """
        params = {}
        params.update(selector)
        # normalize 'type' to 'resource_type'
        resource_type = params.pop('type', params.get('resource_type'))
        params['resource_type'] = resource_type
        providers = {key: self.get_provider(key) for key in self.providers}

        # Prime providers by asynchronously initializing their catalogs
        if API_POOL.free() < 10:
            LOG.warning("Threadpool for calling provider APIs is running low: "
                        "%s free of %s", API_POOL.free(), API_POOL.running())
        pile = eventlet.GreenPile(API_POOL)
        for provider in providers.values():
            pile.spawn(provider.catalog, context)

        for provider in providers.values():
            for component in provider.find_components(**params):
                yield component

    def find_component(self, selector, context):
        """Resolve blueprint component into actual provider component."""
        matches = list(self.find_components(selector, context))
        if not matches:
            LOG.info("Did not find component match for: %s", selector)
            return None

        if len(matches) > 1:
            LOG.warning("Ambiguous component '%s' matches: %s",
                        selector, matches)
            LOG.warning("Will use '%s.%s' as a default if no match is found",
                        matches[0].provider.key, matches[0]['id'])
        return matches[0]

    @staticmethod
    def from_deployment(deployment):
        """Generate an `Environment` object from a deployment or Checkmatefile.

        :param deployment:
            deployment object of Checkmatefile contents, parsed and validated
            using, for example, :func:`chessboard.parser.load`.

        :returns:
            An :class:`Environment` instance.
        """
        return Environment(deployment['environment'])
