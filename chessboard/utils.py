# pylint: disable=C0302,E1101
# Copyright (c) 2011-2015 Rackspace US, Inc.
# All Rights Reserved.
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

"""General utility functions.

- handling content conversion (yaml/json)
"""

import base64
import collections
import copy
import filecmp
import inspect
import itertools
import json
import logging.config
import os
import Queue
import re
import shlex
import shutil
import string
import struct
import subprocess as subprc
import sys
import time
import traceback as traceback_module
import uuid

import arrow
from Crypto.Random import random
import eventlet
from eventlet.green import threading
import six.moves.urllib.parse as urlparse
import yaml
from yaml import composer
from yaml import events
from yaml import parser
from yaml import scanner

from chessboard import codegen
from chessboard import exceptions as cmexc


LOG = logging.getLogger(__name__)
DEFAULT_SENSITIVE_KEYS = [
    'credentials',
    'apikey',
    'error-traceback',
    'error-string',
    re.compile("(?:(?:auth)|(?:api))?[-_ ]?token$"),
    re.compile("priv(?:ate)?[-_ ]?key$"),
    re.compile('password$'),
    re.compile('^password'),
]


def parse_iso_time_string(time_string):
    """Convert an ISO date/time to Waldo format."""
    date_parser = arrow.parser.DateTimeParser()
    return get_time_string(date_parser.parse_iso(time_string).timetuple())


def match_celery_logging(logger):
    """Match celery log level."""
    if logger.level < int(os.environ.get('CELERY_LOG_LEVEL', logger.level)):
        logger.setLevel(int(os.environ.get('CELERY_LOG_LEVEL')))


def pytb_lastline(excinfo=None):
    """Return the actual last line of the (current) traceback.

    To provide exc_info, rather than allowing this function
    to read the stack automatically, this function may be called like so:
        ll = pytb_lastline(sys.exc_info())
    OR
        try:
            1/0
        except Exception as err:
            ll = pytb_lastline(err)
    """
    # TODO(samstav): Add this to airbrake-python utils
    lines = None
    if excinfo:
        if isinstance(excinfo, Exception):
            kls = getattr(excinfo, '__class__', '')
            if kls:
                kls = str(getattr(kls, '__name__', ''))
                kls = ("%s: " % kls) if kls else ''
            lines = [kls + str(excinfo)]
        else:
            try:
                lines = traceback_module.format_exception(*excinfo)
                lines = "\n".join(lines).split('\n')
            except (TypeError, AttributeError) as err:
                LOG.error("Bad argument %s passed to pytb_lastline()."
                          "Should be sys.exc_info() or None.", excinfo,
                          exc_info=err)
    if not lines:
        lines = traceback_module.format_exc().split('\n')
    # remove Falsy values and the word "None"
    lines = [line.strip() for line in lines
             if line.strip() and line.strip() != 'None']
    if lines:
        return lines[-1]


def scrub_data(data, conf=None, exempt=None):
    """Remove password and conf values from dict.

    :param data:    A dict or iterable of results to sanitize.
    :param config:  A dict (optional) of config values to sanitize
                    against in addition to the common keys.
    :param exempt:  An iterable of strings which qualify as exempt from
                    sanitization. Matches must be exact. Be careful.
    Santitize results and remove potentially sensitive data.
    Iterates through results and removes any values that match
    keys found in either `config` or `blacklist`. Returns
    sanitized results dict.
    """
    secrets = {'password', 'passphrase', 'token', 'key', 'user', 'secret'}
    if exempt and not isinstance(exempt, list):
        raise TypeError("'exempt' should be a list of exempted keys.")
    exempt = exempt or []

    if isinstance(data, dict):
        result = copy.deepcopy(data)
        for key, value in result.items():
            if not value:
                continue
            if key in exempt:
                LOG.warning("Key '%s' has been exempted from sanitization "
                            "on this call.", key)
                result[key] = scrub_data(value)
            if conf:
                if key in conf:
                    LOG.debug("Sanitized %s from dict.", key)
                    result[key] = '*****'
                    continue
            elif any(w in str(key).lower() for w in secrets):
                LOG.debug("Sanitized %s from dict.", key)
                result[key] = '*****'
            elif 'key' in str(key).lower():
                if value.startswith('-----'):
                    result[key] = '%s...%s' % (value[0:25], value[-25:])
                else:
                    result[key] = '*****'
                LOG.debug("Sanitized %s from dict.", key)
            elif any((w in str(key).lower() for w in
                      {'url', 'connection', 'backend', 'broker'})):
                result[key] = hide_url_password(value)
            else:
                result[key] = scrub_data(value)
        return result
    elif isinstance(data, tuple):
        return tuple(scrub_data(x) for x in data)
    elif isinstance(data, set):
        return {scrub_data(x) for x in data}
    elif isinstance(data, list):
        return [scrub_data(x) for x in data]
    else:
        return data


