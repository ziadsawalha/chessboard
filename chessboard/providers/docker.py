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

from collections import namedtuple
import os
import shutil
import subprocess
import tempfile

import yaml

from chessboard.components import catalog as cb_catalog
from chessboard import parser

Relation = namedtuple('Relation', ['service', 'interface'])

DOCKERFILE_TEMPLATE = """\
FROM %(distro)s:%(distro_version)s

%(add_section)s

%(run_section)s

%(expose_section)s

CMD %(cmd)s
"""


class TopologyError(Exception):

    """Basic exception type for errors related to :class:`Topology`."""


class DockerProvider(object):

    """Launch application deployments from a Checkmatefile using Docker.

    Uses docker-compose to create links between application components, as well
    as to handle most of the work in creating the containers.
    """

    def __init__(self, working_dir=None):
        """Constructor.

        :param str working_dir:
            Specify the base working directory for launching an application
            deployment on Docker. If not specified, ``working_dir`` defaults
            to the current working directory (cwd).

            It most cases, the ``working_dir`` would be the root of a source
            code repo which contains a Checkmatefile.
        """
        # TODO(larsbutler): Make sure DOCKER_HOST envvar is set
        # If not, raise a warning.
        self.catalog = None
        self.working_dir = working_dir or os.getcwd()

    def _generate_docker_artifacts(self, cmfile, tempdir, custom_components):
        """Write Dockerfiles and a docker-compose.yml file to ``tempdir``.

        These files are meant to be ephemeral for the time being, although in
        the future we may want to output them to a more permanent for debugging
        or further reuse.

        :param cmfile:
            Parsed contents of a Checkmatefile, in object form.
        :param str tempdir:
            Temporary working dir into which this method will write Docker
            artifacts.
        :param custom_components:
            A `dict` of :class:`chessboard.components.catalog.Component`
            objects, keyed by component name. These are loaded from the
            Checkmatefile.
        """
        # key: component name/docker service
        # value: dir of dockerfile
        dockerfile_dirs = {}
        # Create Dockerfiles for each component (both custom components and
        # those components from the catalog).
        for comp in cmfile['components']:
            comp_name = comp['name']
            comp_path = os.path.join(tempdir, 'docker', comp_name)
            os.makedirs(comp_path)
            dockerfile_path = os.path.join(comp_path, 'Dockerfile')
            with open(dockerfile_path, 'w') as dockerfile:
                dockerfile.write(_component_to_dockerfile(comp))
            dockerfile_dirs[comp_name] = comp_path
        # Now generate docker-compose.yml
        relations = _get_relations(cmfile)
        docker_compose_obj = _make_docker_compose(
            cmfile, dockerfile_dirs, relations
        )

        # Copy application source code into custom component directories,
        # so the Dockerfile can find the code during build (if needed).

        # FIXME(larsbutler): This could be expensive if the application
        # code is large. One possible solution may be to re-arrange the
        # file structure in the `tempdir` and use symlinks to avoid
        # copying.
        for comp_name, df_dir in dockerfile_dirs.items():
            if comp_name in custom_components:
                shutil.copytree(self.working_dir,
                                os.path.join(df_dir, 'src'))

        # TODO(larsbutler): Environment variables, particularly for
        # host/port details of relations, needed to be added at some point.
        docker_compose_path = os.path.join(tempdir, 'docker-compose.yml')
        with open(docker_compose_path, 'w') as docker_compose_file:
            yaml.dump(docker_compose_obj, docker_compose_file,
                      default_flow_style=False)

    def launch(self, checkmatefile, tempdir=tempfile.mkdtemp()):
        """Launch an application from a Checkmatefile.

        :param checkmatefile:
            File-like object containing the contents of a Checkmatefile.
        :param tempdir:
            Temporary directory for storing intermediate Docker artifacts.
            If none is specified, one will be generated.
        """
        cmfile = parser.load(checkmatefile)
        custom_components = _get_custom_components(cmfile)
        default_catalog = cb_catalog.get_default_catalog()

        # Load components from the default catalog and add them to the
        # Checkmatefile
        _include_components(cmfile, default_catalog)
        # Switch to the tempdir where we wrote the files and execute
        # docker-compose commands to launch the app.
        # NOTE(larsbutler): Unfortunately, `docker-compose` isn't written to be
        # used like a library (sad face), so the best we can do is execute
        # commands directly.
        old_dir = os.getcwd()
        try:
            # Generate docker artifacts for all components, including those
            # from those components from the default catalog as well as the
            # custom components which are defined in the Checkmatefile itself.
            self._generate_docker_artifacts(cmfile, tempdir, custom_components)

            os.chdir(tempdir)

            subprocess.check_call("docker-compose build --no-cache".split())
            subprocess.check_call("docker-compose up -d".split())
        finally:
            os.chdir(old_dir)
            shutil.rmtree(tempdir)


