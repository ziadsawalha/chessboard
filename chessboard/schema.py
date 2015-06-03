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

"""Schema definition and validation utils for the Checkmatefile structure."""

import logging
import os
import re

import six
import voluptuous as volup
import yaml
from yaml import parser
from yaml import scanner

LOG = logging.getLogger(__name__)


###########################
# Constants and utilities #
###########################

INTERFACE_TYPES = [
    'dns_tcp',
    'dns_udp',
    'ftp',
    'gluster',
    'host',
    'http',
    'https',
    'imaps',
    'imapv2',
    'imapv3',
    'imapv4',
    'ldap',
    'ldaps',
    'linux',
    'memcache',
    'mongodb',
    'mssql',
    'mysql',
    'new-relic',
    'nfs',
    'php',
    'pop3',
    'pop3s',
    'postgres',
    'proxy',
    'rackspace-cloud-monitoring',
    'rdp',
    'redis',
    'sftp',
    'smtp',
    'ssh',
    'tcp',
    'tcp_client_first',
    'tcp_stream',
    'udp',
    'udp_stream',
    'url',
    'varnish',
    'vip',
    'windows',
]

RESOURCE_TYPES = [
    'application',
    'cache',
    'compute',
    'database',
    'database-replica',
    'directory',
    'dns',
    'object-store',
    'host',
    'key-pair',
    'logging',
    'load-balancer',
    'mail-relay',
    'web',
    'monitoring',
    'storage',
    'volume',
]


class DictOf(volup.Schema):

    """Validate that all values in a dict adhere to the supplied schema.

    This allows schemas with a dictionary structure to be defined, where there
    are specific constraints on the value, but no constraints on the key name.

    Shamelessly copied from Checkmate and modified.
    """

    def __call__(self, data):
        """Validate data against this schema."""
        if not isinstance(data, dict):
            raise volup.Invalid('value not a dict')
        errors = []
        for key, value in data.items():
            try:
                self.schema(value)
            except volup.MultipleInvalid as exc:
                # Since the key can be arbitrary, we need to include it in the
                # path so the error can be traced to a specific location.
                for each in exc.errors:
                    each.path.insert(0, key)
                errors.extend(exc.errors)
        if errors:
            raise volup.MultipleInvalid(errors)
        return data


def Coerce(type, msg=None):
    """Coerce a value to a type.

    If the type constructor throws a ValueError, the value will be marked as
    Invalid.

    Shamelessly copied from the voluptuous docs:
    https://github.com/alecthomas/voluptuous/blob/master/README.md
    """
    def f(v):
        try:
            return type(v)
        except ValueError:
            raise volup.Invalid(msg or ('expected %s' % type.__name__))
    return f


class RequireOneInvalid(volup.Invalid):

    """At least one of a required set of keys is missing from a dict."""


def RequireOne(keys):  # pylint: disable=C0103
    """Validate that at least on of the supplied keys exists on a dict."""
    def check(val):
        """Validate data against this schema."""
        if any(([k in val for k in keys])):
            return val
        raise RequireOneInvalid("one of '%s' is required" % ', '.join(keys))
    return check


def coerce_dict(existing, changed):
    """Coerce existing dict with new values without losing the reference."""
    existing.clear()
    existing.update(changed)


#
# Documentation extensions for voluptuous schema.
#
DOCS_PATH = os.path.join(os.path.dirname(__file__), 'schema_docs.yaml')

# This is the schema of the entries expected in the YAML documentation file.
DOCS_SCHEMA = volup.Schema({
    volup.Optional('type'): str,
    'fields': object,
    volup.Optional('description'): str,
    volup.Optional('docs'): str,
    volup.Optional('shorthand'): str,
})


def load_docs(schema_file):
    """Load schema documentation.

    Schema is expected to be a file object with multiple entries in the format
    defined in DOCS_SCHEMA:
        <name>: what is documented (ex. 'component')
            type: defaults to <name> if not supplied, but can also be a
                  'list(<name>)' or 'dict(<name>)'
            fields:
              <key>:
                type: the type of the field, which can also be any <name>
                description: short description of what the field is
                docs: long, markdown documentation for the field
            docs: detailed documentation in markdown
            description: short description
            shorthand: the formating for shorthand syntax if available
    """
    results = {}
    try:
        contents = yaml.safe_load(schema_file)
    except (parser.ParserError, scanner.ScannerError, ValueError) as exc:
        LOG.warning("Schema file '%s' is not valid YAML: %s", DOCS_PATH, exc)
        raise

    try:
        for key, definition in contents.items():
            DOCS_SCHEMA(definition)
            definition.setdefault('type', key)
            results[key] = definition
    except volup.MultipleInvalid as exc:
        LOG.warning("Schema file '%s' has bad data: %s", DOCS_PATH, exc)
        raise

    return results


