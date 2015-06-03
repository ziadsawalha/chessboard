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

    X__schema__ = schema.BLUEPRINT_SCHEMA

    def __init__(self, *args, **kwargs):
        """Create a new Topology."""
        super(Topology, self).__init__(*args, **kwargs)
        self.relations = {}
        self._relate_services()

    @property
    def services(self):
        """Return dict of services."""
        return self.setdefault('services', {})

    def _relate_services(self):
        """Wire up services, per the defined relations.

        This performs some semantic validation checks on the application
        topology; specifically, we check to make sure relations refer to valid
        services. If a service is connected to another service which doesn't
        exist, an error should be raised. Likewise, if a remote service exists
        but does not expose an interface matching the interface of the
        relation, an error should be raised.

        :raises:
            :exception:`TopologyError` on invalid relations.
        """
        for service_name, service in self.services.items():
            relations = service.get('relations')
            if relations:
                maps = []
                for relation in relations:
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
                        # This is all we check for now; later in the pipeline,
                        # we will need to check that the interfaces match, as
                        # well as define in more detail the nature of the
                        # relations between actual instances of resources in
                        # a given deployment.
                        maps.append((remote_service, remote_interface))
                self.relations[service_name] = maps

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