def import_class(import_str):
    """Return a class from a string including module and class."""
    mod_str, _, class_str = import_str.rpartition('.')
    try:
        __import__(mod_str)
        return getattr(sys.modules[mod_str], class_str)
    except (ImportError, ValueError, AttributeError) as exc:
        LOG.debug('Inner Exception: %s', exc)
        raise


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


def read_body(request):
    """Read request body considering content-type and returns it as a dict."""
    data = request.body
    if not data or getattr(data, 'len', -1) == 0:
        raise cmexc.CheckmateNoData("No data provided")
    content_type = request.get_header(
        'Content-type', 'application/json')
    if ';' in content_type:
        content_type = content_type.split(';')[0]

    if content_type == 'application/x-yaml':
        try:
            return yaml_to_dict(data)
        except (parser.ParserError, scanner.ScannerError) as exc:
            raise cmexc.CheckmateValidationException(
                friendly_message="Invalid YAML syntax. Check:\n%s" % exc,
                http_status=406)
        except composer.ComposerError as exc:
            raise cmexc.CheckmateValidationException(
                friendly_message="Invalid YAML structure. Check:\n%s" % exc,
                http_status=406)

    elif content_type == 'application/json':
        try:
            return json.load(data)
        except ValueError as exc:
            raise cmexc.CheckmateValidationException(
                friendly_message="Invalid JSON. %s" % exc,
                http_status=406)
    elif content_type == 'application/x-www-form-urlencoded':
        obj = request.forms.object
        if obj:
            result = json.loads(obj)
            if result:
                return result
        raise cmexc.CheckmateValidationException(
            friendly_message=("Unable to parse '%s' content. Form POSTs only "
                              "support objects in the 'object' field" %
                              content_type),
            http_status=406)
    else:
        raise cmexc.CheckmateException(
            friendly_message="Unsupported Media Type: %s" % content_type,
            http_status=415)


def yaml_to_dict(data):
    """Parse YAML to a dict using checkmate extensions."""
    return yaml.safe_load(yaml.emit(resolve_yaml_external_refs(data),
                                    Dumper=yaml.SafeDumper))


def dict_to_yaml(data):
    """Parse dict to YAML using checkmate extensions."""
    return yaml.safe_dump(data, default_flow_style=False)


def to_yaml(data):
    """Write python object to YAML.

    Includes special handling for Checkmate objects derived from MutableMapping
    """
    if isinstance(data, collections.MutableMapping) and hasattr(data, '_data'):
        return yaml.safe_dump(data._data, default_flow_style=False)
    return yaml.safe_dump(data, default_flow_style=False)


def escape_yaml_simple_string(text):
    """Render a simple string as valid YAML string escaping where necessary.

    Note: Skips formatting if value supplied is not a string or is a multi-line
          string and just returns the value unmodified
    """
    # yaml seems to append \n or \n...\n in certain circumstances
    if text is None or (isinstance(text, basestring) and '\n' not in text):
        return yaml.safe_dump(text).strip('\n').strip('...').strip('\n')
    else:
        return text


def to_json(data):
    """Write out python object to JSON.

    Includes special handling for Checkmate objects derived from MutableMapping
    """
    if isinstance(data, collections.MutableMapping) and hasattr(data, 'dumps'):
        return data.dumps(indent=4)
    return json.dumps(data, indent=4)


def try_int(the_str):
    """Try converting string to int. Return the string on failure."""
    try:
        return int(the_str)
    except ValueError:
        return the_str


def generate_id():
    """Generate a unique ID for an object."""
    return uuid.uuid4().hex[0:6]


