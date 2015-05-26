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

"""Tests for the :mod:`chessboard.providers.docker` module."""

import os
import shutil
import tempfile
import unittest

import mock
import six

from chessboard import parser
from chessboard.providers import docker
from chessboard import schema


class TestComponentToDockerfile(unittest.TestCase):

    """Tests for `_component_to_dockerfile`."""

    def test_redis(self):
        """Test the conversion of a sample redis component file."""
        componentfile = six.StringIO("""
            name: redis
            commands:
              install: "apt-get update && apt-get install redis-server -y"
              start: "redis-server"
            provides:
              - resource_type: database  # could also be `cache`
                interface: redis
                port:
                  default: 6379
                  # we can also override the default from other sources:
                  #env: REDIS_PORT
                  #keychain: redis-port
            requires:
              - resource_type: compute
                relation: host
                interface: linux
                constraints:
                  - setting: os
                    value: 'ubuntu 14.04'""")
        component = parser.load(componentfile, schema=schema.COMPONENT_SCHEMA)
        dockerfile = docker._component_to_dockerfile(component)

        expected_dockerfile = """\
FROM ubuntu:14.04



RUN apt-get update && apt-get install redis-server -y

EXPOSE 6379

CMD redis-server
"""
        self.assertEqual(expected_dockerfile, dockerfile)

    def test_example_app(self):
        """Test conversion of a custom example application."""
        componentfile = six.StringIO("""
name: testapp
files:
  - source: .
    dest: /opt/myapp
  - source: ./static
    dest: /var/www/myapp
commands:
  install: |
    apt-get update
    apt-get install \
    python-pip
    pip install \
        redis \
        flask
  start: "python server.py"
provides:
  - resource_type: application
    interface: http
    port:
      default: 80
requires:
  - resource_type: compute
    relation: host
    interface: linux
    constraints:
      - setting: os
        value: 'ubuntu 14.04'""")
        component = parser.load(componentfile, schema=schema.COMPONENT_SCHEMA)
        dockerfile = docker._component_to_dockerfile(component,
                                                     src_dir_prefix=None)

        expected_dockerfile = """\
FROM ubuntu:14.04

ADD [".", "/opt/myapp"]
ADD ["./static", "/var/www/myapp"]

RUN apt-get update
RUN apt-get install     python-pip
RUN pip install         redis         flask

EXPOSE 80

CMD python server.py
"""
        self.assertEqual(expected_dockerfile, dockerfile)

    def test_example_app_absolute_source_dir(self):
        """Case where app source files are specified with an abspath."""
        tempdir = tempfile.mkdtemp()
        try:
            componentfile = six.StringIO("""
name: testapp
files:
  - source: %(tempdir)s
    dest: /opt/myapp
commands:
  install: |
    apt-get update
    apt-get install \
    python-pip
    pip install \
        redis \
        flask
  start: "python server.py"
provides:
  - resource_type: application
    interface: http
    port:
      default: 80
requires:
  - resource_type: compute
    relation: host
    interface: linux
    constraints:
      - setting: os
        value: 'ubuntu 14.04'""" % dict(tempdir=tempdir))
            component = parser.load(componentfile,
                                    schema=schema.COMPONENT_SCHEMA)
            dockerfile = docker._component_to_dockerfile(component)

            expected_dockerfile = """\
FROM ubuntu:14.04

ADD ["%(tempdir)s", "/opt/myapp"]

RUN apt-get update
RUN apt-get install     python-pip
RUN pip install         redis         flask

EXPOSE 80

CMD python server.py
""" % dict(tempdir=tempdir)
            self.assertEqual(expected_dockerfile, dockerfile)
        finally:
            shutil.rmtree(tempdir)


