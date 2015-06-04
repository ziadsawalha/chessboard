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

"""Tests for the :mod:`chessboard.utils` module."""

import time
import unittest
import uuid

import mock

from chessboard import utils


class TestIsUuid(unittest.TestCase):

    """Main Tests for the :mod:`chessboard.utils.is_uuid` function."""

    def test_is_uuid_blanks(self):
        """Check is_uuid handles falsy values."""
        self.assertFalse(utils.is_uuid(None), "None is not a UUID")
        self.assertFalse(utils.is_uuid(""), "Empty string is not a UUID")
        self.assertFalse(utils.is_uuid(" "), "Space is not a UUID")

    def test_is_uuid_negatives(self):
        """Check is_uuid handles bad values."""
        self.assertFalse(utils.is_uuid("12345"), "12345 is not a UUID")
        self.assertFalse(utils.is_uuid(utils), "module is not a UUID")

    def test_is_uuid_positives(self):
        """Check is_uuid detects valid UUID values."""
        self.assertTrue(utils.is_uuid(uuid.uuid4()), "uuid() is a UUID")
        self.assertTrue(utils.is_uuid(uuid.uuid4().hex),
                        "uuid string is a UUID")


class TestDictPaths(unittest.TestCase):

    """Main Tests for the :mod:`chessboard.utils` module."""

    def test_write_path(self):
        """Test updating path in dict works."""
        cases = [
            {
                'name': 'scalar at root',
                'start': {},
                'path': 'root',
                'value': 'scalar',
                'expected': {'root': 'scalar'}
            }, {
                'name': 'int at root',
                'start': {},
                'path': 'root',
                'value': 10,
                'expected': {'root': 10}
            }, {
                'name': 'bool at root',
                'start': {},
                'path': 'root',
                'value': True,
                'expected': {'root': True}
            }, {
                'name': 'value at two piece path',
                'start': {},
                'path': 'root/subfolder',
                'value': True,
                'expected': {'root': {'subfolder': True}}
            }, {
                'name': 'value at multi piece path',
                'start': {},
                'path': 'one/two/three',
                'value': {},
                'expected': {'one': {'two': {'three': {}}}}
            }, {
                'name': 'add to existing',
                'start': {'root': {'exists': True}},
                'path': 'root/new',
                'value': False,
                'expected': {'root': {'exists': True, 'new': False}}
            }, {
                'name': 'overwrite existing',
                'start': {'root': {'exists': True}},
                'path': 'root/exists',
                'value': False,
                'expected': {'root': {'exists': False}}
            }
        ]
        for case in cases:
            result = case['start']
            utils.write_path(result, case['path'], case['value'])
            self.assertDictEqual(result, case['expected'], msg=case['name'])

    def test_read_path(self):
        """Test reading path in dict works."""
        cases = [
            {
                'name': 'simple value',
                'start': {'root': 1},
                'path': 'root',
                'expected': 1
            }, {
                'name': 'simple path',
                'start': {'root': {'folder': 2}},
                'path': 'root/folder',
                'expected': 2
            }, {
                'name': 'blank path',
                'start': {'root': 1},
                'path': '',
                'expected': None
            }, {
                'name': '/ only',
                'start': {'root': 1},
                'path': '/',
                'expected': None
            }, {
                'name': 'extra /',
                'start': {'root': 1},
                'path': '/root/',
                'expected': 1
            }, {
                'name': 'nonexistent root',
                'start': {'root': 1},
                'path': 'not-there',
                'expected': None
            }, {
                'name': 'nonexistent path',
                'start': {'root': 1},
                'path': 'root/not-there',
                'expected': None
            }, {
                'name': 'empty source',
                'start': {},
                'path': 'root',
                'expected': None
            },
        ]
        for case in cases:
            result = utils.read_path(case['start'], case['path'])
            self.assertEqual(result, case['expected'], msg=case['name'])

    def test_path_exists(self):
        """Test checking path exists in dict works."""
        cases = [
            {
                'name': 'simple value',
                'start': {'root': 1},
                'path': 'root',
                'expected': True
            }, {
                'name': 'simple path',
                'start': {'root': {'folder': 2}},
                'path': 'root/folder',
                'expected': True
            }, {
                'name': 'blank path',
                'start': {'root': 1},
                'path': '',
                'expected': False
            }, {
                'name': '/ only',
                'start': {'root': 1},
                'path': '/',
                'expected': True
            }, {
                'name': 'extra /',
                'start': {'root': 1},
                'path': '/root/',
                'expected': True
            }, {
                'name': 'nonexistent root',
                'start': {'root': 1},
                'path': 'not-there',
                'expected': False
            }, {
                'name': 'nonexistent path',
                'start': {'root': 1},
                'path': 'root/not-there',
                'expected': False
            }, {
                'name': 'empty source',
                'start': {},
                'path': 'root',
                'expected': False
            },
        ]
        for case in cases:
            result = utils.path_exists(case['start'], case['path'])
            self.assertEqual(result, case['expected'], msg=case['name'])


class TestTime(unittest.TestCase):

    """Main Tests for the :mod:`chessboard.utils` module."""

    def test_get_formatted_time_string(self):
        """Test updating path in dict works."""
        some_time = time.gmtime(0)
        with mock.patch.object(utils.time, 'gmtime') as mock_gmt:
            mock_gmt.return_value = some_time
            result = utils.get_time_string()
            self.assertEqual(result, "1970-01-01 00:00:00 +0000")

    def test_get_formatted_time_string_with_input(self):
        result = utils.get_time_string(time_gmt=time.gmtime(0))
        self.assertEqual(result, "1970-01-01 00:00:00 +0000")


class TestYamlConversion(unittest.TestCase):

    """Main Tests for the :mod:`chessboard.utils` module."""

    def test_escape_yaml_simple_string_simple(self):
        self.assertEqual(utils.escape_yaml_simple_string('simple'), "simple")

    def test_escape_yaml_simple_string_null(self):
        self.assertEqual(utils.escape_yaml_simple_string(None), 'null')

    def test_escape_yaml_simple_string_blank(self):
        self.assertEqual(utils.escape_yaml_simple_string(''), "''")

    def test_escape_yaml_simple_string_at(self):
        self.assertEqual(utils.escape_yaml_simple_string("@starts_with_at"),
                         "'@starts_with_at'")

    def test_escape_yaml_simple_string_multi_line(self):
        self.assertEqual(utils.escape_yaml_simple_string('A\nB'), 'A\nB')

    def test_escape_yaml_simple_string_object(self):
        self.assertEqual(utils.escape_yaml_simple_string({'A': 1}), {'A': 1})


class TestUrlCreds(unittest.TestCase):

    """Main Tests for the :mod:`chessboard.utils` module."""

    def test_hide_url_password(self):
        hidden = utils.hide_url_password('http://user:pass@localhost')
        self.assertEqual(hidden, 'http://user:*****@localhost')

    def test_hide_url_password_mongo(self):
        hidden = utils.hide_url_password('mongodb://user:pass@localhost/db')
        self.assertEqual(hidden, 'mongodb://user:*****@localhost/db')


if __name__ == '__main__':
    unittest.main()
