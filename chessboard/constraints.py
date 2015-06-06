# Copyright (c) 2011-2015 Rackspace US, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Constraint Validation Classes.

To add a new constraint type, add:

1. Create a class that inherits from Constraint
2. Override the allowed_keys and required_keys
3. override at a minimum the 'test' method
"""

import inspect
import logging
import re
import sys

import six

from chessboard import exceptions
from chessboard import functions

LOG = logging.getLogger(__name__)


class Constraint(object):

    """Base Class for all Constraints."""

    required_keys = []
    allowed_keys = []
    message = "not explained"

    @classmethod
    def is_syntax_valid(cls, constraint):
        """Check if this constraint's syntax is valid."""
        if not isinstance(constraint, dict):
            return False
        if not all(k in cls.allowed_keys for k in constraint.keys()):
            return False
        if not all(k in constraint.keys() for k in cls.required_keys):
            return False
        return True

    @classmethod
    def from_constraint(cls, constraint, **kwargs):
        """Instantiate correct constraint class based on constraint.

        :param kwargs: accepts parameters for function evaluation
        """
        constraint = functions.parse(constraint, **kwargs)
        for klass in CONSTRAINT_CLASSES:
            if klass.is_syntax_valid(constraint):
                return klass(constraint)
        raise exceptions.ChessboardValidationError(
            "Constraint '%s' is not a valid constraint" % constraint)

    def __init__(self, constraint):
        """Wrap constraint dict with a constraint class."""
        if not self.is_syntax_valid(constraint):
            raise exceptions.ChessboardValidationError(
                "Constraint '%s' is not a valid constraint" % constraint)
        self.constraint = constraint
        if 'message' in constraint:
            self.message = constraint['message']

    def test(self, value):
        """Run the constraint logic on the given value.

        :returns: boolean indicating if the constraint passed or failed.
        """
        return False


class RegExConstraint(Constraint):

    r"""RegEx Constraint.

    Syntax:

    - regex: {regular expression}
    - message: optional validation message

    Notes:

    - forward and backward lookups in the regexes are not supported on browsers
    - use a clear message for users but also for other who read your blueprint

    Example:

     constraints:
     - regex: ^(?=.*).{8,15}$
       message: must be between 8 and 15 characters long
     - regex: ^(?=.*\d)
       message: must contain a digit
     - regex: ^(?=.*[a-z])
       message: must contain a lower case letter
     - regex: ^(?=.*[A-Z])
       message: must contain an upper case letter
    """

    required_keys = ['regex']
    allowed_keys = ['regex', 'message']

    @classmethod
    def is_syntax_valid(cls, constraint):
        """Check if this constraint's syntax is valid."""
        if not super(RegExConstraint, cls).is_syntax_valid(constraint):
            return False
        return True

    def __init__(self, constraint):
        """Wrap constraint dict with a constraint class."""
        Constraint.__init__(self, constraint)
        try:
            self.expression = re.compile(constraint['regex'])
        except re.error:
            raise exceptions.ChessboardValidationError(
                "Constraint has an invalid regular expression: %s" %
                constraint['regex'])

    def test(self, value):
        """Run the constraint logic on the given value."""
        return self.expression.match(value)


class ProtocolsConstraint(Constraint):

    """URL Protocols Constraint.

    Syntax:

    - protocols: [list]
    - message: optional validation message

    Example:

     constraints:
     - protocols: ['http', 'https']
       message: only http and https URLs are supported
    """

    required_keys = ['protocols']
    allowed_keys = ['protocols', 'message']

    def __init__(self, constraint):
        """Wrap constraint dict with a constraint class."""
        Constraint.__init__(self, constraint)
        protocols = constraint['protocols']
        if not isinstance(protocols, list):
            raise exceptions.ChessboardValidationError(
                "Protocols constraint does not have a list of protocols "
                "supplied: %s" % protocols)
        self.protocols = protocols
        self.message = constraint.get('message') or "invalid protocol"

    def test(self, value):
        """Run the constraint logic on the given value."""
        if not issubclass(value.__class__, six.string_types):
            return False
        if '://' not in value:
            return False
        protocol = value[0:value.index('://')]
        return protocol in self.protocols


