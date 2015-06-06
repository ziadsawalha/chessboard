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

"""Custom Exception Classes for Chessboard.

To be serialization-friendly, call the Error __init__ with any extra
attributes:

class ChessboardCustomError(Exception):
    def __init__(self, something_custom):
        super(ChessboardCustomError, self).__init__(something_custom)
        self.something_custom = something_custom

This is important to allow exceptions to flow back from the message queue
tasks or other processes.
"""

BLUEPRINT_ERROR = "Blueprint syntax error"  # remove this


class ChessboardError(Exception):

    """Chessboard Error.

    Base Error for all Chessboard errors.

    The first line of the docstring ("Chessboard Error" in this case) is used
    as the default message.

    Supports these features:
    - external-facing, user-friendly error string.
    """

    def __init__(self, message=None, client_message=None):
        """Create Chessboard Error.

        :param client_message: a message to bubble up to clients (UI, CLI,
                etc...).
        """
        super(ChessboardError, self).__init__(message, client_message)
        self._message = message
        self._client_message = client_message

    @property
    def message(self):
        """Read only property for _message."""
        if self._message is None:
            return self.__doc__.split('\n')[0]
        else:
            return str(self._message)

    @property
    def client_message(self):
        """Return a friendly message always."""
        return self._client_message

    def __str__(self):
        """String representation."""
        return self.message


class ChessboardValidationError(ChessboardError):

    """Validation Error."""

    @property
    def client_message(self):
        """Return a friendly message always."""
        return self._client_message or self._message


class ChessboardNothingToDo(ChessboardError):

    """Nothing to be done for the given request."""


class ChessboardDoesNotExist(ChessboardError):

    """Object does not exist."""
