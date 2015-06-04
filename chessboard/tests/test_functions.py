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

"""Tests for the :mod:`chessboard.functions` module."""

import unittest

import mock

from chessboard import exceptions
from chessboard import functions


class TestScalarFunctions(unittest.TestCase):

    """Test core blueprint function."""

    def test_scalar_none(self):
        """Test that None is passed through."""
        self.assertIsNone(functions.evaluate(None))

    def test_scalar_integer(self):
        """Test that integer is passed through."""
        self.assertEqual(functions.evaluate(1), 1)

    def test_scalar_string(self):
        """Test that string is passed through."""
        self.assertEqual(functions.evaluate("A"), "A")

    def test_scalar_boolean(self):
        """Test that booleans are passed through."""
        self.assertIs(functions.evaluate(True), True)
        self.assertIs(functions.evaluate(False), False)

    def test_empty_list(self):
        """Test that empty list is passed through."""
        self.assertEqual(functions.evaluate([]), [])

    def test_scalar_list(self):
        """Test that list is passed through."""
        self.assertEqual(functions.evaluate(['1', 2]), ['1', 2])


class TestObjectFunctions(unittest.TestCase):

    """Test core blueprint functions for complex datatypes."""

    def setUp(self):
        self.data = {
            'name': 'Sample Data',
            'blueprint': {
                'options': {
                    'opt1int': {
                        'type': 'integer'
                    },
                    'opt2string': {
                        'type': 'string'
                    },
                },
                'services': {
                    'S1': {
                        'component': {'id': 'S1comp'}
                    },
                    'S2': {
                        'component': {'id': 'S2comp'}
                    },
                }},
            'resources': {
                '0': {
                    'service': 'S1',
                    'instance': {'id': 'S1id'},
                },
                '1': {
                    'service': 'S2',
                    'instance': {'id': 'S2id'},
                },
            },
            'inputs': {
                'region': 'North',
                'blueprint': {
                    'size': 'big'
                }
            },
        }

    def test_value_none(self):
        self.assertIsNone(functions.evaluate({'value': None}))

    def test_value_integer(self):
        self.assertEqual(functions.evaluate({'value': 1}), 1)

    def test_value_name(self):
        self.assertEqual(functions.evaluate({'value': 'name://'}, **self.data),
                         'Sample Data')

    def test_value_deep(self):
        function = {'value': 'resources://0/instance/id'}
        self.assertEqual(functions.evaluate(function, **self.data),
                         'S1id')

    def test_resources(self):
        function = {'value': 'resources://1'}
        self.assertEqual(functions.evaluate(function, **self.data),
                         {'service': 'S2', 'instance': {'id': 'S2id'}})

    def test_inputs_scalar(self):
        function = {'value': 'inputs://region'}
        self.assertEqual(functions.evaluate(function, **self.data), "North")

    def test_inputs_scalar_negative(self):
        """Blueprint input does not pick up global input."""
        function = {'value': 'inputs://size'}
        self.assertIsNone(functions.evaluate(function, **self.data))

    def test_inputs_blueprint(self):
        function = {'value': 'inputs://region'}
        self.assertEqual(functions.evaluate(function, **self.data), "North")

    def test_inputs_blueprint_negative(self):
        """Global input does not pick up blueprint input."""
        function = {'value': 'inputs://size'}
        self.assertIsNone(functions.evaluate(function, **self.data))

    @mock.patch.object(functions, "get_pattern")
    def test_pattern(self, mock_get_pattern):
        mock_get_pattern.return_value = "foo"
        function = {'value': 'patterns.regex.linux_user.required'}
        self.assertEqual(functions.evaluate(function, **self.data), "foo")


class TestSafety(unittest.TestCase):

    """Test core blueprint functions for safety."""

    def test_self_referencing(self):
        """Test that self-teferencing object works."""
        data = {
            'object': 1
        }
        data['object'] = data
        function = {'value': 'object://object'}
        self.assertEqual(functions.evaluate(function, **data), data)


