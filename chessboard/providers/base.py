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

"""Base Providers Class."""

from abc import ABCMeta
import logging

from mongoquery import Query
import six

from chessboard.component import Component

LOG = logging.getLogger(__name__)


@six.add_metaclass(ABCMeta)
class Provider(object):

    """Provider base class and interface definition."""

    def __init__(self, key=None, catalog=None, constraints=None):
        """Initialize instance of Provider with supplied environment values."""
        super(Provider, self).__init__()
        self._catalog = catalog
        self._constraints = constraints
        self.key = key or self.full_name

    @property
    def class_name(self):
        """Return provider importable name (class and modules)."""
        return 'chessboard.providers.%s.Provider' % (self.full_name)

    @property
    def full_name(self):
        """Return unique provider name."""
        return '%s.%s' % (self.vendor, self.name)

    @property
    def vendor(self):
        """Return vendor name (defaults to module name)."""
        return str(self.__class__.__module__)

    @property
    def name(self):
        """The provider's short name  which defaults to the class name."""
        return self.__class__.__name__

    def get_component(self, component_id):
        """Return component by id."""
        return self.catalog()[component_id]

    def find_components(self, **conditions):
        """Iterate over components that match supplied conditions."""
        if conditions:
            qry = Query(conditions)
            return six.moves.filter(qry.match, self.iter_components())
        else:
            return self.iter_components()

    def iter_components(self):
        """Iterable list of component."""
        for cid, component in self._catalog.items():
            if 'id' not in component:
                yield Component(list(component.items()) + [('id', cid)],
                                provider=self)
            else:
                yield Component(component.copy(), provider=self)

    def catalog(self, where=None):
        """Return components formatted for API output."""
        if where is None:
            where = {}
        return {c['id']: c for c in self.find_components(**where)}

    def get_resource_name(self, deployment, domain, index, service,
                          resource_type):
        """Calculate a unique name for a resource."""
        if service:
            if deployment._constrained_to_one(service):
                name = "%s.%s" % (service, domain)
            elif isinstance(index, int) or (
                    isinstance(index, six.string_types) and index.isdigit()):
                name = "%s%02d.%s" % (service, int(index), domain)
            else:
                name = "%s%s.%s" % (service, index, domain)
        else:
            name = "shared%s.%s" % (resource_type, domain)
        return name

    def generate_template(self, deployment, resource_type, service, context,
                          index, provider_key, definition, resolver):
        """Create a resource dict for the requested resource.

        This only creates a list of resource dicts to add to the deployment for
        planning purposes. Nothing is created at this stage.

        :param resource_type: string - must be on of schema.RESOURCE_TYPES
        :param service: the name of the service this resource will be added to.
        :param context: the current call context (dict with call information)
        :param index: the numeric index of the resource indicating which
            resource this is if count is >1 in a service.
        :param provider_key: the key of this provider in the environment.
        :param definition: the component definition for this resource.
        :param resolver: the instance of the resolver calling this method. This
            can be used to inspect the planning process or interact with the
            resolver to perform operations like requsting additional resources
            based on most recent deployment/planning state.

        :returns: list of resources that should be added to the deployment.
        """
        LOG.debug("Getting %s template for service %s", resource_type, service)
        # default_domain = os.environ.get('DEFAULT_DOMAIN', 'checkmate.local')
        default_domain = 'checkmate.local'
        domain = deployment.get_setting('domain',
                                        provider_key=provider_key,
                                        resource_type=resource_type,
                                        service_name=service,
                                        default=default_domain)
        result = {
            'type': resource_type,
            'provider': provider_key,
            'instance': {},
            'desired-state': {},
        }
        if service:
            result['service'] = service

        name = self.get_resource_name(deployment, domain, index, service,
                                      resource_type)
        result['dns-name'] = name
        return [result]