#
# Initialize schema docs from schema_docs.yaml by default
#
def load_file(path):
    """Load docs file."""
    try:
        return load_docs(open(path, 'r'))
    except IOError:
        LOG.warning("Schema file '%s' is missing or not readable", path)
        raise

DOCS = load_file(DOCS_PATH)


def parse_type_name(type_string):
    """Parse the string name of a type and return type and subtype.

    Supports `dict(<subtype>)` and `list(<subtype>)` without recursion (i.e.
    you cannot supply `dict(dict(<subtype>))`).

    .. doctest::

        >>> parse_type_name('string')
        ('string', None)
        >>> parse_type_name('list(int)')
        ('list', 'int')
        >>> parse_type_name('dict(option)')
        ('dict', 'option')
        >>> parse_type_name('else(option)')
        ('else(option)', None)

    :returns: tuple of two schema type names (type, subtype)
    """
    parsed = re.match(r'(?P<fxn>(dict|list))\((?P<type>\w*)\)', type_string)
    if parsed:
        return parsed.group('fxn'), parsed.group('type')
    return type_string, None


class DocumentedSchema(volup.Schema):

    """Voluptuous Schema with documentation.

    This class extends voluptuous.Schema to suppoer the following:

    - store a 'name' with the schema
    - decorate validation errors with documentation based on the name

    Usage:

    a) To create a voluptuous.Schema that has a name associated with it:

        DocumentedSchema(Relation(), name='relation')

    b) To create a voluptuous.Schema that can be looked up by name:

        schema = DocumentedSchema(Relation(), name='relation').register()

    c) To output verbose messages:

        schema = DocumentedSchema(Relation(), name='relation').register()
        try:
            schema(bad_data)
        except voluptuous.MultipleInvalid as exc:
            for error in exc.errors:
                if hasattr(error, 'docs'):
                    print error.docs

    """

    registered_types = {}

    def __init__(self, schema, required=False, extra=volup.PREVENT_EXTRA,
                 name=None):
        """Extend voluptuous.Schema __init__ with `name`."""
        self.name = name
        super(DocumentedSchema, self).__init__(schema, required=required,
                                               extra=extra)

    def __call__(self, data):
        """Validate data against this schema."""
        try:
            return super(DocumentedSchema, self).__call__(data)
        except volup.MultipleInvalid as exc:
            self.decorate_errors(exc.errors)
            raise

    def find_schema(self, error_path, schema=None):
        """Find schema entry from error.path.

        This function will navigate the schema based on the voluptuous error
        path supplied. It will start from the current schema as a root (unless
        an override is supplied in the `schema` parameter) and iterate down the
        list of valid/allowed fields and return the last valid schema in the
        path.

        :returns: schema
        """
        if not schema:
            schema = self

        for node in error_path:
            try:
                if isinstance(schema, DocumentedSchema):
                    schema = schema.get_field_schema(node)
                elif isinstance(schema, DictOf):
                    schema = schema.schema
                elif isinstance(schema, list):
                    schema = schema[0]
                else:
                    raise TypeError("Type '%s' not supported." % type(schema))
            except KeyError:
                return schema
        return schema

    def decorate_errors(self, errors):
        """Add `docs` key from schema docs to each error.

        This decorates an exception's `.errors` collection with docs for each
        error if the docs exist. If no docs exist for a specific path (KeyError
        when search in DOCS), then we won't raise a new error.
        """
        for error in errors:
            if hasattr(error, 'docs'):
                continue
            try:
                definition = self.find_schema(error.path)
                if hasattr(definition, 'name'):
                    error.docs = DOCS[definition.name]
            except KeyError:
                break  # No docs exist for this error's path

    def register(self):
        """Add schema to mapping with associated type name.

        Allows chaining by returning self on success. For example:

            label_schema = DocumentedSchema(str, name="label").register()

        :raises: KeyError if registering over a pre-registered class
        :returns: self to allow chaining
        """
        if (self.name in self.registered_types and
                self is not self.registered_types[self.name]):
            raise KeyError(self.name)
        self.registered_types[self.name] = self
        return self

    def __repr__(self):
        """Show `name` in repr."""
        return '<%s %s>' % (self.__class__.__name__, self.name)

    def get_field_schema(self, name):
        """Return the schema defined for a field under this schema.

        :param name: the name of a field defined under this schema.

        :returns: a valid voluptuous.Schema (including types such as `dict` and
            `list`) as defined for this field.

        :raises:
            KeyError: if docs or schema are missing or not registered.
        """
        field = DOCS[self.name]['fields'][name]
        type_name, subtype_name = parse_type_name(field.get('type', 'string'))
        if subtype_name:
            if type_name == 'dict':
                return DictOf(self.registered_types[subtype_name])
            elif type_name == 'list':
                return [self.registered_types[subtype_name]]
            else:
                raise ValueError("Type '%s' does not support subtypes. "
                                 "Expected 'dict' or 'list'." % type_name)
        return self.registered_types[type_name]


