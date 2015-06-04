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

"""Tests for the :mod:`chessboard.classes` module."""

import copy
import json
import unittest

import yaml

from chessboard import classes


class TestExtensibleDict(unittest.TestCase):

    """Tests for :class:`chessboard.classes.ExtensibleDict`."""

    def setUp(self):  # noqa
        self.edict = classes.ExtensibleDict([('a', 1), ('b', 2)], c=3)
        self.edict_empty = classes.ExtensibleDict()

    def test_init(self):
        """Check that init works like dict does."""
        data = dict(a=1, b=2, c=3)
        edict = classes.ExtensibleDict(data)
        self.assertDictEqual(edict, data)

    def test_iter(self):
        """Check that iteration works properly."""
        # Empty
        edict = classes.ExtensibleDict()
        self.assertEqual([], list(iter(edict)))

        # Not empty
        edict = classes.ExtensibleDict([('a', 1), ('b', 2)], c=3)
        self.assertEqual(['a', 'b', 'c'], sorted(list(iter(edict))))

    def test_json_serialization(self):
        """Check that an ExtensibleDict dumps to json properly."""
        # Empty
        edict = classes.ExtensibleDict()
        self.assertEqual('{}', json.dumps(edict))

        # Not empty
        edict = classes.ExtensibleDict([('a', 1), ('b', 2)], c=3)
        self.assertEqual(
            '{"a": 1, "b": 2, "c": 3}', json.dumps(edict, sort_keys=True)
        )

    def test_repr(self):
        """Check that obj.__repr__() displays the underlying dict."""
        self.assertEqual('{}', repr(self.edict_empty))
        self.assertEqual("{'a': 1}", repr(classes.ExtensibleDict(a=1)))

    def test_basic_operations(self):
        """Test basic dictionary-type operations."""
        edict = classes.ExtensibleDict(key='value')
        self.assertIn('key', edict)
        self.assertEqual(edict['key'], 'value')

        edict['new'] = 2
        self.assertIn('new', edict)
        self.assertEqual(edict['new'], 2)
        self.assertEqual(len(edict), 2)

        del edict['new']
        self.assertNotIn('new', edict)

    def test_copy(self):
        """Test that copying works, per Python convention."""
        the_copy = copy.copy(self.edict)

        # Conents should be equivalent
        self.assertEqual(the_copy.__dict__, self.edict.__dict__)
        # IDs should not be the same, indicating that a copy was made
        self.assertNotEqual(id(the_copy), id(self.edict))
        for key in self.edict:
            # But since it's a shallow copy, the values in the copy should just
            # be references to the originals.
            self.assertEqual(id(the_copy[key]), id(self.edict[key]))

    def test_deepcopy(self):
        """Test that deep copying works, per Python convnention."""
        edict = classes.ExtensibleDict(a=[1, 2, 3], b=dict())
        the_copy = copy.deepcopy(edict)

        # Contents should be equivalent
        self.assertEqual(the_copy.__dict__, edict.__dict__)
        # Copy should not have the same id
        self.assertNotEqual(id(the_copy), id(edict))
        # Each element should be a copy as well, and should not have the same
        # id
        for key in edict:
            self.assertNotEqual(id(the_copy[key]), id(edict[key]))

    def test_update(self):
        """Test that the `update` method works just like a `dict`."""
        edict = classes.ExtensibleDict()
        self.assertEqual({}, edict)
        edict.update(dict(a=1))
        self.assertEqual({'a': 1}, edict)
        edict.update(dict(a=2))
        self.assertEqual({'a': 2}, edict)

    def test_clear(self):
        """Test that the `clear` method works just like a `dict`."""
        edict = classes.ExtensibleDict({1: 2})
        self.assertEqual({1: 2}, edict)
        edict.clear()
        self.assertEqual({}, edict)

    def test_blank(self):
        """Allow blank instantiation without schema validation.

        voluptuous does `type(data)()` during validation.
        """
        @staticmethod
        def schema(data):
            """Test callable."""
            raise ValueError("None shall pass %s" % data)

        class Fail(classes.ExtensibleDict):

            """Test class with schema."""

            __schema__ = schema

        with self.assertRaises(ValueError):
            Fail({1: 2})
        self.assertEqual(Fail({}), {})
        self.assertEqual(Fail(), {})

    def test_extensible_dict_is_a_dict(self):
        """ExtensibleDict should look like a dict."""
        self.assertTrue(issubclass(classes.ExtensibleDict, dict))
        self.assertTrue(isinstance(classes.ExtensibleDict(), dict),
                        msg="ExtensibleDict is not being seen as a dict")
        self.assertEqual(classes.ExtensibleDict(test=1)['test'], 1)


class TestExtensibleDictYAMLSerialization(unittest.TestCase):

    """Test the ExtensibleDict is serializable in YAML."""

    def test_yaml_serialization(self):
        """ExtensibleDict acts like dict in YAML."""
        data = {'key': {'a': 1}}
        edict = classes.ExtensibleDict(data)
        serialized = yaml.dump(edict, default_flow_style=False)
        self.assertEqual(serialized, 'key:\n  a: 1\n')

    def test_yaml_representer(self):
        """ExtensibleDict subclass acts like dict in YAML."""
        class SomeClass(classes.ExtensibleDict):

            """Test class."""

            pass

        classes.register_yaml_representer(SomeClass)
        data = SomeClass({'key': {'a': 1}})
        self.assertDictEqual(dict(data), {'key': {'a': 1}})

        result = yaml.safe_dump(SomeClass(data), default_flow_style=False)
        self.assertEqual(result, 'key:\n  a: 1\n')

if __name__ == '__main__':
    unittest.main()