def extract_sensitive_data(data, sensitive_keys=None):
    """Parse the dict passed in, extracting all sensitive data.

    Extracted data is placed into another dict, and returns two dicts; one
    without the sensitive data and with only the sensitive data.

    :param sensitive_keys: a list of keys considered sensitive
    """
    def key_match(key, sensitive_keys):
        """Determine whether or not key is in sensitive_keys."""
        if key in sensitive_keys:
            return True
        if key is None:
            return False
        for reg_expr in [pattern for pattern in sensitive_keys
                         if hasattr(pattern, "search")
                         and callable(getattr(pattern, "search"))]:
            if reg_expr.search(key):
                return True
        return False

    def recursive_split(data, sensitive_keys=None):
        """Return split dict or list if it contains any sensitive fields."""
        if sensitive_keys is None:  # Safer than default value
            sensitive_keys = []
        clean = None
        sensitive = None
        has_sensitive_data = False
        has_clean_data = False
        if isinstance(data, list):
            clean = []
            sensitive = []
            for value in data:
                if isinstance(value, dict):
                    clean_value, sensitive_value = recursive_split(
                        value, sensitive_keys=sensitive_keys)
                    if sensitive_value is not None:
                        sensitive.append(sensitive_value)
                        has_sensitive_data = True
                    else:
                        sensitive.append({})  # placeholder
                    if clean_value is not None:
                        clean.append(clean_value)
                        has_clean_data = True
                    else:
                        clean.append({})  # placeholder
                elif isinstance(value, list):
                    clean_value, sensitive_value = recursive_split(
                        value, sensitive_keys=sensitive_keys)
                    if sensitive_value is not None:
                        sensitive.append(sensitive_value)
                        has_sensitive_data = True
                    else:
                        sensitive.append([])  # placeholder
                    if clean_value is not None:
                        clean.append(clean_value)
                        has_clean_data = True
                    else:
                        clean.append([])
                else:
                    clean.append(value)
                    sensitive.append(None)  # placeholder
                    has_clean_data = True
        elif isinstance(data, dict):
            clean = {}
            sensitive = {}
            for key, value in data.iteritems():
                if key_match(key, sensitive_keys):
                    has_sensitive_data = True
                    sensitive[key] = value
                elif isinstance(value, dict):
                    clean_value, sensitive_value = recursive_split(
                        value, sensitive_keys=sensitive_keys)
                    if sensitive_value is not None:
                        has_sensitive_data = True
                        sensitive[key] = sensitive_value
                    if clean_value is not None:
                        has_clean_data = True
                        clean[key] = clean_value
                elif isinstance(value, list):
                    clean_value, sensitive_value = recursive_split(
                        value, sensitive_keys=sensitive_keys)
                    if sensitive_value is not None:
                        has_sensitive_data = True
                        sensitive[key] = sensitive_value
                    if clean_value is not None:
                        has_clean_data = True
                        clean[key] = clean_value
                else:
                    has_clean_data = True
                    clean[key] = value
        if has_sensitive_data:
            if has_clean_data:
                return clean, sensitive
            else:
                return None, sensitive
        else:
            if has_clean_data:
                return clean, None
            else:
                return data, None

    if sensitive_keys is None:
        sensitive_keys = DEFAULT_SENSITIVE_KEYS
    clean, sensitive = recursive_split(data, sensitive_keys=sensitive_keys)
    return clean, sensitive


def flatten(list_of_dict):
    """Convert a list of dictionary to a single dictionary.

    If 2 or more dictionaries have the same key then the data from the last
    dictionary in the list will be taken.
    """
    result = {}
    for entry in list_of_dict:
        result.update(entry)
    return result


def merge_dictionary(dst, src, extend_lists=False):
    """Recursively merge two dicts.

    Hashes at the root level are NOT overwritten

    Note: This updates dst.
    """
    stack = [(dst, src)]
    while stack:
        current_dst, current_src = stack.pop()
        for key in current_src:
            source = current_src[key]
            if key not in current_dst:
                current_dst[key] = source
            else:
                dest = current_dst[key]
                if isinstance(source, dict) and isinstance(dest, dict):
                    stack.append((dest, source))
                elif isinstance(source, list) and isinstance(dest, list):
                    merge_lists(dest, source, extend_lists=extend_lists)
                else:
                    current_dst[key] = source
    return dst


