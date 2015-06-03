"""Utility Classes.

ExtensibleDict is a dict that supports the following extra features:
- accepts atributes (built-in dicts don't).
- can be validated by setting a callable to __schema__.
- __schema__ callable may also coerce the dict into defined structure.
- subclasses get hooked into YAML serialization mechanism
- subclasses will get automatically serialized by json
"""

import six
try:
    import yaml
    from yaml import SafeDumper, Dumper
    from yaml import representer
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
        new_type = type.__new__(mcs, *args, **kwargs)
        register_yaml_representer(new_type)
        if args[0] != "ExtensibleDict":
            ExtensibleDict.__initsubclass__(new_type)
        return new_type


@six.add_metaclass(ExtensibleDictSubclassDetector)
class ExtensibleDict(dict):

    """Class that behaves like a dict and can be extended and validated."""

    def __new__(cls, *args, **kwargs):
        obj = dict.__new__(cls)
        obj.__init__(*args, **kwargs)
        # TODO: don't register each one, but until I figure out how pyyaml
        # detects classes I need to:
        if YAML_DETECTED is True:
            register_yaml_representer(cls)
        return obj

    @classmethod
    def __initsubclass__(cls, subclass):
        """Called when ExtensibleDict has been subclassed"""
        # I wish we could do this here, but PyYAML dumping then fails
        # register_yaml_representer(cls)
        pass

    #
    # dict emulation methods
    #
    def __init__(self, *args, **kwargs):
        # Validate the incoming data first
        self.validate(dict(*args, **kwargs))
        # Validate the actual class allowing coercion
        dict.__init__(self, *args, **kwargs)
        self.validate(self)

    def __setitem__(self, key, value):
        #TODO: validate
        dict.__setitem__(self, self.__keytransform__(key), value)

    def __delitem__(self, key):
        #TODO: validate
        dict.__delitem__(self, key)

    @staticmethod
    def __keytransform__(key):
        return key

    #
    # Schema methods
    #
    @classmethod
    def validate(cls, data):
        """Checks schema and validates data.

        :raises: ValueError or Schema errors if errors exist.
        :returns: the current object with any type coercions applied.
        """
        schema = getattr(cls, '__schema__', None)
        if schema and data:
            return schema(data)