def _get_os(component):
    """Get the `os` constraint from a `Component`.

    :param component:
        :class:`chessboard.components.catalog.Component` object.

    :returns:
        The OS (operating system) chosen by the ``component``, or `None` if
        there is no OS constraint specified.
    """
    requires_constraints = [x for x in component['requires']]
    for rc in requires_constraints:
        # look for os
        for constraint in rc['constraints']:
            if constraint.get('setting') == 'os':
                return constraint.get('value')
    # TODO(larsbutler): what if multiple constraints specify os, twice?
    # and with conflicting values?
    # TODO(larsbutler): what if there is no os? Do we need it?


def _component_to_dockerfile(component, src_dir_prefix='src'):
    """Convert a `Component` object to a Dockerfile.

    :param component:
        :class:`chessboard.components.catalog.Component` object.

    :returns:
        Dockerfile contents representing this component, as a string.
    """
    # TODO(larsbutler): Perform a simple validation on the os value.
    distro, distro_version = _get_os(component).split()
    distro = distro.lower()

    #############
    # ADD section
    def fix_src(src):
        if not src_dir_prefix:
            # no change
            return src

        if not os.path.isabs(src):
            # We need to traverse up a few dirs to find our source code.
            return os.path.join(src_dir_prefix, src)
        return src

    files = component.get('files') or []
    add_section = '\n'.join(
        'ADD ["%(src)s", "%(dest)s"]' % dict(
            src=fix_src(eachfile['source']), dest=eachfile['dest']
        )
        for eachfile in files
    )

    #############
    # RUN section
    # TODO(larsbutler): this could be a list of commands
    run_cmd = component['commands']['install']
    run_cmds = run_cmd.split('\n')
    run_section = '\n'.join('RUN %s' % cmd
                            for cmd in run_cmds
                            # filter empty lines/strings
                            if cmd)

    ################
    # EXPOSE section
    # figure out which ports we need to expose
    ports = [(x.get('port') or {}).get('default')
             for x in component['provides']]
    # filter out Nones
    ports = [x for x in ports if x is not None]
    expose_section = '\n'.join('EXPOSE %s' % port for port in ports)

    cmd = component['commands']['start']

    rendered = DOCKERFILE_TEMPLATE % dict(
        distro=distro,
        distro_version=distro_version,
        add_section=add_section,
        run_section=run_section,
        expose_section=expose_section,
        cmd=cmd,
    )
    return rendered


def _get_custom_components(cmfile):
    """Get custom components defined in a Checkmatefile.

    :param cmfile:
        Parsed Checkmatefile contents, in object form.

    :returns:
        A `dict` of the :class:`chessboard.components.catalog.Component`
        objects, keyed by component name.
    """
    custom = {}
    comps = cmfile.get('components') or []
    for comp in comps:
        custom[comp['name']] = comp

    return custom