class InConstraint(Constraint):

    """Constraint to limit to a list.

    Syntax:

    - in: [list]
      message: optional validation message

    Notes:

    - clients (browsers) can use this to display a drop-down if 'choice' is not
      provided

    Example:

     constraints:
     - in: ['Ubuntu 12.04']
       message: only http and https URLs are supported
    """

    required_keys = ['in']
    allowed_keys = ['in', 'message']

    def __init__(self, constraint):
        """Wrap constraint dict with a constraint class."""
        Constraint.__init__(self, constraint)
        allowed = constraint['in']
        if not isinstance(allowed, list):
            raise exceptions.ChessboardValidationError(
                "In constraint does not have a list of values supplied: %s" %
                allowed)
        self.allowed = allowed

    def test(self, value):
        """Run the constraint logic on the given value."""
        return value in self.allowed


class SimpleComparisonConstraint(Constraint):

    """Constraint to for simple comparisons: >, <, >=, <=.

    Syntax (one or more of the following):

    - less-than: {value}
    - greater-than: {value}
    - less-than-or-equal-to: {value}
    - greater-than-or-equal-to: {value}

    - message: optional validation message

    Note:
    - a default message will be generated automatically but can be overridden
    - you can combine more than one rule in one constraint (split them up for
      clarity or to supply different validation messages)

    Example:

     constraints:
     - less-than: 8
       greater-than: 1
       message: must be between 3 and 7
    """

    required_keys = [
        'less-than',
        'greater-than',
        'less-than-or-equal-to',
        'greater-than-or-equal-to',
    ]
    allowed_keys = [
        'less-than',
        'greater-than',
        'less-than-or-equal-to',
        'greater-than-or-equal-to',
        'message',
    ]

    @classmethod
    def is_syntax_valid(cls, constraint):
        """Check if this constraint's syntax is valid."""
        if not isinstance(constraint, dict):
            return False
        if not all(k in cls.allowed_keys for k in constraint.keys()):
            return False

        # We use 'any' here instead of 'all'. We don't call the superclass

        if not any(k in constraint.keys() for k in cls.required_keys):
            return False
        return True

    def __init__(self, constraint):
        """Wrap constraint dict with a constraint class."""
        Constraint.__init__(self, constraint)
        rules = []
        messages = []
        for key, value in constraint.items():
            if key == 'less-than':
                rules.append(lambda x, v=value: x < v)
                messages.append("must be less than %s" % value)
            elif key == 'less-than-or-equal-to':
                rules.append(lambda x, v=value: x <= v)
                messages.append("must be less than or equal to %s" % value)
            elif key == 'greater-than':
                rules.append(lambda x, v=value: x > v)
                messages.append("must be greater than %s" % value)
            elif key == 'greater-than-or-equal-to':
                rules.append(lambda x, v=value: x >= v)
                messages.append("must be greater than or equal to %s" % value)
        self.rules = rules

        if 'message' in constraint:
            self.message = constraint['message']
        elif messages:
            self.message = ', '.join(messages)

    def test(self, value):
        """Run the constraint logic on the given value."""
        return all(rule(value) for rule in self.rules)


class StaticConstraint(Constraint):

    """Constraint that is evaluated to true or false.

    Syntax:

    - check: false
      message: This will NEVER work
    - check:
        if:
          and:
          - value: inputs://one
          - value: inputs://two
      message: If you specify "one", then you also need "two"

    Note: the evaluation of the "if:" construct above happens outside of the
    constraint as it requires the deployment. The constraint class just
    determines true/false. See deployment.py for the evaluation code.
    """

    required_keys = ['check']
    allowed_keys = ['check', 'message']

    def test(self, value):
        """Run the constraint logic on the given value."""
        return self.constraint.get('check')

# Auto-populate this global with all constraint classes defined in this module.
CONSTRAINT_CLASSES = [k for n, k in inspect.getmembers(sys.modules[__name__],
                                                       inspect.isclass)
                      if issubclass(k, Constraint)]