class TestDockerProvider(unittest.TestCase):

    """Tests for :class:`chessboard.providers.docker.DockerProvider`."""

    def setUp(self):
        """Create Checkmatefile file and sample realistic application files."""
        self.working_dir = tempfile.mkdtemp()
        checkmatefile_contents = """
components:
  - name: testapp
    files:
      - source: .
        dest: /opt/testapp
    commands:
      install: |
        apt-get update
        apt-get install python-pip -y
        cd /opt/testapp && pip install -r requirements.txt
      start: "cd /opt/testapp && python server.py"
    provides:
      - resource_type: application
        interface: http
        port:
          default: 80
    requires:
      - resource_type: compute
        relation: host
        interface: linux
        constraints:
          - setting: os
            value: ubuntu 14.04
blueprint:
  services:
    testapp:
      component:
        # component is defined somewhere else
        name: testapp
      relations:
        - service: redis
          interface: redis
    redis:
      component:
         name: redis"""

        server_py_contents = """
from flask import Flask
from redis import Redis
import os
app = Flask(__name__)

redis_1_port = os.environ.get('REDIS_1_PORT')
_proto, host, port = redis_1_port.split(':')
host = host.strip('/')
redis = Redis(host=host, port=port)


@app.route('/')
def hello():
    redis.incr('hits')
    return 'Hello World! I have been seen %s times.' % redis.get('hits')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
"""

        requirements_txt_contents = """
flask
redis
"""
        self.checkmatefile_path = os.path.join(self.working_dir,
                                               'Checkmatefile')
        server_py_path = os.path.join(self.working_dir, 'server.py')
        requirements_txt_path = os.path.join(self.working_dir,
                                             'requirements.txt')

        with open(self.checkmatefile_path, 'w') as fp:
            fp.write(checkmatefile_contents)
        with open(server_py_path, 'w') as fp:
            fp.write(server_py_contents)
        with open(requirements_txt_path, 'w') as fp:
            fp.write(requirements_txt_contents)

        self.dp = docker.DockerProvider(working_dir=self.working_dir)

    def tearDown(self):
        """Clean up the files that `setUp` created."""
        shutil.rmtree(self.working_dir)

    @mock.patch('subprocess.check_call')
    @mock.patch('os.chdir')
    def test_launch(self, os_chdir, sp_cc):
        """Test the `launch` method of the `DockerProvider`.

        This is sort of an integration test, since it will exercise many areas
        of the provider and supporting code.
        """
        tempdir = tempfile.mkdtemp()
        try:
            with mock.patch('shutil.rmtree') as rmtree:
                with open(self.checkmatefile_path) as checkmatefile:
                    self.dp.launch(checkmatefile, tempdir=tempdir)

                self.assertEqual(2, sp_cc.call_count)
                self.assertEqual(2, os_chdir.call_count)
                self.assertEqual(1, rmtree.call_count)

                self.assertEqual(
                    [mock.call('docker-compose build --no-cache'.split()),
                     mock.call('docker-compose up -d'.split())],
                    sp_cc.call_args_list
                )
                starting_dir = os.getcwd()
                self.assertEqual(
                    [mock.call(tempdir), mock.call(starting_dir)],
                    os_chdir.call_args_list
                )
                self.assertEqual([mock.call(tempdir)], rmtree.call_args_list)
            self._verify_docker_artifacts(tempdir)
        finally:
            shutil.rmtree(tempdir)

    def _verify_docker_artifacts(self, tempdir):
        docker_compose_path = os.path.join(tempdir, 'docker-compose.yml')
        redis_path = os.path.join(tempdir, 'docker', 'redis')
        redis_dockerfile = os.path.join(redis_path, 'Dockerfile')
        testapp_path = os.path.join(tempdir, 'docker', 'testapp')
        testapp_dockerfile = os.path.join(testapp_path, 'Dockerfile')

        expected_docker_compose = """\
redis:
  build: %(redis_path)s
  ports:
  - '6379'
testapp:
  build: %(testapp_path)s
  links:
  - redis
  ports:
  - '80'
""" % dict(redis_path=redis_path, testapp_path=testapp_path)
        with open(docker_compose_path) as fp:
            self.assertEqual(expected_docker_compose, fp.read())

        expected_redis_df = """\
FROM ubuntu:14.04



RUN apt-get update && apt-get install redis-server -y

EXPOSE 6379

CMD redis-server
"""
        expected_testapp_df = """\
FROM ubuntu:14.04

ADD ["src/.", "/opt/testapp"]

RUN apt-get update
RUN apt-get install python-pip -y
RUN cd /opt/testapp && pip install -r requirements.txt

EXPOSE 80

CMD cd /opt/testapp && python server.py
"""

        with open(redis_dockerfile) as fp:
            self.assertEqual(expected_redis_df, fp.read())
        with open(testapp_dockerfile) as fp:
            self.assertEqual(expected_testapp_df, fp.read())


class TestGetRelations(unittest.TestCase):

    """Tests for :func:`chessboard.providers.docker._get_relations`."""

    def test_unknown_remote_service(self):
        """Error case where a relation refers to an unkown remote service."""
        checkmatefile = six.StringIO("""
            components:
              - name: testapp
                files:
                  - source: .
                    dest: /opt/testapp
                commands:
                  install: |
                    apt-get update
                    apt-get install python-pip -y
                    cd /opt/testapp && pip install -r requirements.txt
                  start: "cd /opt/testapp && python server.py"
                provides:
                  - resource_type: application
                    interface: http
                    port:
                      default: 80
                requires:
                  - resource_type: compute
                    relation: host
                    interface: linux
                    constraints:
                      - setting: os
                        value: ubuntu 14.04
            blueprint:
              services:
                testapp:
                  component:
                    # component is defined somewhere else
                    name: testapp
                  relations:
                    - service: reddis  # this should raise an error
                      interface: redis
                redis:
                  component:
                     name: redis""")
        contents = parser.load(checkmatefile)
        with self.assertRaises(docker.TopologyError) as ar:
            docker._get_relations(contents)
        self.assertEqual(
            "Service 'testapp' defines a relation to an unknown remote service"
            " 'reddis'.",
            str(ar.exception)
        )

    def test_typical(self):
        """Typical case of extracting validation relation info."""
        checkmatefile = six.StringIO("""
            components:
              - name: testapp
                files:
                  - source: .
                    dest: /opt/testapp
                commands:
                  install: |
                    apt-get update
                    apt-get install python-pip -y
                    cd /opt/testapp && pip install -r requirements.txt
                  start: "cd /opt/testapp && python server.py"
                provides:
                  - resource_type: application
                    interface: http
                    port:
                      default: 80
                requires:
                  - resource_type: compute
                    relation: host
                    interface: linux
                    constraints:
                      - setting: os
                        value: ubuntu 14.04
            blueprint:
              services:
                testapp:
                  component:
                    # component is defined somewhere else
                    name: testapp
                  relations:
                    - service: redis
                      interface: redis
                redis:
                  component:
                     name: redis""")
        contents = parser.load(checkmatefile)
        relations = docker._get_relations(contents)
        expected = {
            'testapp': [docker.Relation(service='redis', interface='redis')]
        }
        self.assertEqual(expected, relations)