def merge_lists(dest, source, extend_lists=False):
    """Recursively merge two lists.

    This applies merge_dictionary if any of the entries are dicts.
    Note: This updates dst.
    """
    if not source:
        return
    if not extend_lists:
        # Make them the same size
        left = dest
        right = source[:]
        if len(dest) > len(source):
            right.extend([None for _ in range(len(dest) - len(source))])
        elif len(dest) < len(source):
            left.extend([None for _ in range(len(source) - len(dest))])
        # Merge lists
        for index, value in enumerate(left):
            if value is None and right[index] is not None:
                dest[index] = right[index]
            elif isinstance(value, dict) and \
                    isinstance(right[index], dict):
                merge_dictionary(dest[index], source[index],
                                 extend_lists=extend_lists)
            elif isinstance(value, list):
                merge_lists(value, right[index])
            elif right[index] is not None:
                dest[index] = right[index]
    else:
        dest.extend([src for src in source if src not in dest])
    return dest


def is_ssh_key(key):
    """Check if string looks like it is an ssh key."""
    if not key:
        return False
    if not isinstance(key, basestring):
        return False
    if not key.startswith('ssh-rsa AAAAB3NzaC1yc2EA'):
        return False
    if ' ' not in key:
        return False
    parts = key.split()
    if len(parts) < 2:
        return False
    key_string = parts[1]
    try:
        data = base64.decodestring(key_string)
    except StandardError:
        return False
    int_len = 4
    str_len = struct.unpack('>I', data[:int_len])[0]  # this should return 7
    if str_len != 7:
        return False
    if data[int_len:int_len + str_len] == 'ssh-rsa':
        return True
    return False


def get_class_name(instance):
    """Return instance's class name."""
    return instance.__class__.__name__


def get_source_body(function):
    """Get the body of a function (i.e. no definition line, and unindented."""
    lines = inspect.getsource(function).split('\n')

    # Find body - skip decorators and definition
    start = 0
    for number, line in enumerate(lines):
        if line.strip().startswith("@"):
            start = number + 1
        elif line.strip().startswith("def "):
            start = number + 1
            break
    lines = lines[start:]

    # Unindent body
    indent = len(lines[0]) - len(lines[0].lstrip())
    for index, line in enumerate(lines):
        lines[index] = line[indent:]
    return '\n'.join(lines)


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
    except StandardError:
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


def is_evaluable(value):
    """Check if value is a function that can be passed to evaluate()."""
    try:
        return (value.startswith('=generate_password(') or
                value.startswith('=generate_uuid('))
    except AttributeError:
        return False


def generate_password(min_length=None, max_length=None, required_chars=None,
                      starts_with=string.ascii_letters, valid_chars=None):
    """Generate a password based on constraints provided.

    :param min_length: minimum password length
    :param max_length: maximum password length
    :param required_chars: a set of character sets, one for each required char
    :param starts_with: a set of characters required as the first character
    :param valid_chars: the set of valid characters for non-required chars
    """
    # Raise Exception if max_length exceeded
    if min_length > 255 or max_length > 255:
        raise ValueError('Maximum password length of 255 characters exceeded.')

    # Choose a valid password length based on min_length and max_length
    if max_length and min_length and max_length != min_length:
        password_length = random.randint(min_length, max_length)
    else:
        password_length = max_length or min_length or 12

    # If not specified, default valid_chars to letters and numbers
    valid_chars = valid_chars or ''.join([
        string.ascii_letters,
        string.digits
    ])

    first_char = ''
    if starts_with:
        first_char = random.choice(starts_with)
        password_length -= 1

    password = ''
    if required_chars:
        for required_set in required_chars:
            if password_length > 0:
                password = ''.join([password, random.choice(required_set)])
                password_length -= 1
            else:
                raise ValueError(
                    'Password length is less than the '
                    'number of required characters.'
                )

    if password_length > 0:
        password = ''.join([
            password,
            ''.join(
                [random.choice(valid_chars) for _ in range(password_length)]
            )
        ])

    # Shuffle all except first_char
    password = ''.join(random.sample(password, len(password)))

    return '%s%s' % (first_char, password)


