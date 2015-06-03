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

"""Docker provider for launching applications from a Checkmatefile."""

from __future__ import print_function

import copy

from chessboard.providers import base
from chessboard import utils

DEFAULT_CATALOG = utils.yaml_to_dict("""
docker_generic:
  resource_type: application
docker_mysql:
  resource_type: database
  provides:
  - database: mysql

""")


class Provider(base.Provider):

    """Provides Docker Containers."""

    def __init__(self, key=None, catalog=None, constraints=None):
        if catalog is None:
            catalog = copy.deepcopy(DEFAULT_CATALOG)
        super(Provider, self).__init__(key=key,
                                       catalog=catalog,
                                       constraints=constraints)
