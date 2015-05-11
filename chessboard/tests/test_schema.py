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

"""Tests for the :mod:`chessboard.schema` module."""

import unittest

import six
import voluptuous as volup
import yaml

from chessboard import parser
from chessboard import schema as cb_schema


class TestDictOf(unittest.TestCase):

    """Tests for :func:`chessboard.schema.DictOf`."""

    def setUp(self):
        """For these tests, we create a simple but realstic schema."""
        component_schema = volup.Schema({
            volup.Required('interface'): str,
            volup.Required('type'): str,
        })
        service_schema = volup.Schema({
            volup.Required('component'): component_schema,
            volup.Optional('relations'): [dict],
        })
        blueprint_schema = volup.Schema({
            volup.Required('services'): cb_schema.DictOf(service_schema),
        })
        self.schema = volup.Schema({
            volup.Required('blueprint'): blueprint_schema,
        })

    def test_valid(self):
        """Test validation against a valid input."""
        content = yaml.safe_load("""
            blueprint:
              services:
                comp1:
                  component:
                    interface: http
                    type: bar
                  relations:
                  - comp2: http
                  - comp3: http
                comp2:
                  component:
                    interface: http
                    type: baz""")
        # The validation simply returns the input value
        output = self.schema(content)
        self.assertEqual(output, content)

    def test_invalid_missing_required(self):
        """Test validation when missing a required element."""
        content = yaml.safe_load("""
            blueprint:
              services:
                comp1:
                  component:
                    interface: http
                    type: bar
                  relations:
                  - comp2: http
                  - comp3: http
                comp2:
                  component:
                    interface: http
                    type: baz
                comp3:
                  # comp3 is missing a `component` key
                  relations:
                  - comp2: http""")
        with self.assertRaises(volup.MultipleInvalid) as mi:
            self.schema(content)

        expected_path = ['blueprint', 'services', 'comp3', 'component']
        # Some of the `path` elements may look like strings, but are actually
        # `voluptuous.Required` types; hence the map(str, ...).
        self.assertListEqual(expected_path,
                             [str(x) for x in mi.exception.path])

    def test_invalid_not_a_dict(self):
        """Test validation when the data is a list, not a dict.

        In this test, we've turned `services` into a list, instead of a dict.
        The schema requires that it is a dict of services, so we should get
        an error on this.
        """
        content = yaml.safe_load("""
            blueprint:
              services:
                - comp1:
                  component:
                    interface: http
                    type: bar
                  relations:
                  - comp2: http
                  - comp3: http
                - comp2:
                  component:
                    interface: http
                    type: baz""")
        with self.assertRaises(volup.MultipleInvalid) as mi:
            self.schema(content)

        expected_path = ['blueprint', 'services']
        self.assertListEqual(expected_path,
                             [str(x) for x in mi.exception.path])


