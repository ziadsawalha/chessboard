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

"""Tests for the :mod:`chessboard.exceptions` module."""

import unittest

from chessboard import exceptions


class TestChessboardError(unittest.TestCase):

    """Tests for the :mod:`chessboard.exceptions` module."""

    def test_exception(self):
        """Check exception instantiation."""
        exc = exceptions.ChessboardError()
        self.assertEqual(str(exc), "Chessboard Error.")
        self.assertEqual(repr(exc), "ChessboardError(None, None)")

    def test_exception_message(self):
        """Check exception instantition with arguments."""
        exc = exceptions.ChessboardError("Technical Message")
        self.assertEqual(str(exc), "Technical Message")
        self.assertEqual(
            repr(exc),
            "ChessboardError('Technical Message', None)")

    def test_exception_friendly(self):
        """Exception uses standard message for __str__ like other exceptions.

        We only want to use friendly messages when we explicetly want them,
        otherwise we want to behave like a normal exception.
        """
        exc = exceptions.ChessboardError("Technical Message",
                                         client_message="Friendly Message")
        self.assertEqual(str(exc), "Technical Message")

    def test_exception_representable(self):
        """Representation of ChessboardError allows for eval()."""
        exc = exceptions.ChessboardError("Technical Message",
                                         client_message="Friendly Message")
        representation = repr(exc)
        self.assertEqual(representation,
                         "ChessboardError('Technical Message', "
                         "'Friendly Message')")

    def test_exception_evaluable(self):
        """Test Exception can be Deserialized."""
        exc = exceptions.ChessboardError("Technical Message",
                                         client_message="Friendly Message")
        rehydratred = eval(repr(exc),  # pylint: disable=W0123
                           {'ChessboardError': exceptions.ChessboardError},
                           {'no': 'global'})
        self.assertEqual(rehydratred.__dict__, exc.__dict__)


if __name__ == '__main__':
    unittest.main()
