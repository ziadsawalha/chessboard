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

"""Classes and utilities for modeling and handling application components."""

from chessboard import classes
from chessboard import schema


class Component(classes.ExtensibleDict):

    """Construct and validate the relations between application services.

    The main thing this class does right now is read parsed and validated
    Checkmatefile contents (see :meth:`from_deployment`), analyze the
    relations defined for each service, create a simple mapping for those
    relations, and check that the relations are valid.
    """

    __schema__ = schema.COMPONENT_SCHEMA

    def __init__(self, *args, **kwargs):
        """Create a new Component.

        :keyword id: string - unique identifier
        :keyword provider: provider that manages this component

        Note: for details of classes, go see the schema module
        """
        contents = dict(*args, **kwargs)
        self.provider = contents.pop('provider', None)
        super(Component, self).__init__(contents)
        if self.provider:
            self['provider'] = self.provider.key
        self._resource_type = (self.get('is') or self.get('type') or
                               self.get('resource_type'))

    @property
    def resource_type(self):
        """Return resource_type value."""
        return self._resource_type

    @property
    def provides(self):
        """Return what the component provides."""
        return self.setdefault('provides', [])

    @property
    def requires(self):
        """Return what the component requires."""
        return self.setdefault('requires', [])

    @property
    def supports(self):
        """Return what the component optionally supports."""
        return self.setdefault('supports', [])