######################
# Schema definitions #
######################


#: Schema for a member of
#:  `blueprint` -> `services` -> SERVICE_NAME -> `relations`
RELATION_LONG_SCHEMA = volup.Schema({
    # TODO(larsbutler): This is the "long form" of relation schema.
    # We need to also define the short form.
    # Short form is just a single entry in a dict in the following format:
    #   {<service>: <interface>} or {<service>: <interface>#<tag>}
    #
    #   where:
    #       - <service> is the `service` name and expands to `service` in the
    #         long form
    #       - <interface> is a valid interface type and expands to `interface`
    #         in the long form
    #       - <tag> is an arbitrary label on the interface of another service.
    #         we use tag in the case where another service defines multiple
    #         interfaces with the same type; this tag is used to differentiate
    #         them. Expands to `connect-from` in the long form.
    #         TODO(larsbutler): Why is it `connect-from`, and not `connect-to`?
    #         It seems backwards.
    volup.Required('service'): str,
    volup.Required('interface'): volup.Any('*', *INTERFACE_TYPES),

    # FIXME(larsbutler): Need a better description for all of these.
    # "source connection point name"
    volup.Optional('connect-from'): str,
    # The combination of resource type, interface, and tag is called a
    # "target connection point name"
    volup.Optional('connect-to'): str,
    # FIXME(larsbutler): Need more detailed schema for these:
    volup.Optional('constraints'): list,
    volup.Optional('attributes'): dict,
})


def Relation(msg=None, coerce=False):
    """Validate a relation (coerce shorthand to long form).

    Supported formats:

    -   {service: interface}
    -   {service: interface#tag}
    -   or long form (see RELATION_LONG_SCHEMA)
    """
    def check(entry):
        if not isinstance(entry, dict):
            raise volup.Invalid('not a valid relation entry')
        if len(entry) == 1:
            [(key, value)] = entry.items()
            if not isinstance(value, six.string_types):
                raise volup.Invalid('not a valid relation value')

            # shorthand (type: interface and optional connection source)
            if '#' in value:
                interface, hashtag = value.split('#')[0:2]
                changed = {
                    'service': key,
                    'interface': interface,
                    'connect-from': hashtag,
                }
            else:
                changed = {'service': key, 'interface': value}
            if coerce:
                coerce_dict(entry, changed)
            else:
                entry = changed
        return RELATION_LONG_SCHEMA(entry)
    return check
RELATION_SCHEMA = DocumentedSchema(Relation(), name='relation').register()

# TODO(larsbutler): This is the "long form" of constraint structure.
# We need to define the "short form" which is:
#   {<setting>: <value>}, where <setting> is the `setting` name and <value> is
#   the `value`.
CONSTRAINT_SCHEMA = DocumentedSchema({
    volup.Required('setting'): str,
    # FIXME(larsbutler): Per a conversation with @ziadsawalha, `value` is
    # supposed to be required, but it's not. I've seen examples of "valid"
    # Checkmatefiles where this is missing.
    volup.Optional('value'): volup.Any(bool, float, int, str),
    volup.Optional('message'): str,
    # Used to apply the constraint to a specific provider
    volup.Optional('provider'): str,
    # Optional constraint operators:
    volup.Optional('greater-than'): Coerce(str),
    volup.Optional('less-than'): Coerce(str),
    volup.Optional('greater-than-or-equal-to'): Coerce(str),
    volup.Optional('less-than-or-equal-to'): Coerce(str),
    volup.Optional('min-length'): int,
    volup.Optional('max-length'): int,
    volup.Optional('allowed-chars'): Coerce(str),
    volup.Optional('required-chars'): Coerce(str),
    volup.Optional('in'): list,
    volup.Optional('protocols'): list,
    volup.Optional('regex'): str,
}, name="constraint").register()

