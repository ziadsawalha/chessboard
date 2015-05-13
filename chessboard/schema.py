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

import six
import voluptuous as volup

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


def DictOf(schema):
    """Validate that all values in a dict adhere to the supplied schema.

    This allows schemas with a dictionary structure to be defined, where there
    are specific constraints on the value, but no constraints on the key name.

    Shamelessly copied from Checkmate and modified.
    """
    def check(entry):
        if not isinstance(entry, dict):
            raise volup.Invalid('value not a dict')
        errors = []
        for key, value in entry.items():
            try:
                schema(value)
            except volup.MultipleInvalid as exc:
                # Since the key can be arbitrary, we need to include it in the
                # path so the error can be traced to a specific location.
                for each in exc.errors:
                    each.path.insert(0, key)
                errors.extend(exc.errors)
        if errors:
            raise volup.MultipleInvalid(errors)
        return entry
    return check


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


def RequireOne(keys):
    """Validate that at least on of the supplied keys exists on a dict."""
    def check(val):
        if any(([k in val for k in keys])):
            return
        raise RequireOneInvalid("one of '%s' is required" % ', '.join(keys))
    return check


def coerce_dict(existing, changed):
    """Coerce existing dict with new values without losing the reference."""
    existing.clear()
    existing.update(changed)


def schema_from_list(keys_list):
    """Generate a schema from a list of keys."""
    return Schema(dict((key, object) for key in keys_list))

######################
# Schema definitions #
######################


#: Schema for a member of
#:  `blueprint` -> `services` -> SERVICE_NAME -> `relations`
RELATION_SCHEMA = volup.Schema({
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
    -   or long form (see RELATION_SCHEMA)
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
        return RELATION_SCHEMA(entry)
    return check


# TODO(larsbutler): This is the "long form" of constraint structure.
# We need to define the "short form" which is:
#   {<setting>: <value>}, where <setting> is the `setting` name and <value> is
#   the `value`.
CONSTRAINT_SCHEMA = volup.Schema({
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
})

# These are the values that can be supplied under `component` in a service:
COMPONENT_SELECTOR_SCHEMA_FIELDS = volup.Schema({
    # Explicitely selecting a component by the provider-supplied `id`
    # Ex. `id: rsCloudLB` explicitely selects a Rackspac Cloud Load Balancer
    volup.Optional('id'): volup.All(str, volup.Length(min=3, max=32)),
    # Selecting a component by the well-known application name (ex. wordpress)
    volup.Optional('name'): str,
    # Selecting a component that supports a well-known interface
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
SERVICE_SCHEMA = volup.Schema({
    volup.Required('component'): COMPONENT_SELECTOR_SCHEMA,
    # TODO(larsbutler): need to be more specific
    volup.Optional('relations'): [Relation()],
    volup.Optional('constraints'): [CONSTRAINT_SCHEMA],
    volup.Optional('display-name'): str,
})


#: Schema for `blueprint`
BLUEPRINT_SCHEMA = volup.Schema({
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
})

#: Top level Checkmatefile schema
CHECKMATEFILE_SCHEMA = volup.Schema({
    volup.Required('blueprint'): BLUEPRINT_SCHEMA,
    # TODO(larsbutler): Add the other sections, like `environment` and `inputs`
    volup.Optional('environment'): object,
    volup.Optional('inputs'): object,
    volup.Optional('flavors'): object,
    volup.Optional('include'): object,
})
