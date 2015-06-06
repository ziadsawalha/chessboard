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

"""Built-in Provider that supplies key-pairs."""

from __future__ import print_function

import copy

from chessboard import keys
from chessboard.providers import base
from chessboard import utils

DEFAULT_CATALOG = utils.yaml_to_dict("""
core_key_pair:
  resource_type: key-pair
""")


class Provider(base.Provider):

    """Provides keys."""

    def __init__(self, key=None, catalog=None, constraints=None):
        """Initialize instance of Provider with supplied environment values."""
        if catalog is None:
            catalog = copy.deepcopy(DEFAULT_CATALOG)
        super(Provider, self).__init__(key=key,
                                       catalog=catalog,
                                       constraints=constraints)

    def add_resource(self, resource, deployment):
        """TODO: Example Call."""
        private, public = keys.generate_key_pair()
        resource['instance']['private'] = private
        resource['instance']['public'] = public
        return [resource]