class TestCheckmatefileSchema(unittest.TestCase):

    """Main tests for the Checkmatefile schema definition."""

    def test_valid(self):
        """Test a simple but realistic Checkmatefile against the schema."""
        fileobj = six.StringIO("""
            blueprint:
              id: 8363F2D2284D4871BC618E92D152994F
              name: "magentostack-cloud"
              description: "Magento install with Cloud Databases."
              version: 1.0.0
              services:
                lb:
                  component:
                    interface: http
                    resource_type: load-balancer
                    constraints:
                    - algorithm: ROUND_ROBIN
                  relations:
                  - service: magento
                    interface: http
                  - service: magento-worker
                    interface: http
                  display-name: Load Balancer
                'magento':
                  component:
                    name: magento
                    resource_type: application
                    interface: http
                    role: master
                  constraints:
                  - setting: count
                    value: 1
                  - setting: resource_type
                    value: compute
                  - setting: disk
                    value: 50
                'magento-worker':
                  component:
                    name: magento
                    resource_type: application
                    interface: http
                    role: worker
                  constraints:
                  - setting: count  # used for manual scaling
                    greater-than-or-equal-to: 0
                    less-than: 9
                  - setting: resource_type
                    value: compute
                  - setting: disk
                    value: 50""")
        parser.load(fileobj, schema=cb_schema.CHECKMATEFILE_SCHEMA)

    def test_invalid(self):
        """Test an extremely simple invalid blueprint."""
        fileobj = six.StringIO("""
            blueprint: {}
            test: asfsfas""")
        with self.assertRaises(parser.MultiValidationError) as mve:
            parser.load(fileobj, schema=cb_schema.CHECKMATEFILE_SCHEMA)

        expected_message = """\
['blueprint']['services']: required key not provided
['test']: extra keys not allowed"""
        self.assertEqual(expected_message, mve.exception.message)

    def test_numeric_blueprint_id_not_allowed(self):
        """Numeric blueprint id value are not allowed.

        The reason for this is because the number may be converted in
        unexpected ways:

        100 -> "100"
        0100 -> "64"
        0x0 -> "0"
        """
        invalid_ids = ["100", "0100", "0x0"]

        for invalid_id in invalid_ids:
            fileobj = six.StringIO("""
                blueprint:
                  id: %(invalid_id)s
                  name: test
                  services: {}
                  version: 0.0.1""" % dict(invalid_id=invalid_id))

            with self.assertRaises(parser.MultiValidationError) as mve:
                parser.load(fileobj, schema=cb_schema.CHECKMATEFILE_SCHEMA)

            self.assertEqual("['blueprint']['id']: expected str",
                             str(mve.exception))


class TestRelationSchema(unittest.TestCase):

    """Test Relation schema."""

    def test_relations(self):
        obj = yaml.safe_load("""
        relations:
        - db: mysql
        - cache: redis#objects
        - service: foo
          interface: varnish
          connect-from: sessions
          connect-to: persistent
          attributes:
            timeout: 300
        """)
        unchanged = [o.copy() for o in obj['relations']]
        _schema = volup.Schema([cb_schema.Relation()])
        errors = cb_schema.validate(obj['relations'], _schema)
        self.assertFalse(errors)
        # Check that coercion did not get applied
        self.assertEqual(unchanged, obj['relations'])

    def test_relations_coerce(self):
        obj = yaml.safe_load("""
        relations:
        - db: mysql
        - cache: redis#objects
        - service: foo
          interface: varnish
          connect-from: sessions
          connect-to: persistent
          attributes:
            timeout: 300
        """)
        _schema = volup.Schema([cb_schema.Relation(coerce=True)])
        cb_schema.validate(obj['relations'], _schema)
        expected = {
            'relations': [
                {
                    'service': 'db',
                    'interface': 'mysql',
                }, {
                    'service': 'cache',
                    'interface': 'redis',
                    'connect-from': 'objects',
                }, {
                    'service': 'foo',
                    'interface': 'varnish',
                    'connect-from': 'sessions',
                    'connect-to': 'persistent',
                    'attributes': {
                        'timeout': 300
                    },
                },
            ]
        }
        self.assertEqual(obj, expected)

    def test_relations_negative_dict(self):
        """Ensure dict format is not allowed."""
        obj = yaml.safe_load("""
        relations:
        - pages:
            service: cache
            interface: memcache
        """)
        _schema = volup.Schema([cb_schema.Relation()])
        errors = cb_schema.validate(obj['relations'], _schema)
        self.assertEqual(errors, ["invalid list value @ data[0]"])

    def test_relations_negative_service(self):
        """Ensure 'service' is required."""
        obj = yaml.safe_load("""
        relations:
        - connect-to: test
          interface: mysql  # No service
        """)
        _schema = volup.Schema([cb_schema.Relation()])
        errors = cb_schema.validate(obj['relations'], _schema)
        expected = [
            "required key not provided @ data[0]['service']",
        ]
        self.assertEqual(errors, expected)


if __name__ == '__main__':
    unittest.main()