def _include_components(cmfile, catalog):
    """Modify ``cmfile`` to include (in-line) components from a catalog.

    :param cmfile:
        Checkmatefile contents as a `dict`.
    :param dict catalog:
        Default catalog of :class:`chessboard.components.catalog.Component`
        objects, as a `dict`, keyed by the component name.
    """
    services = cmfile['blueprint']['services']
    components = cmfile['components']

    for svc_name, svc in services.items():
        svc_component = svc['component']

        # FIXME(larsbutler): Assume for now that component selector is "name".
        # We need to expand this to include others.
        assert 'name' in svc_component
        svc_selector = svc_component['name']

        # Was a component by this name included in the `components` section of
        # the Checkmatefile?
        # If so, it should override a component of the same name that would
        # otherwise come from the catalog.
        # For example, if the catalog contains a generic component with the
        # name `redis`, a Checkmatefile may define a custom component with the
        # name `redis` to _override_ this component.
        def components_has(name):
            for comp in components:
                if comp['name'] == name:
                    return True
            return False

        if not components_has(svc_selector):
            # No custom component by this name was included in the
            # Checkmatefile.
            # Try to get it from the catalog.
            catalog_component = catalog.get(svc_selector)
            if catalog_component is None:
                # TODO(larsbutler): Use another error type.
                # Component is not in the Checkmatefile, nor is it in the
                # catalog.
                raise RuntimeError(
                    "Component '%s' could not be resolved." % svc_selector
                )
            else:
                # components[svc_selector] = catalog_component
                components.append(catalog_component)


def _get_relations(cmfile):
    """Parse relations from the `services` defined in the Checkmatefile.

    :param cmfile:
        Parsed Checkmatefile contents, in object form.

    :returns:
        `dict` of relation information. Keys are the name of a service which
        relates to one or more other services, and values are lists of
        :class:`Relation` namedtuples, which define the remote service and
        remote interface.
    """
    relations = {}
    services = cmfile['blueprint']['services']

    for service_name, service in services.items():
        if service.get('relations'):
            svc_relations = []
            for relat in service.get('relations'):
                remote_service = relat['service']
                remote_interface = relat['interface']
                if remote_service not in services:
                    # The remote service we want to connect to doesn't
                    # exist.
                    raise TopologyError(
                        "Service '%(sn)s' defines a relation to an unknown"
                        " remote service '%(rs)s'."
                        % dict(sn=service_name, rs=remote_service)
                    )
                else:
                    # The remote service exists.
                    # This is all we check for now; later in the pipeline,
                    # we will need to check that the interfaces match, as
                    # well as define in more detail the nature of the
                    # relations between actual instances of resources in
                    # a given deployment.
                    rel = Relation(remote_service, remote_interface)
                    svc_relations.append(rel)
            relations[service_name] = svc_relations
    return relations


def _make_docker_compose(cmfile, dockerfile_dirs, relations):
    """Build a dictionary of docker-compose file contents.

    These contents are meant to be dumped into a yaml file.

    :param cmfile:
        Parsed contents of a Checkmatefile, in object form.
    :param dict dockerfile_dirs:
        `dict` of Dockerfile directories, keyed by the service name.
    :param relations:
        Relation information required to "wire up" services. Relation info
        should come from :func:`_get_relations`, or at least be in the same
        format.

    :returns:
        `dict` containing the data to dump to a docker-compose.yml file,
        including `links`, `build` info, and `ports`.
    """
    dc = {}

    components = cmfile['components']
    for comp in components:
        service = comp['name']
        df_dir = dockerfile_dirs[service]

        svc_contents = {
            'build': df_dir,
            # 'links': [],
            'ports': [],
        }
        # Links:
        if service in relations:
            # we have links to make:
            svc_contents['links'] = [r.service for r in relations[service]]

        # Ports:
        for prov in comp['provides']:
            svc_contents['ports'].append(str(prov['port']['default']))

        dc[service] = svc_contents
    return dc