# These are the values that can be supplied under `component` in a service:
COMPONENT_SELECTOR_SCHEMA_FIELDS = volup.Schema({
    # Explicitly selecting a component by the provider-supplied `id`
    # Ex. `id: rsCloudLB` explicitely selects a Rackspace Cloud Load Balancer
    volup.Optional('id'): volup.All(str, volup.Length(min=3, max=32)),
    # Selecting a component by the well-known application name (ex. wordpress)
    volup.Optional('name'): str,
    # Selecting a component that supports a well-known interface (this also
    # requires resource_type)
    volup.Optional('interface'): volup.Any('*', *INTERFACE_TYPES),
    # Selecting a component by its type (ex. database)
    volup.Optional('resource_type'): volup.Any('*', *RESOURCE_TYPES),
    # Selecting a component by role (ex. slave vs, master)
    volup.Optional('role'): str,
    # Selecting a component with constraints (ex. os == 'CentOS 6.5')
    volup.Optional('constraints'): [dict],
})
COMPONENT_SELECTOR_SCHEMA = volup.All(
    volup.Schema(COMPONENT_SELECTOR_SCHEMA_FIELDS),
    # At least one of id, name, or resource_type is required. Without one of
    # these, the conditions will be too ambiguous to select a suitable
    # component. See individual field comments above on what each of these
    # means.
    # TODO(zns): if resource_type is supplied, then we should also require
    # interface
    RequireOne(['id', 'name', 'resource_type'])
)

#: Schema for a member of `blueprint` -> `services`
SERVICE_SCHEMA = DocumentedSchema({
    volup.Required('component'): COMPONENT_SELECTOR_SCHEMA,
    # TODO(larsbutler): need to be more specific
    volup.Optional('relations'): [RELATION_SCHEMA],
    volup.Optional('constraints'): [CONSTRAINT_SCHEMA],
    volup.Optional('display-name'): str,
}, name='service').register()

#: Schema for `blueprint`
BLUEPRINT_SCHEMA = DocumentedSchema({
    volup.Optional('id'): str,
    volup.Optional('name'): str,
    volup.Required('services'): DictOf(SERVICE_SCHEMA),
    volup.Optional('version'): str,
    volup.Optional('description'): str,
    # The `source` field would (most likely) never be written by a blueprint
    # author directly.
    # These are only used if a blueprint is pulled from a remote source, and it
    # purely metadata. These attributes do not affect the behavior of the
    # blueprint.
    # If we are working in the checkmate UI, for example, and we pull in a
    # Checkmatefile from a remote repo, these fields will get populated. These
    # are useful, then, if copies are made/modified from this Checkmatefile so
    # we can trace the origin.
    volup.Optional('source'): {
        volup.Required('repo-url'): str,
        volup.Required('sha'): str,
        # master, another branch name, tag, etc.
        volup.Optional('ref'): str,
    },
}, name='blueprint').register()

#: Top level Checkmatefile schema
CHECKMATEFILE_SCHEMA = DocumentedSchema({
    volup.Required('blueprint'): BLUEPRINT_SCHEMA,
    # TODO(larsbutler): Add the other sections, like `environment` and `inputs`
    volup.Optional('environment'): object,
    volup.Optional('inputs'): object,
    volup.Optional('flavors'): object,
    volup.Optional('include'): object,
}, name='checkmateFile').register()


def generate_docs(docs=None):
    """Return markdown page with all schema documentation.

    :keyword docs: supply a documentation dict. Default reverts to `DOCS`.
    """
    if docs is None:
        docs = DOCS
    toc = []
    body = []
    for doc, content in docs.items():
        if 'docs' in content:
            # Prepare an entry with hyperlink to content
            toc.append('[%s](#%s)' % (doc, doc))
            # Prepare anchor with content header
            anchor = '#### <a name="%s"></a>%s' % (doc, doc)
            body.append('%s\n\n%s' % (anchor, content['docs']))
    return """\
<!--Content autogenerated from schema_docs.yaml-->
# Glossary

%s  \


%s
""" % ('  \n'.join(toc), '\n\n'.join(body))
