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

"""Code Deployment for Humans.

Usage:
  app exposes <type_spec> [--default-port <port>] [--use-free-port] \
[--set-env <env-spec>] [--name <name>]
  app provides <type_spec> [--set-env <env-spec>] [--options <opt-spec>] \
[--version <version-spec>] [--packages <package>]
  app (requires|supports) <type_spec> [--set-env <env-spec>] \
[--options <opt-spec>] [--version <version-spec>] [--packages <package>]
  app define [--start-command=<start>]
  app deploy [--providers=<providers>] ...
  app scale-out <deployment> [--force] [--count <add_spec>]
  app list deployments
  app destroy <deployment> [--force]
  app -h | --help
  app version

Options:
  -h --help                 Show this screen.
  --version <version-spec>  Show version.
  --default-port <port>     Port to try to start up on [default: 8080].
  --use-free-port           Find a free port if default not available.
  --set-env                 Pairs of vars to set.
  --options <opt-spec>      Pairs of values to supply.
  --start-command <start>   How to start up our app.
  --name <name>             Name to use for the component [default: app]
"""

from __future__ import print_function

import re

from docopt import docopt
import yaml


def version(options):
    """Print version."""
    print("0.0.0")


def exposes(options):
    """Add exposes."""
    blueprint = load_file(options)
    app = get_app(options, blueprint)
    provides_list = app.setdefault('provides', [])
    type_spec = parse_spec(options['<type_spec>'])
    resource_type = type_spec.get('type')
    interface = type_spec.get('interface')
    tag = type_spec.get('tag')
    matches = find_connection_points(provides_list, interface=interface,
                                     resource_type=resource_type, tag=tag)
    if not matches:
        if resource_type and resource_type != '*':
            new = {resource_type: interface}
        else:
            new = {'interface': interface}
        if tag:
            new['name'] = tag
        if type_spec['port']:
            if type_spec['free']:
                new['port'] = str(type_spec['port']) + '?'
            else:
                new['port'] = type_spec['port']
        provides_list.append(new)
        matches.append(new)
    for entry in matches:
        entry['exposed'] = True
    print(blueprint)
    return matches


def provides(options):
    """Add provides."""
    blueprint = load_file(options)
    app = get_app(options, blueprint)
    provide_list = app.setdefault('provides', [])
    type_spec = parse_spec(options['<type_spec>'])
    resource_type = type_spec.get('type')
    interface = type_spec.get('interface')
    tag = type_spec.get('tag')
    matches = find_connection_points(provide_list, interface=interface,
                                     resource_type=resource_type, tag=tag)
    if not matches:
        if resource_type and resource_type != '*':
            new = {resource_type: interface}
        else:
            new = {'interface': interface}
        if tag:
            new['name'] = tag
        provide_list.append(new)
        matches.append(new)
    for entry in matches:
        if type_spec['port']:
            if type_spec['free']:
                entry['port'] = str(type_spec['port']) + '?'
            else:
                entry['port'] = type_spec['port']
    print(blueprint)
    return matches


def requires(options, key='requires'):
    """Add requires."""
    blueprint = load_file(options)
    app = get_app(options, blueprint)
    req_list = app.setdefault(key, [])
    type_spec = parse_spec(options['<type_spec>'])
    resource_type = type_spec.get('type')
    interface = type_spec.get('interface')
    tag = type_spec.get('tag')
    matches = find_connection_points(req_list, interface=interface,
                                     resource_type=resource_type, tag=tag)
    if not matches:
        if resource_type and resource_type != '*':
            new = {resource_type: interface}
        else:
            new = {'interface': interface}
        if tag:
            new['name'] = tag
        req_list.append(new)
        matches.append(new)
    print(blueprint)
    return matches


def supports(options):
    """Add supports."""
    return requires(options, key='supports')