def evaluate(function_string):
    """Evaluate an option value.

    Understands the following functions:
    - generate_password()
    - generate_uuid()
    """
    func_name, kwargs = codegen.kwargs_from_string(function_string)
    if func_name == 'generate_uuid':
        return uuid.uuid4().hex
    if func_name == 'generate_password':
        return generate_password(**kwargs)
    raise NameError("Unsupported function: %s" % function_string)


def execute_shell(command, with_returncode=True, cwd=None, strip=True):
    """Execute a command (containing no shell operators) locally.

    Raises CheckmateCalledProcessError on non-zero exit status.

    :param command:         Shell command to be executed. If the value is
                            a string, it will be split using shlex.split()
                            to return a shell-like syntax as a list. If the
                            value is a list, it will be passed directly to
                            Popen.
    :param with_returncode: Include the exit_code in the return body.
                            Default is True.
    :param cwd:             The child's current directory will be changed
                            to `cwd` before it is executed. Note that this
                            directory is not considered when searching the
                            executable, so you can't specify the program's
                            path relative to this argument. Value should not
                            be quoted or shell escaped, since it is passed
                            directly to os.chdir() by subprocess.Popen
    :param strip:           Strip the output of whitespace using str.strip()
    :returns:               A dict with 'stdout', and (optionally),
                            'returncode'

    Note:   Popen is called with stderr=subprocess.STDOUT, which sends
            all stderr to stdout.
    """
    if isinstance(command, basestring):
        cmd = shlex.split(command)
    elif isinstance(command, list):
        cmd = command
        command = " ".join(cmd)
    else:
        raise TypeError("'command' should be a string or a list")
    LOG.debug("Executing `%s` on local machine", command)
    LOG.debug("Command after split: %s", cmd)
    try:
        pope = subprc.Popen(
            cmd, stdout=subprc.PIPE, stderr=subprc.STDOUT, cwd=cwd,
            universal_newlines=True)
    except OSError as err:
        raise cmexc.CheckmateCalledProcessError(
            1, command, output=repr(err))
    out, err = pope.communicate()
    assert not err
    out = {'stdout': out.strip() if strip else out}
    if pope.returncode != 0:
        raise cmexc.CheckmateCalledProcessError(
            pope.returncode, command, output=out['stdout'])
    if with_returncode:
        out.update({'returncode': pope.returncode})
    return out


def check_all_output(params, find="ERROR", env=None, cwd=None):
    """Detect 'find' string in params, returning a list of all matching lines.

    Similar to subprocess.check_output, but parses both stdout and stderr
    and detects any string passed in as the find parameter.

    :returns: tuple (stdout, stderr, lines with :param:find in them)

    We used this for processing Knife output where the details of the error
    were piped to stdout and the actual error did not have everything we
    needed because knife did not exit with an error code, but now we're just
    keeping it for the script provider (coming soon)
    """
    on_posix = 'posix' in sys.builtin_module_names

    def start_thread(func, *args):
        """Start thread as a daemon."""
        thread = threading.Thread(target=func, args=args)
        thread.daemon = True
        thread.start()
        return thread

    def consume(infile, output, found):
        """Per thread: read lines in file searching for find."""
        for line in iter(infile.readline, ''):
            output(line)
            if find in line:
                found(line)
        infile.close()

    process = subprc.Popen(params, stdout=subprc.PIPE,
                           stderr=subprc.PIPE, bufsize=1,
                           close_fds=on_posix, env=env, cwd=cwd)

    # preserve last numlines of stdout and stderr
    numlines = 100
    stdout = collections.deque(maxlen=numlines)
    stderr = collections.deque(maxlen=numlines)
    found = collections.deque(maxlen=numlines)
    threads = [start_thread(consume, *args)
               for args in (process.stdout, stdout.append, found.append),
               (process.stderr, stderr.append, found.append)]
    for thread in threads:
        thread.join()  # wait for IO completion

    retcode = process.wait()

    if retcode == 0:
        return (stdout, stderr, found)
    else:
        msg = "stdout: %s \n stderr: %s \n Found: %s" % (stdout, stderr, found)
        LOG.debug(msg)
        raise cmexc.CheckmateCalledProcessError(
            retcode, ' '.join(params),
            output='\n'.join(stdout),
            error_info='%s%s' % ('\n'.join(stderr), '\n'.join(found)))


