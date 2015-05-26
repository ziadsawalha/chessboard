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

"""Utilities for modeling and loading application components."""

import os

from chessboard import classes
from chessboard import parser
from chessboard import schema


class Component(classes.ExtensibleDict):

    """Component definition for a :class:`Service`."""

    def __init__(self, name, provides, id=None, files=None, commands=None,
                 requires=None):
        """Constructor.

        For more details on each parameter, see
        :data:`chessboard.schema.COMPONENT_SCHEMA`.
        """
        super(Component, self).__init__(
            name=name, provides=provides, id=id, files=files,
            commands=commands, requires=requires
        )
        self.name = name
        self.provides = provides
        self.id = id
        self.files = files or []
        self.commands = commands or {}
        self.requires = requires or []


def get_default_catalog(components_dir=os.path.dirname(__file__)):
    """Load a catalog of components from a components directory.

    :param str components_dir:
        Defaults to `chessboard/components`.

    :returns:
        `dict` of :class:`Component` objects, keyed by component name.
    """
    catalog = {}

    for each in os.listdir(components_dir):
        each_path = os.path.join(components_dir, each)
        if os.path.isdir(each_path):
            # assume it's a component
            # look for a yaml file with the name component.yaml
            comp_yaml = os.path.join(each_path, 'component.yaml')
            if not os.path.exists(comp_yaml):
                # No component found in this dir; ignore it.
                continue
            with open(comp_yaml) as fp:
                comp_contents = parser.load(fp, schema=schema.COMPONENT_SCHEMA)
                catalog[comp_contents['name']] = Component(**comp_contents)
    return catalog
