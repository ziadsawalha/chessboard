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

"""General utility functions."""

import collections
import sys
import time
import uuid

import arrow
import six
import six.moves.urllib.parse as urlparse
import yaml
from yaml import events


def parse_iso_time_string(time_string):
    """Convert an ISO date/time to Waldo format."""
    date_parser = arrow.parser.DateTimeParser()
    return get_time_string(date_parser.parse_iso(time_string).timetuple())


def import_class(import_str):
    """Return a class from a string including module and class."""
    mod_str, _, class_str = import_str.rpartition('.')
    __import__(mod_str)
    return getattr(sys.modules[mod_str], class_str)


def import_object(import_str, *args, **kw):
    """Return an object including a module or module and class."""
    try:
        __import__(import_str)
        return sys.modules[import_str]
    except ImportError:
        cls = import_class(import_str)
        return cls(*args, **kw)


def resolve_yaml_external_refs(document):
    """Parse YAML and resolves any external references.

    :param document: a stream object
    :returns: an iterable
    """
    anchors = []
    for event in yaml.parse(document, Loader=yaml.SafeLoader):
        if isinstance(event, events.AliasEvent):
            if event.anchor not in anchors:
                # Swap out local reference for external reference
                new_ref = u'ref://%s' % event.anchor
                event = events.ScalarEvent(anchor=None, tag=None,
                                           implicit=(True, False),
                                           value=new_ref)
        if hasattr(event, 'anchor') and event.anchor:
            anchors.append(event.anchor)

        yield event


def yaml_to_dict(data):
    """Parse YAML to a dict using checkmate extensions."""
    return yaml.safe_load(yaml.emit(resolve_yaml_external_refs(data),
                                    Dumper=yaml.SafeDumper))


def dict_to_yaml(data):
    """Parse dict to YAML using checkmate extensions."""
    return yaml.safe_dump(data, default_flow_style=False)


def escape_yaml_simple_string(text):
    """Render a simple string as valid YAML string escaping where necessary.

    Note: Skips formatting if value supplied is not a string or is a multi-line
          string and just returns the value unmodified
    """
    # yaml seems to append \n or \n...\n in certain circumstances
    if text is None or (isinstance(text, six.string_types) and
                        '\n' not in text):
        return yaml.safe_dump(text).strip('\n').strip('...').strip('\n')
    else:
        return text


def try_int(the_str):
    """Try converting string to int. Return the string on failure."""
    try:
        return int(the_str)
    except ValueError:
        return the_str


def generate_id():
    """Generate a unique ID for an object."""
    return uuid.uuid4().hex[0:6]


def get_time_string(time_gmt=None):
    """Return time in Checkmate canonical time string format.

    Changing this function will change all times that checkmate uses in
    blueprints, deployments, etc...
    """
    # TODO(Pablo): We should assert that time_gmt is a time.struct_time
    return time.strftime("%Y-%m-%d %H:%M:%S +0000", time_gmt or time.gmtime())


def is_uuid(value):
    """Test that a provided value is a valid uuid."""
    if not value:
        return False
    if isinstance(value, uuid.UUID):
        return True
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def write_path(target, path, value):
    """Write a value into a dict building any intermediate keys."""
    parts = path.split('/')
    current = target
    for part in parts[:-1]:
        if part not in current:
            current[part] = current = {}
        else:
            current = current[part]
    current[parts[-1]] = value


def read_path(source, path):
    """Read a value from a dict supporting a path as a key."""
    parts = path.strip('/').split('/')
    current = source
    for part in parts[:-1]:
        if part not in current:
            return
        current = current[part]
        if not isinstance(current, collections.MutableMapping):
            return
    return current.get(parts[-1])


def path_exists(source, path):
    """Check a dict for the existence of a path as a key."""
    if path == '/' and isinstance(source, dict):
        return True
    parts = path.strip('/').split('/')
    if not parts:
        return False
    current = source
    for part in parts:
        if not isinstance(current, collections.MutableMapping):
            return False
        if part not in current:
            return False
        current = current[part]
    return True


def hide_url_password(url):
    """Detect a password part of a URL and replaces it with *****."""
    try:
        parsed = urlparse.urlsplit(url)
        if parsed.password:
            return url.replace(':%s@' % parsed.password, ':*****@')
    except StandardError:
        pass
    return url