def copy_contents(source, dest, with_overwrite=False, create_path=True):
    """Copy the contents of a `source' directory to `dest'.

    It's affect is roughly equivalent to the following shell command:

    mkdir -p /path/to/dest && cp -r /path/to/source/* /path/to/dest/

    """
    if not os.path.exists(dest):
        if create_path:
            os.makedirs(dest)
        else:
            raise IOError("%s does not exist.  Use create_path=True to create "
                          "destination" % dest)
    for src_file in os.listdir(source):
        source_path = os.path.join(source, src_file)
        if os.path.isdir(source_path):
            try:
                shutil.copytree(source_path, os.path.join(dest, src_file))
            except OSError as exc:
                if exc.errno == 17:  # File exists
                    if with_overwrite:
                        shutil.rmtree(os.path.join(dest, src_file))
                        shutil.copytree(
                            source_path, os.path.join(dest, src_file))
                    else:
                        raise IOError("%s exists, use with_overwrite=True to "
                                      "overwrite destination." % dest)
        else:
            shutil.copy(source_path, dest)


def filter_resources(resources, provider_name):
    """Return resources of a specified type."""
    results = []
    for resource in resources.values():
        if 'provider' in resource:
            if resource['provider'] == provider_name:
                results.append(resource)
    return results


def hide_url_password(url):
    """Detect a password part of a URL and replaces it with *****."""
    try:
        parsed = urlparse.urlsplit(url)
        if parsed.password:
            return url.replace(':%s@' % parsed.password, ':*****@')
    except StandardError:
        pass
    return url


def set_url_creds(url, username=None, password=None):
    """Return url with credentials set as supplied."""
    parsed = urlparse.urlsplit(url)
    scheme, netloc, path, query, fragment = parsed
    netloc = "%s:%s@%s:%s" % (username or '', password or '',
                              parsed.hostname, parsed.port or '')
    netloc = netloc.replace(":@", "@").strip(':@')
    result = urlparse.SplitResult(scheme=scheme, netloc=netloc, path=path,
                                  query=query, fragment=fragment)
    return urlparse.urlunsplit(result)


def are_dir_trees_equal(dir1, dir2):
    """Compare two directories recursively.

    Files in each directory are assumed to be equal if their names and contents
    are equal.

    @param dir1: First directory path
    @param dir2: Second directory path

    @return: True if the directory trees are the same and
        there were no errors while accessing the directories or files,
        False otherwise.

    Original Author: http://stackoverflow.com/users/817499/mateusz-kobos
    """
    if not os.path.exists(dir1):
        return False
    if not os.path.exists(dir2):
        return False

    def check_dircmp(dircmp):
        """Check dircmp deeply."""
        if dircmp.left_only or dircmp.right_only or dircmp.funny_files:
            return False
        _, mismatch, errors = filecmp.cmpfiles(
            dir1, dir2, dircmp.common_files, shallow=False)
        if mismatch or errors:
            return False
        for subdir_cmp in dircmp.subdirs.values():
            if not check_dircmp(subdir_cmp):
                return False
        return True

    dirs_cmp = filecmp.dircmp(dir1, dir2)
    return check_dircmp(dirs_cmp)


def create_hashable(obj, hash_all=False):
    """Try to create a hashable from combinations of lists, sets, and dicts.

    Does not necessarily work on all objects. In this case it will return the
    TypeError (unhashable) exception generated.

    To recursively hash every observed object, element, item, key, and value,
    use hash_all=True.
    """
    chsh = lambda arg: create_hashable(arg, hash_all=hash_all)
    try:
        hashed = hash(obj)
    except TypeError:
        if isinstance(obj, (tuple, list, set, frozenset)):
            try:
                obj = sorted(obj)
            except TypeError:
                pass
            return frozenset(chsh(o) for o in obj)
        elif isinstance(obj, (dict, collections.Mapping)):
            obj_items = obj.items()
            try:
                obj_items = sorted(obj_items)
            except TypeError:
                pass
            return frozenset((chsh(key), chsh(value))
                             for key, value in obj_items)
        else:
            raise
    else:
        if hash_all:
            return hashed
        else:
            return obj


