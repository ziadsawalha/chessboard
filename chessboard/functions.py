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

"""Blueprint functions.

Functions are YAML or JSON objects that can be evaluated at runtime to yield
values which are used to replace the function node.

This enables inserting values in YAML/JSON objects which get evaluated at
runtime into objects or values conditionally or using data not available
during design time (when the JSON/YAML is being authored.

For example:

```yaml
blueprint:
  options:
    publish:
      default: false
      type: boolean
    url:
      type: url
      required:
        value: inputs://publish
inputs:
  blueprint:
    publish: true
```

Functions that can be used in blueprints:
- value: accepts URI-type values (ex. resources://0/instance/ip)
- patterns.*: used to pull in tested regex patterns from patterns.yaml
"""

import copy
import os

import six
import six.moves.urllib.parse as urlparse
import yaml

from chessboard import exceptions
from chessboard import utils


def get_patterns():
    """Load regex patterns from patterns.yaml.

    These are effectively macros for blueprint authors to use.

    We cache this so we don't have to parse the yaml frequently. We always
    return a copy so we don't share the mutable between calls (and clients).
    """
    if hasattr(get_patterns, 'cache'):
        return copy.deepcopy(get_patterns.cache)
    path = os.path.join(os.path.dirname(__file__), 'patterns.yaml')
    patterns = yaml.safe_load(open(path, 'r'))
    get_patterns.cache = patterns
    return copy.deepcopy(patterns)

PATTERNS = {'patterns': get_patterns()}


def evaluate(obj, **kwargs):
    """Evaluate the passed in object using Checkmate syntax."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'value':
                value = evaluate(value, **kwargs)
                return get_value(value, **kwargs)
        return obj
    elif isinstance(obj, list):
        return [evaluate(o, **kwargs) for o in obj]
    else:
        return obj


def get_value(value, **kwargs):
    """Parse value entry (supports URIs)."""
    if is_uri(value):
        return get_from_path(value, **kwargs)
    elif is_pattern(value):
        return get_pattern(value, PATTERNS)
    else:
        return value


def is_uri(value):
    """Quick check to see if we have a URI."""
    if isinstance(value, six.string_types):
        if '://' in value:
            try:
                parsed = urlparse.urlparse(value)
                return len(parsed.scheme) > 0
            except AttributeError:
                return False
    return False


def is_pattern(value):
    """Quick check to see if we have a pattern from the pattern library."""
    return (isinstance(value, six.string_types) and
            value.startswith("patterns.") and
            value[-1] != ".")


def parse(obj, **kwargs):
    """Evaluate the passed in object's values using Checkmate syntax."""
    if isinstance(obj, dict):
        return {k: evaluate(v, **kwargs) for k, v in obj.items()}
    else:
        return obj


def get_from_path(path, **kwargs):
    """Find value using URL syntax."""
    if not path:
        return path
    try:
        parsed = urlparse.urlparse(path)
        focus = kwargs[parsed.scheme]
        if parsed.netloc or parsed.path:
            combined = '%s/%s' % (parsed.netloc, parsed.path)
            combined = combined.replace('//', '/').strip('/')
            return utils.read_path(focus, combined)
        else:
            return focus
    except KeyError:
        return path


def path_exists(path, **kwargs):
    """Check value exists using URL syntax."""
    if not path:
        return False
    try:
        parsed = urlparse.urlparse(path)
        focus = kwargs[parsed.scheme]
        if parsed.netloc or parsed.path:
            combined = '%s/%s' % (parsed.netloc, parsed.path)
            combined = combined.replace('//', '/').strip('/')
            return utils.path_exists(focus, combined)
        else:
            return False
    except KeyError:
        return False


def get_pattern(value, patterns):
    """Get pattern from pattern library."""
    pattern = utils.read_path(patterns, value.replace('.', '/'))
    if not isinstance(pattern, dict):
        if pattern is None:
            raise exceptions.ChessboardDoesNotExist(
                "Pattern '%s' does not exist" % value)
        else:
            raise exceptions.ChessboardError(
                "Pattern is not in valid format: %s" % value)
    if 'value' not in pattern:
        raise exceptions.ChessboardError(
            "Pattern is missing 'value' entry: %s" % value)
    return pattern['value']
