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

"""Tests for the :mod:`chessboard.resolver` module."""

import unittest

import six

from chessboard.deployment import Deployment
from chessboard import parser
from chessboard import resolver


class TestResolver(unittest.TestCase):

    """Tests for :mod:`chessboard.resolver`."""

    def test(self):
        contents = six.StringIO("""
            blueprint:
              services:
                just_a_key:
                  component:
                    resource_type: database
                  constraints:
                  - setting: count
                    value: 3
            resources:
              user:
                type: user
            environment:
              providers:
                docker:
                  constraints:
                  - name: Hi
            inputs:
              resources:
              - type: Ha!
        """)
        checkmate_file = parser.load(contents)
        deployment = Deployment.from_checkmate_file(checkmate_file)
        resolver.resolve(deployment)
        expected = {
            '1': {
                'status': 'PLANNED',
                'index': '1',
                'service': 'just_a_key',
                'provider': 'docker',
                'component': 'docker_mysql',
                'dns-name': 'just_a_key02.checkmate.local',
                'instance': {},
                'desired-state': {},
                'type': 'database'
            },
            '0': {
                'status': 'PLANNED',
                'index': '0',
                'service': 'just_a_key',
                'provider': 'docker',
                'component': 'docker_mysql',
                'dns-name': 'just_a_key01.checkmate.local',
                'instance': {},
                'desired-state': {},
                'type': 'database'
            },
            '2': {
                'status': 'PLANNED',
                'index': '2',
                'service': 'just_a_key',
                'provider': 'docker',
                'component': 'docker_mysql',
                'dns-name': 'just_a_key03.checkmate.local',
                'instance': {},
                'desired-state': {},
                'type': 'database'
            },
            '3': {
                'index': '3',
                'type': 'Ha!'
            },
            'user': {
                'type': 'user'
            }
        }
        self.assertEqual(expected, deployment['resources'])


if __name__ == '__main__':
    unittest.main()
