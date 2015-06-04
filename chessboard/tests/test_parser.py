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

"""Tests for the :mod:`chessboard.parser` module."""

import unittest

import six
import voluptuous as volup

from chessboard import parser


class TestMultiValidationError(unittest.TestCase):

    """Tests for :class:`chessboard.parser.MultiValidationError`.

    Mostly, we need to tests the formatting of error messages.
    """

    def test_error_formatting(self):
        """Test the formatting of error paths."""
        schema = volup.Schema({
            volup.Required('blueprint'): volup.Schema({
                volup.Required('id'): str,
                volup.Required('name'): str,
                volup.Optional('description'): str,
            }),
        })

        fileobj = six.StringIO("""
            blueprint:
                id: def456
            inputs: {}""")

        expected_repr = """\
MultiValidationError(
\t['blueprint']['name']: required key not provided
\t['inputs']: extra keys not allowed
)"""
        expected_str = """\
['blueprint']['name']: required key not provided
['inputs']: extra keys not allowed"""

        expected_message = (
            "['blueprint']['name']: required key not provided\n"
            "['inputs']: extra keys not allowed"
        )
        with self.assertRaises(parser.MultiValidationError) as mve:
            parser.load(fileobj, schema=schema)

        self.assertEqual(expected_str, str(mve.exception))
        self.assertEqual(expected_repr, repr(mve.exception))
        self.assertEqual(expected_message, mve.exception.message)


if __name__ == '__main__':
    unittest.main()
