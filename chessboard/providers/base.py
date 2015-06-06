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
import itertools
import logging

from mongoquery import Query
import six

from chessboard.component import Component

LOG = logging.getLogger(__name__)


@six.add_metaclass(ABCMeta)
class Provider(object):

    """Provider base class and interface definition."""

    def __init__(self, key=None, catalog=None, constraints=None):
        super(Provider, self).__init__()
        self._catalog = catalog
        self._constraints = constraints
        self.key = key or self.full_name

    @property
    def class_name(self):
        return 'chessboard.providers.%s.Provider' % (self.full_name)

    @property
    def full_name(self):
        return '%s.%s' % (self.vendor, self.name)

    @property
    def vendor(self):
        return str(self.__class__.__module__)

    @property
    def name(self):
        return self.__class__.__name__

    def get_component(self, component_id):
        """Return component by id."""
        return self.catalog()[component_id]

    def find_components(self, **conditions):
        """Iterate over components that match supplied conditions."""
        if conditions:
            qry = Query(conditions)
            return itertools.ifilter(qry.match, self.iter_components())
        else:
            return self.iter_components()

    def iter_components(self):
        """Iterable list of component."""
        for cid, component in self._catalog.iteritems():
            if 'id' not in component:
                yield Component(component.items() + [('id', cid)],
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
        if service:
            if deployment._constrained_to_one(service):
                name = "%s.%s" % (service, domain)
            elif isinstance(index, int) or (isinstance(index, basestring) and
                                            index.isdigit()):
                name = "%s%02d.%s" % (service, int(index), domain)
            else:
                name = "%s%s.%s" % (service, index, domain)
        else:
            name = "shared%s.%s" % (resource_type, domain)
        return name

    def generate_template(self, deployment, resource_type, service, context,
                          index, provider_key, definition, resolver):
        LOG.debug("Getting %s template for service %s", resource_type, service)
        # default_domain = os.environ.get('CHECKMATE_DOMAIN', 'checkmate.local')
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