def total_size(obj, handlers={}):
    """Return the approximate memory footprint of an object and its contents.

    Automatically finds the contents of the following builtin containers and
    their subclasses:  tuple, list, deque, dict, set and frozenset.
    To search other containers, add handlers to iterate over their contents:

    :keyword handlers: hash of functions used to iterate on specific types
        ex. handlers = {SomeContainerClass: iter,
                    OtherContainerClass: OtherContainerClass.get_elements}
    """
    dict_handler = lambda d: itertools.chain.from_iterable(d.items())
    all_handlers = {
        tuple: iter,
        list: iter,
        collections.deque: iter,
        dict: dict_handler,
        set: iter,
        frozenset: iter,
    }
    all_handlers.update(handlers)  # user handlers take precedence
    seen = set()  # track which object id's have already been seen
    default_size = sys.getsizeof(0)  # estimate sizeof object w/o __sizeof__

    def sizeof(obj):
        if id(obj) in seen:  # do not double count the same object
            return 0
        seen.add(id(obj))
        size = sys.getsizeof(obj, default_size)

        for typ, handler in all_handlers.items():
            if isinstance(obj, typ):
                size += sum(map(sizeof, handler(obj)))
                break
        return size

    return sizeof(obj)


class ContextPool(eventlet.GreenPool):

    """GreenPool subclassed to kill its coros when it gets gc'ed."""

    def __enter__(self):
        """."""
        return self

    def __exit__(self, type, value, traceback):
        """Kill coroutines on exit."""
        for coro in list(self.coroutines_running):
            coro.kill()


class GreenAsyncPileWaitallTimeout(eventlet.Timeout):

    """Wait for routines to finish."""


class GreenAsyncPile(object):

    """Runs jobs in a pool of green threads with results iterator.

    The results can be retrieved by using this object as an iterator.

    This is very similar in principle to eventlet.GreenPile, except it returns
    results as they become available rather than in the order they were
    launched.

    Correlating results with jobs (if necessary) is left to the caller.
    """

    def __init__(self, size):
        """Init and set size of pool.

        :param size: size pool of green threads to use.
        """
        if isinstance(size, eventlet.GreenPool):
            self._pool = size
            self._responses = eventlet.queue.LightQueue(size.size)
            self._errors = eventlet.queue.LightQueue(size.size)
        else:
            self._pool = eventlet.GreenPool(size)
            self._responses = eventlet.queue.LightQueue(size)
            self._errors = eventlet.queue.LightQueue(size)
        self._inflight = 0

    def _run_func(self, func, args, kwargs, _return_value_key=None):
        try:
            if _return_value_key:
                self._responses.put((_return_value_key, func(*args, **kwargs)))
            else:
                self._responses.put(func(*args, **kwargs))
        except Exception as exc:
            LOG.exception(exc)
            # if we let this raise here, it won't raise in the
            # context of the process that spawned it.
            # Send it back to that thread and allow it
            # to check for results that are Exceptions
            if _return_value_key:
                self._errors.put((_return_value_key, exc))
                self._responses.put((_return_value_key, exc))
            else:
                self._errors.put(exc)
                self._responses.put(exc)
        finally:
            self._inflight -= 1

    def spawn(self, func, *args, **kwargs):
        """Spawn a job in a green thread on the pile."""
        _return_value_key = copy.deepcopy(
            kwargs.pop('_return_value_key', None))
        self._inflight += 1
        self._pool.spawn(self._run_func, func, args, kwargs,
                         _return_value_key=_return_value_key)

    def waitall(self, timeout):
        """Wait timeout seconds for any results to come in.

        :param timeout: seconds to wait for results
        :returns: list of results accrued in that time
        """
        results = []
        try:
            with GreenAsyncPileWaitallTimeout(timeout):
                while True:
                    results.append(self.next())
        except (GreenAsyncPileWaitallTimeout, StopIteration):
            pass
        return results

    def __iter__(self):
        """."""
        return self

    def next(self):
        """."""
        try:
            return self._responses.get_nowait()
        except Queue.Empty:
            if self._inflight == 0:
                raise StopIteration()
            else:
                return self._responses.get()

    def get_errors(self):
        """Return an iterator of errors from the pile."""
        def _get_errors():
            while not self._errors.empty():
                try:
                    yield self._errors.get_nowait()
                except Queue.Empty:
                    yield
        return (err for err in _get_errors() if err)
