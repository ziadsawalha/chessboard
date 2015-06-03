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

"""Classes and utilities for modeling and handling application deployments."""

from __future__ import print_function

import logging

from chessboard.topology import Topology
from chessboard import classes
from chessboard.constraints import Constraint
from chessboard.environment import Environment
from chessboard import exceptions
from chessboard import functions
from chessboard.inputs import Input
from chessboard import schema
from chessboard import utils

LOG = logging.getLogger(__name__)


class Deployment(classes.ExtensibleDict):

    """."""

    __schema__ = schema.DEPLOYMENT_SCHEMA

    def __init__(self, *args, **kwargs):
        """Create a new Deployment."""
        super(Deployment, self).__init__(*args, **kwargs)

    @staticmethod
    def from_checkmate_file(checkmate_file):
        """Generate a `Deployment` object from a Checkmatefile.

        :param Checkmatefile:
            Checkmatefile contents, parsed and validated
            using, for example, :func:`chessboard.parser.load`.

        :returns:
            A :class:`Deployment` instance.
        """
        contents = checkmate_file.copy()
        if 'id' not in contents:
            contents['id'] = utils.generate_id()
        contents.setdefault('status', 'NEW')
        return Deployment(contents)

    @property
    def resources(self):
        """Return the resources the deployment is managing."""
        return self.setdefault('resources', {})

    @property
    def inputs(self):
        """Return the inputs the deployment is managing."""
        return self.setdefault('inputs', {})

    @property
    def topology(self):
        """Return the topology of the deployment if it exists."""
        return Topology.from_deployment(self)

    @property
    def blueprint(self):
        """Return the topology of the deployment if it exists."""
        return self.topology

    @property
    def environment(self):
        """Return the environment of the deployment if it exists."""
        return Environment.from_deployment(self)

    def validate_options(self):
        """Validate blueprints options.

        - Check that blueprint options marked 'required' are supplied.
        - Check that url-type options are valid

        Raise error if not.
        """
        for key, option in self.get('options', {}).iteritems():
            self.check_option_required(key, option)
            self.check_option_url(key, option)

    def check_option_url(self, key, option):
        """Check that URL option has consistent cert info."""
        inputs = self.get('inputs', {})
        bp_inputs = inputs.get('blueprint', {})

        if option.get('type') == 'url':
            value = bp_inputs.get(key)
            if isinstance(value, dict):
                if 'private_key' in value and 'certificate' not in value:
                    msg = ("If a private key is supplied for '%s', then a "
                           "certificate is also required" % key)
                    raise exceptions.CheckmateValidationException(msg)
                if 'certificate' in value and 'private_key' not in value:
                    raise exceptions.CheckmateValidationException(
                        "If a certificate is supplied for '%s', then a "
                        "private key is also required" % key)
                if 'intermediate_key' in value and (
                        'private_key' not in value or
                        'certificate' not in value):
                    raise exceptions.CheckmateValidationException(
                        "If an intermediate key is supplied for '%s', then a "
                        "certificate and private key are also required" % key)

    def check_option_required(self, key, option):
        """Check that if an option is required, then it has a value."""
        inputs = self.get('inputs', {})
        bp_inputs = inputs.get('blueprint', {})
        if 'default' in option:
            return True
        if 'required' not in option:
            return True
        required = option['required']
        if isinstance(required, dict):
            required = functions.evaluate(
                required,
                options=self.get('blueprint', {}).get('options'),
                services=self.get('blueprint', {}).get('services'),
                resources=self.get('resources'),
                inputs=inputs
            )
        if required:
            if key not in bp_inputs:
                raise exceptions.CheckmateValidationException(
                    "Required blueprint input '%s' not supplied" % key)

    def validate_input_constraints(self):
        """Check that inputs meet the option constraint criteria.

        Raise error if not
        """
        blueprint = self.blueprint
        if 'options' in blueprint:
            options = blueprint['options']
            inputs = self.get('inputs', {})
            bp_inputs = inputs.get('blueprint', {})
            services = self.get('blueprint', {}).get('services')
            resources = self.get('resources')
            for key, option in options.iteritems():
                constraints = option.get('constraints')
                if constraints:
                    value = bp_inputs.get(key, option.get('default'))

                    # Handle special defaults
                    if utils.is_evaluable(value):
                        value = utils.evaluate(value[1:])

                    if value is None:
                        continue  # don't validate null inputs

                    for entry in constraints:
                        parsed = functions.parse(
                            entry,
                            options=options,
                            services=services,
                            resources=resources,
                            inputs=inputs)
                        constraint = Constraint.from_constraint(parsed)
                        if not constraint.test(Input(value)):
                            msg = ("The input for option '%s' did not pass "
                                   "validation. The value was '%s'. The "
                                   "validation rule was %s" %
                                   (key,
                                    value if option.get('type') != 'password'
                                    else '*******',
                                    constraint.message))
                            raise exceptions.CheckmateValidationException(msg)


    def get_setting(self, name, resource_type=None, service_name=None,
                    provider_key=None, relation=None, default=None):
        """Find a value that an option was set to.

        Look in this order:
        - start with the deployment inputs where the paths are:
            inputs/blueprint
            inputs/providers/:provider
            etc
        - global inputs
        - environment settings (generated at planning time)
        - resources (generated during deployment)
        - finally look at the component defaults

        :param name: the name of the setting
        :param service: the name of the service being evaluated
        :param resource_type: the type of the resource being evaluated (ex.
                compute, database)
        :param default: value to return if no match found
        """
        if not name:
            raise exceptions.CheckmateValidationException(
                "setting() was called with a blank value. Check your map "
                "file for bad calls to 'setting'"
            )
        if relation:
            result = self._get_svc_relation_attribute(name, service_name,
                                                      relation)
            if result is not None:
                LOG.debug(
                    "Setting '%s' matched in _get_svc_relation_attribute", name
                )
                return result
        if service_name:
            result = self._get_input_service_override(
                name, service_name, resource_type=resource_type)
            if result is not None:
                LOG.debug(
                    "Setting '%s' matched in _get_input_service_override", name
                )
                return result

            result = self._check_services_constraints(name, service_name)
            if result is not None:
                LOG.debug("Setting '%s' matched in "
                          "_check_services_constraints", name)
                return result

        if provider_key:
            result = self._get_input_provider_option(
                name, provider_key, resource_type=resource_type)
            if result is not None:
                LOG.debug(
                    "Setting '%s' matched in _get_input_provider_option", name
                )
                return result

        result = self._check_resources_constraints(
            name, service_name=service_name, resource_type=resource_type)
        if result is not None:
            LOG.debug("Setting '%s' matched in "
                      "_check_resources_constraints", name)
            return result

        result = self._check_options_constraints(
            name, service_name=service_name, resource_type=resource_type)
        if result is not None:
            LOG.debug("Setting '%s' matched in "
                      "_check_options_constraints", name)
            return result

        result = self._get_input_simple(name)
        if result is not None:
            LOG.debug("Setting '%s' matched in _get_input_simple", name)
            return result

        result = self._get_input_global(name)
        if result is not None:
            LOG.debug("Setting '%s' matched in _get_input_global", name)
            return result

        result = self._get_env_provider_constraint(
            name, provider_key, resource_type=resource_type)
        if result is not None:
            LOG.debug("Setting '%s' matched in "
                      "_get_env_provider_constraint", name)
            return result

        result = self._get_env_provider_constraint(
            name, 'common', resource_type=resource_type)
        if result is not None:
            LOG.debug("Setting '%s' matched 'common' setting in "
                      "_get_env_provider_constraint", name)
            return result

        result = self._get_resource_setting(name)
        if result is not None:
            LOG.debug("Setting '%s' matched in _get_resource_setting", name)
            return result

        result = self._get_setting_value(name)
        if result is not None:
            LOG.debug("Setting '%s' matched in _get_setting_value", name)
            return result

        LOG.debug("Setting '%s' unmatched with resource_type=%s, service=%s, "
                  "provider_key=%s and returning default '%s'", name,
                  resource_type, service_name, provider_key, default)
        return default

    def _get_resource_setting(self, name):
        """Get a value from resources with support for paths."""
        if name:
            node = self.get("resources", {})
            for key in name.split("/"):
                if key in node:
                    try:
                        node = node[key]
                    except TypeError:
                        return None
                else:
                    return None
            return node

    def _get_setting_by_resource_path(self, path, default=None):
        """Read a setting that constrains a static resource by path name.

        The name must be resources/:resource_key/:setting
        """
        # FIXME: we need to confirm if we want this as part of the DSL
        blueprint = self['blueprint']
        if 'options' in blueprint:
            options = blueprint['options']
            for key, option in options.iteritems():
                if 'constrains' in option:
                    constraints = self.parse_constraints(option['constrains'])
                    for constraint in constraints:
                        if self.constraint_applies(constraint, path):
                            result = self._apply_constraint(path, constraint,
                                                            option=option,
                                                            option_key=key)
                            if result is not None:
                                LOG.debug("Found setting '%s' from constraint."
                                          " %s=%s", path, key, result)
                                return result
        return default

    def _get_setting_value(self, name):
        """Get a value from the deployment hierarchy with support for paths.

        But does not allow root items.
        """
        if name and isinstance(name, basestring) and '/' in name:
            node = self
            for key in name.split("/"):
                if key in node:
                    try:
                        node = node[key]
                    except TypeError:
                        return None
                else:
                    return None
            return node

    def _get_input_global(self, name):
        """Get a setting directly under inputs."""
        inputs = self.inputs
        if name in inputs:
            result = inputs[name]
            LOG.debug("Found setting '%s' in inputs. %s=%s",
                      name, name, result)
            return result

    def _get_input_simple(self, name):
        """Get a setting directly from inputs/blueprint."""
        inputs = self.inputs
        if 'blueprint' in inputs:
            blueprint_inputs = inputs['blueprint']
            # Direct, simple entry
            if name in blueprint_inputs:
                result = blueprint_inputs[name]
                LOG.debug("Found setting '%s' in inputs/blueprint. %s=%s",
                          name, name, result)
                return result

    def _check_options_constraints(self, name, service_name=None,
                                   resource_type=None):
        """Get a setting implied through blueprint option constraint.

        :param name: the name of the setting
        :param service_name: the name of the service being evaluated
        :param resource_type: the resource type to match the constraint with
        """
        blueprint = self['blueprint']
        if 'options' in blueprint:
            options = blueprint['options']
            for key, option in options.iteritems():
                if 'constrains' in option:  # the verb 'constrains' (not noun)
                    constraints = self.parse_constraints(option['constrains'])
                    for constraint in constraints:
                        if self.constraint_applies(
                                constraint, name, service_name=service_name,
                                resource_type=resource_type):
                            result = self._apply_constraint(name, constraint,
                                                            option=option,
                                                            option_key=key)
                            if result is not None:
                                LOG.debug("Found setting '%s' from constraint."
                                          " %s=%s", name, name, result)
                                return result

    def _check_resources_constraints(self, name, service_name=None,
                                     resource_type=None):
        """Get a setting implied through a static resource constraint.

        :param name: the name of the setting
        :param service_name: the name of the service being evaluated
        :param resource_type: the type of the resource being evaluated
        """
        blueprint = self['blueprint']
        if 'resources' in blueprint:
            resources = blueprint['resources']
            for key, resource in resources.iteritems():
                if 'constrains' in resource:
                    constraints = resource['constrains']
                    constraints = self.parse_constraints(constraints)
                    for constraint in constraints:
                        if self.constraint_applies(
                                constraint, name, service_name=service_name,
                                resource_type=resource_type):
                            instance = self['resources'][key]['instance']
                            result = self._apply_constraint(name, constraint,
                                                            resource=instance)
                            if result is not None:
                                LOG.debug("Found setting '%s' from constraint "
                                          "in blueprint resource '%s'. %s=%s",
                                          name, key, name, result)
                                return result

    def _get_svc_relation_attribute(self, name, service_name, relation_to):
        """Get a setting implied through a blueprint service attribute.

        :param name: the name of the setting
        :param service_name: the name of the service being evaluated
        :param relation_to: the name of the service ot which the service_name
        is related
        """
        blueprint = self['blueprint']
        if 'services' in blueprint:
            services = blueprint['services']
            service = services.get(service_name, None)
            if service:
                if 'relations' in service:
                    relations = service['relations']
                    for relation in relations:
                        relation_key = relation['key']
                        if (relation_key == relation_to or
                                relation.get('service', None) == relation_to):
                            attributes = relation.get('attributes', None)
                            if attributes:
                                for attrib_key, attribute \
                                        in attributes.iteritems():
                                    if attrib_key == name:
                                        LOG.debug(
                                            "Found setting '%s' as a service "
                                            "attribute in service '%s'. %s=%s",
                                            name, service_name,
                                            name, attribute)
                                        return attribute

    def _check_services_constraints(self, name, service_name):
        """Get a setting implied through a blueprint service constraint.

        :param name: the name of the setting
        :param service_name: the name of the service being evaluated
        """
        blueprint = self['blueprint']
        if 'services' in blueprint:
            services = blueprint['services']
            service = services.get(service_name, None)
            if service is not None:
                # Check constraints under service
                if 'constraints' in service:
                    constraints = service['constraints']
                    constraints = self.parse_constraints(constraints)
                    for constraint in constraints:
                        if name == constraint['setting']:
                            result = self._apply_constraint(name, constraint)
                            LOG.debug("Found setting '%s' as a service "
                                      "constraint in service '%s'. %s=%s",
                                      name, service_name, name, result)
                            return result
                # Check constraints under component
                if 'component' in service:
                    if service['component'] is not None:
                        if 'constraints' in service['component']:
                            constraints = service['component']['constraints']
                            constraints = self.parse_constraints(constraints)
                            for constraint in constraints:
                                if name == constraint['setting']:
                                    result = self._apply_constraint(name,
                                                                    constraint)
                                    LOG.debug("Found setting '%s' as a "
                                              "service comoponent constraint "
                                              "in service '%s'. %s=%s", name,
                                              service_name, name, result)
                                    return result

    @staticmethod
    def parse_constraints(constraints):
        """Ensure constraint syntax is valid.

        If it is key/values, convert it to a list.
        If the list has key/values, convert them to the expected format with
        setting, service, etc...
        """
        constraint_list = []
        if isinstance(constraints, list):
            constraint_list = constraints
        elif isinstance(constraints, dict):
            LOG.warning("Constraints not a list: %s", constraints)
            for key, value in constraints.iteritems():
                constraint_list.append({'setting': key,
                                        'value': value})
        parsed = []
        for constraint in constraint_list:
            if len(constraint) == 1 and constraint.keys()[0] != 'setting':
                # it's one key/value pair which is not 'setting':path
                # Convert setting:value to full constraint syntax
                parsed.append({'setting': constraint.keys()[0],
                               'value': constraint.values()[0]})
            else:
                parsed.append(constraint)

        return parsed

    @staticmethod
    def constraint_applies(constraint, name, resource_type=None,
                           service_name=None):
        """Check if a constraint applies.

        :param constraint: the constraint dict
        :param name: the name of the setting
        :param resource_type: the resource type (ex. compute)
        :param service_name: the name of the service being evaluated
        """
        if 'resource_type' in constraint:
            if resource_type is None or \
                    constraint['resource_type'] != resource_type:
                return False
        if 'setting' in constraint:
            if constraint['setting'] != name:
                return False
        if 'service' in constraint:
            if service_name is None or constraint['service'] != service_name:
                return False
        if 'resource' in constraint:
            if resource_type is None or \
                    constraint['resource'] != resource_type:
                return False
        LOG.debug("Constraint '%s' for '%s' applied to '%s/%s'",
                  constraint, name, service_name or '*', resource_type or '*')
        return True

    def _apply_constraint(self, name, constraint, option=None, resource=None,
                          option_key=None):
        """Return the value of the option applying any constraint definitions.

        :param name: the name of the option we are seeking
        :param constraint: the dict of any constraint used to find the option
        :param option: the option being evaluated
        :param resource: the resource the constraint is applied to
        :param option_key: the key of the option the constraint is coming from
        """
        # Return the value if it is explicitely assigned in the constraint
        if 'value' in constraint:
            return constraint['value']

        # Find the value
        value = None
        if resource:
            # use the resource as the value if the constraint has a resource
            value = resource
        else:
            if option_key:
                value = self._get_input_simple(option_key)
            if value is None and option and 'default' in option:
                value = option.get('default')
                LOG.debug("Default setting '%s' obtained from constraint "
                          "in blueprint input '%s': default=%s",
                          name, option_key, value)

        # objectify the value it if it is a typed option

        if option and 'type' in option and not resource:
            value = self._objectify(option, value)

        # If the constraint has an attribute specified, get that attribute

        if 'attribute' in constraint:
            attribute = constraint['attribute']

            if value is not None:
                result = None
                if isinstance(value, cm_inputs.Input):
                    if hasattr(value, attribute):
                        result = getattr(value, attribute)
                elif isinstance(value, collections.Mapping):
                    if attribute in value:
                        result = value[attribute]
                else:
                    error_message = "Could not read attribute '%s' while " \
                                    "obtaining option '%s' since value is " \
                                    "of type %s" % (attribute, name,
                                                    type(value).__name__)
                    raise exceptions.CheckmateException(
                        error_message,
                        friendly_message=exceptions.BLUEPRINT_ERROR)
                if result is not None:
                    LOG.debug("Found setting '%s' from constraint. %s=%s",
                              name, option_key or name, result)
                    return result

        if value is not None:
            LOG.debug("Found setting '%s' from constraint in blueprint input "
                      "'%s'. %s=%s", name, option_key, option_key, value)
            return value

    @staticmethod
    def _objectify(option, value):
        """Parse option based on type into an object of that type."""
        if 'type' not in option:
            return value
        if option['type'] == 'url':
            result = cm_inputs.Input(value)
            if isinstance(value, basestring):
                result.parse_url()
            return result
        else:
            return value

    def _get_input_service_override(self, name, service_name,
                                    resource_type=None):
        """Get a setting applied through a deployment setting on a service.

        Params are ordered similar to how they appear in yaml/json::
            inputs/services/:id/:resource_type/:option-name

        :param service_name: the name of the service being evaluated
        :param resource_type: the resource type (ex. compute)
        :param name: the name of the setting
        """
        inputs = self.inputs
        if 'services' in inputs:
            services = inputs['services']
            if service_name in services:
                service_object = services[service_name]
                if resource_type in service_object:
                    options = service_object[resource_type]
                    if name in options:
                        result = options[name]
                        LOG.debug("Found setting '%s' as service setting "
                                  "in blueprint/services/%s/%s'. %s=%s", name,
                                  service_name, resource_type, name, result)
                        return result

    def _get_input_provider_option(self, name, provider_key,
                                   resource_type=None):
        """Get a setting applied through a deployment setting to a provider.

        Params are ordered similar to how they appear in yaml/json::
            inputs/providers/:id/[:resource_type/]:option-name

        :param name: the name of the setting
        :param provider_key: the key of the provider in question
        :param resource_type: the resource type (ex. compute)
        """
        inputs = self.inputs
        if 'providers' in inputs:
            providers = inputs['providers']
            if provider_key in providers:
                provider = providers[provider_key] or {}
                if resource_type in provider:
                    options = provider[resource_type]
                    if options and name in options:
                        result = options[name]
                        LOG.debug("Found setting '%s' as provider setting in "
                                  "blueprint/providers/%s/%s'. %s=%s", name,
                                  provider_key, resource_type, name, result)
                        return result

    def _get_env_provider_constraint(self, name, provider_key,
                                     resource_type=None):
        """Apply a setting.

        Apply a setting through a provider constraint in the
        environment

        :param name: the name of the setting
        :param provider_key: the key of the provider in question
        :param resource_type: the resource type (ex. compute)
        """
        environment = self.environment
        providers = environment.providers
        if provider_key in providers:
            provider = providers[provider_key] or {}
            constraints = provider.get('constraints', [])
            assert isinstance(constraints, list), ("constraints need to be a "
                                                   "list or array")
            constraints = self.parse_constraints(constraints)
            for constraint in constraints:
                if self.constraint_applies(constraint, name,
                                           resource_type=resource_type):
                    result = self._apply_constraint(name, constraint)
                    LOG.debug("Found setting '%s' as a provider constraint in "
                              "the environment for provider '%s'. %s=%s",
                              name, provider_key, name, result)
                    return result

    def _constrained_to_one(self, service_name):
        """Return true if a service is constrained to 1, false otherwise.

        Example:

            blueprint:
              [...]
              services:
                [...]
                master:
                  [...]
                  constraints:
                  - count: 1
                  [...]
        """
        blueprint_resource = self['blueprint']['services'][service_name]
        if 'constraints' in blueprint_resource:
            for constraint in blueprint_resource['constraints']:
                if 'count' in constraint:
                    if constraint['count'] == 1:
                        return True
        return False

    def create_resource_template(self, index, definition, service_name,
                                 context, planner):
        """Create a new resource dict to add to the deployment.

        :param index: the index of the resource within its service (ex. web2)
        :param definition: the component definition coming from the Plan
        :param context: RequestContext (auth token, etc) for catalog calls

        :returns: a validated dict of the resource ready to add to deployment
        """
        # Call provider to give us a resource template
        provider_key = definition['provider']
        provider = self.environment.get_provider(provider_key)
        component = provider.get_component(definition['id'])
        # TODO(any): Provider key can be used from within the provider class.
        # But if we do that then the planning mixin will start reading data
        # from the child class
        LOG.debug("Getting resource templates for %s: %s", provider_key,
                  component)
        resources = provider.generate_template(
            self,
            component.resource_type,
            service_name,
            context,
            index,
            provider.key,
            definition,
            planner
        )
        for resource in resources:
            resource.setdefault('component', definition['id'])
            resource.setdefault('status', "NEW")
            resource.setdefault('desired-state', {})
            #cm_res.Resource.validate(resource)
        return resources
