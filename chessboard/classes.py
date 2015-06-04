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

"""Utility Classes.

ExtensibleDict is a dict that supports the following extra features:
- accepts attributes (built-in dicts don't).
- can be validated by setting a callable to __schema__.
- __schema__ callable may also coerce the dict into a defined structure.
- subclasses will not break automatic serialization by json or PyYAML.

Note: this comes from [morpheus](https://github.com/ziadsawalha/morpheus). The
conditional handling of the `yaml` import makes this module work even if used
in an environment without yaml installed. This is not going to be an issue in
`chessboard` since chessboard requires PyYAML, but I left that in there to
allow for porting to [simpl](https://github.com/checkmate/simple) and minimize
changes from the version in morpheus.
"""

import six
try:  # see note in docstring on this conditional import
    import yaml
    from yaml import Dumper
    from yaml import representer
    from yaml import SafeDumper
    YAML_DETECTED = True
except ImportError:  # pragma: nocover
    YAML_DETECTED = False


def register_yaml_representer(cls):
    """Register our classes with YAML for de/serialization."""
    yaml.add_representer(cls, representer.Representer.represent_dict,
                         Dumper=Dumper)
    yaml.add_representer(cls, representer.SafeRepresenter.represent_dict,
                         Dumper=SafeDumper)


class ExtensibleDictSubclassDetector(type):

    """Metaclass to detect when ExtensibleDict is subclassed."""

    def __new__(mcs, *args, **kwargs):
        """Called whenever a new ExtensibleDict subclasse is defined."""
        new_type = type.__new__(mcs, *args, **kwargs)
        register_yaml_representer(new_type)
        if args[0] != "ExtensibleDict":
            ExtensibleDict.__initsubclass__(new_type)
        return new_type


@six.add_metaclass(ExtensibleDictSubclassDetector)
class ExtensibleDict(dict):

    """Class that behaves like a dict and can be extended and validated."""

    def __new__(cls, *args, **kwargs):
        """Called before __init__ of a new ExtensibleDict class/superclass."""
        # Using dict.__new__ lets us create a new instance that has `dict` as
        # its underlying implementation.
        obj = dict.__new__(cls)
        # We call __init__ ourselves since we're controlling the instantiation.
        obj.__init__(*args, **kwargs)
        # TODO(zns): We shoud be able to call this once per class definition,
        # in __initsubclass__ and not for each instantiation, but yaml seems
        # to need it here. Until I figure out how pyyaml detects classes I need
        # to do this here:
        if YAML_DETECTED is True:
            register_yaml_representer(cls)
        return obj

    @classmethod
    def __initsubclass__(cls, subclass):
        """Called when ExtensibleDict has been subclassed."""
        # I wish we could uncomment the following line and remove the call that
        # is not in __new__, but PyYAML dumping then fails
        # register_yaml_representer(cls)
        pass

    #
    # dict emulation methods
    #
    def __init__(self, *args, **kwargs):
        """Validate data on instantiation."""
        # Validate the incoming data first (`validate` is a class method)
        self.validate(dict(*args, **kwargs))
        dict.__init__(self, *args, **kwargs)
        # Validate the actual class allowing coercion
        self.validate(self)

    def __setitem__(self, key, value):
        """Set item and keep data valid."""
        # TODO(zns): validate
        dict.__setitem__(self, self.__keytransform__(key), value)

    def __delitem__(self, key):
        """Remove item and keep data valid."""
        # TODO(zns): validate
        dict.__delitem__(self, key)

    @staticmethod
    def __keytransform__(key):
        """Translate key to a hashable value."""
        return key

    #
    # Schema methods
    #
    @classmethod
    def validate(cls, data):
        """Check schema and validate data.

        :raises: ValueError or Schema errors if errors exist.
        :returns: the current object with any type coercions applied.
        """
        schema = getattr(cls, '__schema__', None)
        if schema and data:
            return schema(data)
