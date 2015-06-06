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

"""Generate valid Python code from a string.

Inspired by the PyPI codegen package:
https://github.com/andreif/codegen/blob/master/codegen.py
"""

from ast import literal_eval
from ast import NodeVisitor
from ast import parse


def _params_as_dict(expression):
    """Add all but function name and enclosing parentheses to a new dict."""
    return literal_eval('{%s}' % ''.join(expression[2:-1]))


def kwargs_from_string(parse_string):
    """Parse the function name and kwargs from a string.

    :param parse_string: the string purported to have valid Python code
    """
    if not parse_string:
        return None, {}
    generator = CodeGenerator()
    generator.visit(parse(parse_string))
    return (generator.kwargs[0], _params_as_dict(generator.kwargs))


class CodeGenerator(NodeVisitor):

    """Build an Abstract Syntax Tree from a parsed string.

    Initiated by passing a string into the inherited `visit` method
    """

    def __init__(self):
        """Initialize kwars attribute."""
        self.kwargs = []

    def visit_Name(self, node):
        """Receive Node Name."""
        self.kwargs.append(node.id)

    def visit_Call(self, node):
        """Receive Call Signature."""
        need_comma = []

        def append_comma():
            """Append COmma if needed."""
            if need_comma:
                self.kwargs.append(', ')
            else:
                need_comma.append(True)
        self.visit(node.func)
        self.kwargs.append('(')
        for arg in node.args:
            append_comma()
            self.visit(arg)
        for keyword in node.keywords:
            append_comma()
            self.kwargs.append("'")
            self.kwargs.append(keyword.arg)
            self.kwargs.append("': ")
            self.visit(keyword.value)
        self.kwargs.append(')')

    def visit_Str(self, node):
        """Receive String."""
        self.kwargs.append(repr(node.s))

    def visit_Num(self, node):
        """Receive Number."""
        self.kwargs.append(repr(node.n))

    def visit_NameConstant(self, node):
        """Receive Named Constant (ex. None in Python 3)."""
        self.kwargs.append(repr(node.value))

    def sequence_visit(left, right):
        """Receive Sequence."""
        def visit(self, node):
            """Visit Sequence."""
            self.kwargs.append(left)
            for index, item in enumerate(node.elts):
                if index:
                    self.kwargs.append(', ')
                self.visit(item)
            self.kwargs.append(right)
        return visit

    visit_List = sequence_visit('[', ']')
    visit_Set = sequence_visit('{', '}')
