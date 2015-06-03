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

"""Tests for :mod:`chessboard.topology`."""

import unittest

import six

from chessboard import parser
from chessboard import topology


class TestTopology(unittest.TestCase):

    """Tests for :class:`chessboard.topology.Topology`."""

    def test_blank(self):
        """Assert that blank Topology instances can be created.

        Because voluptuous executes `type(data)()`, we need to make sure that
        works.
        """
        self.assertEqual(topology.Topology(), {})

    def test_valid(self):
        """Test Topology generation for a valid case."""
        checkmatefile = six.StringIO("""
            blueprint:
              id: def456
              name: sample app
              version: 0.0.1
              services:
                LoadBalancer:
                  component:
                    resource_type: load-balancer
                    interface: https
                  relations:
                    - service: App1
                      interface: https
                    - service: App2
                      interface: https
                    - service: App3
                      interface: http
                App1:
                  component:
                    resource_type: application
                    interface: https
                  relations:
                    - service: DB
                      interface: mysql
                App2:
                  component:
                    resource_type: application
                    interface: https
                  relations:
                    - service: DB
                      interface: mysql
                App3:
                  component:
                    resource_type: application
                    interface: http
                  relations:
                    - service: DB
                      interface: mysql
                    - MongoDB: mongodb
                DB:
                  component:
                    resource_type: database
                    interface: mysql
                MongoDB:
                  component:
                    resource_type: database
                    interface: mongodb""")
        contents = parser.load(checkmatefile)
        topo = topology.Topology.from_deployment(contents)
        expected_relations = {
            'App1': [('DB', 'mysql')],
            'App2': [('DB', 'mysql')],
            'App3': [('DB', 'mysql'), ('MongoDB', 'mongodb')],
            'LoadBalancer': [('App1', 'https'), ('App2', 'https'),
                             ('App3', 'http')],
        }
        self.assertDictEqual(expected_relations, topo.relations)

    def test_relations_invalid_service(self):
        """Relation refers to a missing service."""
        checkmatefile = six.StringIO("""
            blueprint:
              id: def456
              name: sample app
              version: 0.0.1
              services:
                LoadBalancer:
                  component:
                    resource_type: load-balancer
                    interface: https
                  relations:
                    - service: App1
                      interface: https
                    - service: App2
                      interface: https
                App1:
                  component:
                    resource_type: application
                    interface: https
                  relations:
                    - service: DB
                      interface: mysql
                App2:
                  component:
                    resource_type: application
                    interface: https
                  relations:
                    # The service `Database` doesn't exist
                    - service: Database
                      interface: mysql
                DB:
                  component:
                    resource_type: database
                    interface: mysql""")
        contents = parser.load(checkmatefile)
        with self.assertRaises(topology.TopologyError) as terr:
            topology.Topology.from_deployment(contents)
        self.assertEqual(
            "Service 'App2' defines a relation to an unknown remote service "
            "'Database'.",
            str(terr.exception)
        )

    def test_no_relations(self):
        """A case with no relations defined at all."""
        checkmatefile = six.StringIO("""
        blueprint:
          id: def456
          name: test
          version: 0.0.1
          services:
            App1:
              component:
                resource_type: application
                interface: https
            App2:
              component:
                resource_type: application
                interface: https""")
        contents = parser.load(checkmatefile)
        topo = topology.Topology.from_deployment(contents)
        self.assertDictEqual({}, topo.relations)


if __name__ == '__main__':
    unittest.main()