def find_connection_points(points, tag=None, interface=None,
                           resource_type=None):
    """Return the connection points that match supplied filters."""
    matches = []
    if resource_type == '*':
        resource_type = None
    if interface == '*':
        interface = None
    for entry in points:
        entry_type = entry.get('resource_type')
        entry_interface = entry.get('interface')
        if resource_type in entry:
            if resource_type in entry:
                raise ValueError("resource_type specified in short and long "
                                 "form")
            entry_type, entry_interface = resource_type, entry[resource_type]
        if resource_type and entry_type != resource_type:
            continue  # mismatch
        if interface and entry_interface != interface:
            continue  # mismatch
        if tag and entry.get('name') != tag:
            continue  # mismatch
        matches.append(entry)
    return matches


def get_app(options, blueprint):
    """Get component from blueprint."""
    return blueprint['components'].setdefault(options['--name'], {})


def parse_spec(type_spec):
    """Parse string spec into full dict.

    Spec format is:

    <resource_type>:<interface>[<port>?]#<name>

    Examples:

    # A mysql database
    database:mysql

    # An http application that defaults to port 8080
    application:http[8080]

    # An http application that defaults to port 8080 but falls back to any open
    # port and is tagged with name 'admin'
    application:http[8081?]#admin
    """
    exp = re.match(
        r"""(?P<type>\w+)"""  # capture the resource_type
        r""":(?P<interface>\w+)"""  # capture the interface after the colon
        r"""(\[(?P<port>\d+)"""  # optional port number
        r"""(?P<free>\?)?\])?"""  # '?' after port means find a free port
        r"""(\#(?P<tag>\w*))?""",  # optional tag
        type_spec)
    parsed = exp.groupdict()
    parsed['free'] = parsed['free'] == '?'
    return parsed


def load_file(options):
    """Load blueprint file."""
    path = options.get('file', 'blueprint.yaml')
    try:
        with open(path, 'r') as handle:
            return yaml.safe_load(handle)
    except IOError:
        return {'components': {}}


def save_file(options, contents):
    """Save blueprint file."""
    path = options.get('file', 'blueprint.yaml')
    with open(path, 'w') as handle:
        yaml.dump(contents, stream=handle, dumper=yaml.SafeDumper)


def main(argv):
    """Do it!"""
    options = docopt(__doc__, argv=argv)
    results = None
    for key, value in options.items():
        if value and key in globals():
            fxn = globals().get(key)
            results = fxn(options)
            break
    else:
        print(__doc__)
    return results


def test_parse_spec():
    """Test parse_spec()."""
    expected = [
        {
            'interface': 'http',
            'tag': 'name',
            'type': 'database',
            'port': '8080',
            'free': True,
        }, {
            'interface': 'http',
            'tag': 'name',
            'type': 'database',
            'port': '8080',
            'free': False,
        }, {
            'interface': 'http',
            'tag': None,
            'type': 'database',
            'port': '8080',
            'free': True,
        }, {
            'interface': 'http',
            'tag': 'name',
            'type': 'database',
            'port': None,
            'free': False,
        }, {
            'interface': 'http',
            'tag': None,
            'type': 'database',
            'port': None,
            'free': False,
        }
    ]
    assert parse_spec('database:http[8080?]#name') == expected[0]
    assert parse_spec('database:http[8080]#name') == expected[1]
    assert parse_spec('database:http[8080?]') == expected[2]
    assert parse_spec('database:http#name') == expected[3]
    assert parse_spec('database:http') == expected[4]


def test_main():
    """Test main()."""
    expected = [
        [{'application': 'http', 'exposed': True}],
        [{'application': 'http', 'name': 'magento', 'port': '8080?'}],
        [{'cache': 'redis', 'name': 'objects'}],
        [{'name': 'users', 'database': 'mysql'}],
    ]
    assert main(['exposes', 'application:http']) == expected[0]
    assert main(['provides', 'application:http[8080?]#magento']) == expected[1]
    assert main(['supports', 'cache:redis#objects']) == expected[2]
    assert main(['requires', 'database:mysql[8080]#users']) == expected[3]


if __name__ == "__main__":
    test_parse_spec()
    test_main()
