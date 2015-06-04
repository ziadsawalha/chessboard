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

"""Classes and utilities for modeling and handling application topology."""

from chessboard import classes
from chessboard import schema


class TopologyError(Exception):

    """Basic exception type for errors related to :class:`Topology`."""


class Topology(classes.ExtensibleDict):

    """Construct and validate the relations between application services.

    The main thing this class does right now is read parsed and validated
    Checkmatefile contents (see :meth:`from_deployment`), analyze the
    relations defined for each service, create a simple mapping for those
    relations, and check that the relations are valid.
    """

    __schema__ = schema.BLUEPRINT_SCHEMA

    @property
    def services(self):
        """Return the `services` item as an attribute."""
        return self.get('services')

    def get_relations(self):
        """Return map of all relations in all services.

        This also performs some semantic validation checks on the application
        topology; specifically, we check to make sure relations refer to valid
        services. If a service is connected to another service which doesn't
        exist, an error should be raised.

        :returns: dict of service names with relations as `(target, interface)`
        :raises:
            :exception:`TopologyError` on invalid relations.
        """
        relations = {}
        services = self.services
        if not services:
            return relations
        for service_name, service in services.items():
            svc_relations = service.get('relations')
            if svc_relations:
                maps = []
                for relation in svc_relations:
                    remote_service = relation['service']
                    remote_interface = relation['interface']
                    if remote_service not in self.services:
                        # The remote service we want to connect to doesn't
                        # exist.
                        raise TopologyError(
                            "Service '%(sn)s' defines a relation to an unknown"
                            " remote service '%(rs)s'."
                            % dict(sn=service_name, rs=remote_service)
                        )
                    else:
                        # The remote service exists.
                        maps.append((remote_service, remote_interface))
                relations[service_name] = maps
        return relations

    @staticmethod
    def from_deployment(deployment):
        """Generate a `Topology` object from a deployment or Checkmatefile.

        :param deployment:
            deployment object of Checkmatefile contents, parsed and validated
            using, for example, :func:`chessboard.parser.load`.

        :returns:
            A :class:`Topology` instance.
        """
        return Topology(deployment['blueprint'])
