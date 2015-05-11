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

"""Checkmatefile parsing utilities.

Uses validation in :mod:`chessboard.schema` to validate inputs.
"""

import six
import voluptuous as volup
import yaml

from chessboard import schema as cb_schema


class MultiValidationError(Exception):

    """Basically a re-imagining of a `voluptuous.MultipleInvalid` error.

    Reformats multiple errors messages for easy debugging of invalid
    Checkmatefiles.
    """

    def __init__(self, errors):
        """MultiValidationError constructor.

        :param errors:
            List of `voluptuous.Invalid` or `voluptuous.MultipleInvalid`
            exception objects.
        """
        self.errors = errors
        self.message = self._generate_message()

    def __str__(self):
        """Just return the pre-computed message.

        See :meth:`_generate_message`.
        """
        return self.message

    def __repr__(self):
        """Simple representation of the exception, with the full message."""
        indented_message = '\n'.join(
            sorted('\t' + x for x in self.message.split('\n'))
        )
        return (
            '%(cls_name)s(\n%(message)s\n)'
            % dict(cls_name=self.__class__.__name__, message=indented_message)
        )

    def _generate_message(self):
        """Reformat `path` attributes of each `error` and create a new message.

        Join `path` attributes together in a more readable way, to enable easy
        debugging of an invalid Checkmatefile.

        :returns:
            Reformatted error paths and messages, as a multi-line string.
        """
        reformatted_paths = (
            ''.join(
                "[%s]" % str(x)
                # If it's not a string, don't put quotes around it. We do this,
                # for example, when the value is an int, in the case of a list
                # index.
                if isinstance(x, six.integer_types)
                # Otherwise, assume the path node is a string and put quotes
                # around the key name, as if we were drilling down into a
                # nested dict.
                else "['%s']" % str(x)
                for x in error.path
            )
            for error in self.errors
        )

        messages = (error.msg for error in self.errors)
        # combine each path with its message:
        zipped = zip(reformatted_paths, messages)
        combined_messages = (
            '%(path)s: %(messages)s' % dict(path=path, messages=message)
            for path, message in zipped
        )

        return '\n'.join(sorted(combined_messages))


def load(fileobj, schema=cb_schema.CHECKMATEFILE_SCHEMA):
    """Load and validate a Checkmatefile.

    Read the Checkmatefile and validate the syntax of the file per the
    defined Checkmatefile schema, then return the Checkmatefile contents as a
    `dict`.

    :param fileobj:
        A file-like with the contents of the Checkmatefile, in YAML format.
    :param schema:
        A callable into which the loaded Checkmatefile contents are passed (as
        a dict, not as raw YAML). The callable should return the validated
        contents, or raise exceptions.

    :returns:
        Checkmatefile contents as a `dict`.
    """
    contents = fileobj.read()
    data = yaml.safe_load(contents)

    # Validate the contents per the checkmatefile schema
    try:
        # NOTE(larsbutler): Voluptuous schema validators can mutate data, so we
        # need to return whatever the schema validator gives us.
        return schema(data)
    except volup.MultipleInvalid as exc:
        raise MultiValidationError(exc.errors)
