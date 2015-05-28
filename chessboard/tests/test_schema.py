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

import os
import unittest
import uuid

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


class TestRequireOne(unittest.TestCase):

    """Tests for :func:`chessboard.schema.RequireOne`."""

    def test_valid(self):
        """Test RequireOne passes valid data."""
        schema = cb_schema.RequireOne(['a', 'b'])
        schema({'a': 1})
        schema({'b': 1})
        schema({'a': 1, 'b': 2})

    def test_invalid(self):
        """Test RequireOne fails invalid data."""
        schema = cb_schema.RequireOne(['a', 'b'])
        with self.assertRaises(cb_schema.RequireOneInvalid):
            schema({'x': 1})
        with self.assertRaises(cb_schema.RequireOneInvalid):
            schema({})


class TestSchemaDocs(unittest.TestCase):

    """Test that documentation is parseable and implemented."""

    def test_docs_exist(self):
        """Confirm `schema_docs.yaml` is there."""
        self.assertTrue(os.path.exists, cb_schema.DOCS_PATH)

    def test_docs_valid_yaml(self):
        """Confirm schema file has valid YAML in it."""
        self.assertIsInstance(yaml.safe_load(open(cb_schema.DOCS_PATH, 'r')),
                              dict)

    def test_docs_valid_schema(self):
        """Confirm schema file has valid docs."""
        self.assertIsInstance(
            cb_schema.load_docs(open(cb_schema.DOCS_PATH, 'r')), dict)

    def test_definition_finder_(self):
        """Check that supplied schema is used."""
        schema = cb_schema.CHECKMATEFILE_SCHEMA.find_schema(['blueprint'])
        self.assertIs(schema, cb_schema.BLUEPRINT_SCHEMA)

    def test_definition_finder_deep(self):
        """Test with key ('lb') and index (0) in long path."""
        service = 'lb'
        index = 0
        schema = cb_schema.CHECKMATEFILE_SCHEMA.find_schema(
            ['blueprint', 'services', service, 'constraints', index, 'foo'])
        self.assertIs(schema, cb_schema.CONSTRAINT_SCHEMA)

    def test_undocumented_error(self):
        """An error with no docs should not cause a new exception."""
        schema = cb_schema.DocumentedSchema({'foo': 1})
        try:
            schema({'bar': 2})
        except volup.MultipleInvalid as exc:
            self.assertEqual(len(exc.errors), 1)
            self.assertFalse(hasattr(exc.errors[0], 'docs'))

    def test_standard_type_definition(self):
        """Don't fail if schema returned is a standard type.

        If a list or dict are returned, they should not cause the decorater
        function to fail. We probably should wrap these in DocumentedSchema
        classes to get them properly documented.
        """
        blueprint = six.StringIO("""
            blueprint:
              services:
                foo:
                  relations:
                    not-list: But it should be'
            """)
        with self.assertRaises(parser.MultiValidationError) as mve:
            parser.load(blueprint, schema=cb_schema.CHECKMATEFILE_SCHEMA)
        error = mve.exception.errors[0]
        self.assertEqual(error.path,
                         ['blueprint', 'services', 'foo', 'relations'])
        self.assertEqual(error.msg, 'expected a list')

    def test_fail_double_registration(self):
        """Fail if different schema are registered with the same name."""
        name = uuid.uuid4().hex
        schema1 = cb_schema.DocumentedSchema(str, name=name).register()
        schema2 = cb_schema.DocumentedSchema(int, name=name)
        self.assertFalse(schema1 is schema2)
        with self.assertRaises(KeyError):
            schema2.register()

    def test_generate_docs(self):
        self.assertEqual(
            cb_schema.generate_docs(docs={'foo': {'docs': '**markdown**'}}),
            """<!--Content autogenerated from schema_docs.yaml-->
# Glossary

[foo](#foo)  \


#### <a name="foo"></a>foo

**markdown**
""")


class TestVerboseParser(unittest.TestCase):

    """Test that documentation is returned."""

    def test_error_docs(self):
        """Test verbose errors."""
        fileobj = six.StringIO("""
            blueprint:
              id: 0100
              services:
                lb:
                  constraints:
                  - foo: []
        """)
        with self.assertRaises(parser.MultiValidationError) as mve:
            parser.load(fileobj, schema=cb_schema.CHECKMATEFILE_SCHEMA)

        self.assertTrue(all(hasattr(e, 'docs') for e in mve.exception.errors))


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
        """Test Relation() passes valid relations unchanged."""
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
        errors = inspect(obj['relations'], _schema)
        self.assertFalse(errors)
        # Check that coercion did not get applied
        self.assertEqual(unchanged, obj['relations'])

    def test_relations_coerce(self):
        """Test Relation() coerces relations when requested."""
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
        inspect(obj['relations'], _schema)
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
        """Ensure dict not allowed as value."""
        obj = yaml.safe_load("""
        relations:
        - pages:
            service: cache
            interface: memcache
        """)
        _schema = volup.Schema([cb_schema.Relation()])
        errors = inspect(obj['relations'], _schema)
        self.assertEqual(errors, ["invalid list value @ data[0]"])

    def test_relations_negative_type(self):
        """Ensure invalid types are not allowed."""
        _schema = volup.Schema(cb_schema.Relation())
        errors = inspect("string", _schema)
        self.assertEqual(errors, ["not a valid relation entry"])

    def test_relations_negative_service(self):
        """Ensure 'service' is required."""
        obj = yaml.safe_load("""
        relations:
        - connect-to: test
          interface: mysql  # No service
        """)
        _schema = volup.Schema([cb_schema.Relation()])
        errors = inspect(obj['relations'], _schema)
        expected = [
            "required key not provided @ data[0]['service']",
        ]
        self.assertEqual(errors, expected)


def inspect(obj, schema):
    """Inspect an in-memory object against a schema.

    :param obj: a dict of the object to validate
    :param schema: a schema to validate against (usually from this file)

    :returns: list (contains errors if they exist)
    """
    errors = []
    if schema:
        try:
            schema(obj)
        except volup.MultipleInvalid as exc:
            for error in exc.errors:
                errors.append(str(error))
    return errors


if __name__ == '__main__':
    unittest.main()
