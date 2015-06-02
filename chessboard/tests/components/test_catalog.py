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

"""Tests for the :mod:`chessboard.components.catalog` module."""

import os
import shutil
import tempfile
import unittest

from chessboard.components import catalog


class TestGetDefaultCatalog(unittest.TestCase):

    """Tests for :func:`chessboard.components.catalog.get_default_catalog`."""

    def test_empty(self):
        """Case where the components directory is empty."""
        tempdir = tempfile.mkdtemp()

        try:
            cat = catalog.get_default_catalog(components_dir=tempdir)
            self.assertDictEqual({}, cat)
        finally:
            shutil.rmtree(tempdir)

    def test_typical(self):
        """Test catalog loading from a directory with a few components."""
        tempdir = tempfile.mkdtemp()

        redis_component = """
            name: redis
            commands:
              install: "apt-get update && apt-get install redis-server -y"
              start: "redis-server"
            provides:
              - resource_type: database
                interface: redis
                port:
                  default: 6379
            requires:
              - resource_type: compute
                relation: host
                interface: linux
                constraints:
                - setting: os
                  value: ubuntu 14.04"""
        mongo_component = """
            name: mongodb
            commands:
              install: "apt-get update && apt-get install mongodb -y"
              start: "mongod"
            provides:
              - resource_type: database
                interface: mongodb
                port:
                  default: 27017
            requires:
              - resource_type: compute
                relation: host
                interface: linux
                constraints:
                - setting: os
                  value: ubuntu 14.04"""

        try:
            redis_dir = os.path.join(tempdir, 'redis')
            os.makedirs(redis_dir)
            mongo_dir = os.path.join(tempdir, 'mongodb')
            os.makedirs(mongo_dir)
            foo_dir = os.path.join(tempdir, 'foo')
            os.makedirs(foo_dir)

            with open(os.path.join(redis_dir, 'component.yaml'), 'w') as fp:
                fp.write(redis_component)
            with open(os.path.join(mongo_dir, 'component.yaml'), 'w') as fp:
                fp.write(mongo_component)
            # `foo_dir` has no component file, so we will ignore it.

            cat = catalog.get_default_catalog(components_dir=tempdir)
            self.assertEqual(2, len(cat))
            redis = cat['redis']
            mongo = cat['mongodb']

            expected_redis = {
                'name': 'redis',
                'id': None,
                'files': [],
                'commands': {
                    'install': ('apt-get update && apt-get install '
                                'redis-server -y'),
                    'start': 'redis-server',
                },
                'provides': [
                    {'interface': 'redis', 'port': {'default': 6379},
                     'resource_type': 'database'},
                ],
                'requires': [
                    {'constraints': [
                        {'setting': 'os', 'value': 'ubuntu 14.04'}],
                     'interface': 'linux',
                     'relation': 'host',
                     'resource_type': 'compute'},
                ]
            }
            self.assertDictEqual(expected_redis, redis.__dict__)

            expected_mongo = {
                'name': 'mongodb',
                'id': None,
                'files': [],
                'commands': {
                    'install': 'apt-get update && apt-get install mongodb -y',
                    'start': 'mongod',
                },
                'provides': [
                    {'interface': 'mongodb', 'port': {'default': 27017},
                     'resource_type': 'database'},
                ],
                'requires': [
                    {'constraints': [
                        {'setting': 'os', 'value': 'ubuntu 14.04'}],
                     'interface': 'linux',
                     'relation': 'host',
                     'resource_type': 'compute'},
                ]
            }
            self.assertDictEqual(expected_mongo, mongo.__dict__)
        finally:
            shutil.rmtree(tempdir)