class TestPathParsing(unittest.TestCase):

    """Test URL evaluation."""

    def setUp(self):
        self.data = {
            'name': 'Sample Data',
            'root': {'base': 'item'},
            'deep': {'A': {'B': {'C': 'top'}}},
        }

    def test_path_none(self):
        """Test that none doesn't break."""
        self.assertIsNone(functions.get_from_path(None))

    def test_path_blank(self):
        """Test that empty string doesn't break."""
        self.assertEqual(functions.get_from_path(''), '')
        self.assertFalse(functions.path_exists(''))

    def test_path_scheme_only(self):
        """Test that passing only a URI scheme works."""
        self.assertEqual(functions.get_from_path('https://'), 'https://')
        self.assertFalse(functions.path_exists('https://'))
        self.assertFalse(functions.path_exists('foo://', foo=1))

    def test_path_scheme_only_scalar(self):
        """Test that scalar value at root is returned."""
        result = functions.get_from_path('name://', **self.data)
        expected = 'Sample Data'
        self.assertEqual(result, expected)

    def test_path_root(self):
        """Test that one-level path works."""
        result = functions.get_from_path('root://', **self.data)
        expected = {'base': 'item'}
        self.assertEqual(result, expected)

    def test_path_scalar(self):
        """Test that one-level-deep scalar works."""
        result = functions.get_from_path('root://base', **self.data)
        expected = 'item'
        self.assertEqual(result, expected)

    def test_path_deep(self):
        """Test that deep path works."""
        result = functions.get_from_path('deep://A/B/C', **self.data)
        expected = 'top'
        self.assertEqual(result, expected)

    def test_path_skip_invalid(self):
        """Test that invalid path is unchanged."""
        self.assertEqual(functions.get_from_path('blah'), 'blah')
        self.assertEqual(functions.get_from_path('blah', a=1), 'blah')


class TestURIDetection(unittest.TestCase):

    """Test URI detection."""

    def test_is_uri(self):
        """Test URI detection."""
        self.assertTrue(functions.is_uri("http://test"))
        self.assertTrue(functions.is_uri("options://region"))
        self.assertTrue(functions.is_uri("resources://A/B/C"))

    def test_is_uri_negative(self):
        """Test URI detection (negative)."""
        self.assertFalse(functions.is_uri("://test"))
        self.assertFalse(functions.is_uri("://"))
        self.assertFalse(functions.is_uri(''))
        self.assertFalse(functions.is_uri(None))
        self.assertFalse(functions.is_uri({}))


class TestPatterns(unittest.TestCase):

    """Test Pattern detection and parsing."""

    def test_is_pattern(self):
        """Test pattern detection."""
        self.assertTrue(functions.is_pattern("patterns.regex.linux_user"))

    def test_is_pattern_negative(self):
        """Test pattern detection Inegative)."""
        self.assertFalse(functions.is_pattern("patterns"))
        self.assertFalse(functions.is_pattern("patterns."))
        self.assertFalse(functions.is_pattern(''))
        self.assertFalse(functions.is_pattern(None))
        self.assertFalse(functions.is_pattern({}))

    def test_is_pattern_not_there(self):
        """Test non-existing pattern check."""
        self.assertTrue(functions.is_pattern("patterns.foo"))

    def test_get_pattern_missing(self):
        """Test missing pattern raises error."""
        with self.assertRaises(exceptions.ChessboardDoesNotExist):
            functions.get_pattern('patterns.foo', {'patterns': {'bar': 1}})

    def test_get_pattern_bad_format(self):
        """Test badly formatted pattern raises error."""
        with self.assertRaises(exceptions.ChessboardError):
            functions.get_pattern('patterns.bar', {'patterns': {'bar': int()}})

    def test_get_pattern_no_value(self):
        """Test pattern wth missing value raises error."""
        with self.assertRaises(exceptions.ChessboardError):
            functions.get_pattern('patterns.bar', {'patterns': {'bar': {}}})

    def test_get_pattern(self):
        """Test get_pattern works."""
        patterns = {'patterns': {'foo': {'value': 'X'}}}
        self.assertEqual(functions.get_pattern('patterns.foo', patterns), 'X')


class TestParse(unittest.TestCase):

    """Test Function Parsing."""

    def test_parsing_only_values(self):
        """Test that only values are parsed."""
        data = {'value': {'value': False}}
        self.assertEqual(functions.parse(data), {'value': False})

    def test_plain_object(self):
        """Test that objects get passed back."""
        self.assertEqual(functions.parse({}), {})
        self.assertEqual(functions.parse({'A': 1}), {'A': 1})

    def test_scalars(self):
        """Test that scalar values are unchanged."""
        self.assertEqual(functions.parse(1), 1)
        self.assertEqual(functions.parse('A'), 'A')
        self.assertEqual(functions.parse(''), '')
        self.assertEqual(functions.parse(None), None)
        self.assertEqual(functions.parse(False), False)


if __name__ == '__main__':
    unittest.main()
