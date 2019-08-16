# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

###############################################################################
#
#  How to test APIs using curl:
#
#  #!/bin/bash
#
#  TRYTON_URL=http://127.0.0.1:8000/db_name/
#  LOGIN=admin
#  LOGIN_ID=1
#  PASSWORD=admin
#
#  CALL_ID=1
#
#  LOGIN_DATA="{\"id\":$CALL_ID,\"method\":\"common.db.login\","
#  LOGIN_DATA+="\"params\":[\"$LOGIN\",{\"password\": \"$PASSWORD\"},\"fr\"]}"
#  LOGIN_RESPONSE=$(curl --silent -X POST $TRYTON_URL \
#      -H "Content-Type: application/json" \
#      --data "$LOGIN_DATA")
#
#  SESSION="$(echo "$LOGIN_RESPONSE" | sed 's/.*"\(.*\)"]}/\1/')"
#  AUTHORIZATION="$(printf "%s:%s:%s" "$LOGIN" "$LOGIN_ID" "$SESSION")"
#  AUTHORIZATION="$(printf "$AUTHORIZATION" | base64 -w 0)"
#
#  API_NAME="model.api.core.list_apis"
#  API_PARAMS="[{}, {}, {}]"
#  API_DATA="{\"id\": $CALL_ID, \"method\": \"$API_NAME\","
#  API_DATA+="\"params\": $API_PARAMS}"
#  curl -X POST $TRYTON_URL \
#      -H "Content-Length: ${#API_DATA}" \
#      -H "Authorization: Session $AUTHORIZATION" \
#      -H "Content-Type: application/json" \
#      --data "$API_DATA"
#
###############################################################################

# Fastest json schema parsing using
# https://www.peterbe.com/plog/jsonschema-validate-10x-faster-in-python
import logging
import fastjsonschema
import datetime

from decimal import Decimal, InvalidOperation
from contextlib import contextmanager

from trytond.pool import Pool
from trytond.model import Model, ModelStorage
from trytond.transaction import Transaction
from trytond.config import config
from trytond.rpc import RPC
from trytond.server_context import ServerContext


DEFAULT_INPUT_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    }

DEFAULT_OUTPUT_SCHEMA = {
    'type': 'null',
    }

DATE_SCHEMA = {'type': 'string', 'pattern': r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$'}

AMOUNT_SCHEMA = {'type': 'string', 'pattern': r'^([0-9]{1,}\.)?[0-9]{1,}$'}

RATE_SCHEMA = {'oneOf': [
        {'type': 'string', 'enum': ['1', '1.0', '1.00', '1.000', '1.0000']},
        {'type': 'string', 'pattern': r'^0\.[0-9]{1,4}$'},
        ],
    }


api_logger = logging.getLogger('api')


def DEFAULT_EXAMPLE():
    return [{'input': {}, 'output': None}]


def api_context():
    return ServerContext().get('_api_context', None)


@contextmanager
def api_input_error_manager():
    api_input_errors = []
    with ServerContext().set_context(_api_input_errors=api_input_errors):
        try:
            yield
        finally:
            if api_input_errors:
                raise APIInputError(api_input_errors)


def apify(klass, api_name):
    '''
        Transforms a standard method into an API. This mainly means:
        - calling the appropriate checks / input conversions
        - executing the method
        - handling of errors
    '''
    function = getattr(klass, api_name)
    model_name = klass.__name__

    # re-decorate everytime if needed
    if hasattr(function, '__origin_function'):
        function = getattr(function, '__origin_function', function)
    else:
        # We want to use unbound functions so that the cls is properly set when
        # calling them
        function = function.__func__

    def decorated(parameters, context=None):
        pool = Pool()
        Api = pool.get('api')
        Model = pool.get(model_name)

        # Required for super calls to decorated functions
        transaction_context, api_context, supered = {}, {}, False
        if context is None:
            assert ServerContext().get('_api_context')
            context = {}
            supered = True
        else:
            transaction_context = Api.update_transaction_context(context)
            api_context = {'_api_context': context}
        with Transaction().set_context(**transaction_context):
            with ServerContext().set_context(**api_context):
                try:
                    # We only check / validate for the inital call, not super
                    # calls
                    if not supered:
                        # First error manager for pure validations
                        with api_input_error_manager():
                            Model._check_access(api_name, parameters)
                            parameters = Model._check_input(
                                api_name, parameters)

                        # We only want a (partial) data validation
                        if context.get('_validate', False):
                            return True

                    # Second error manager for the few cases where it either is
                    # not worth to check in the first phase
                    with api_input_error_manager():
                        result = function(Model, parameters)
                    return Api.handle_result(
                        Model, api_name, parameters, result)
                except Exception as e:
                    if (api_logger.isEnabledFor(logging.DEBUG)
                             or config.getboolean('env', 'testing') is True):
                        if context.get('_debug_server', False):
                            raise
                    return Api.handle_error(e)

    decorated.__origin_function = function
    return decorated


def amount_for_api(amount):
    assert isinstance(amount, Decimal)
    return str(amount)


def amount_from_api(amount):
    try:
        return Decimal(amount)
    except InvalidOperation:
        Pool().get('api').add_input_error({
                'type': 'conversion',
                'data': {
                    'input': amount,
                    'target_type': 'Decimal',
                    },
                })


def date_for_api(date):
    assert isinstance(date, datetime.date)
    return date.strftime('%Y-%m-%d')


def date_from_api(date):
    try:
        return datetime.datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        Pool().get('api').add_input_error({
                'type': 'conversion',
                'data': {
                    'input': date,
                    'target_type': 'date',
                    },
                })


class APIError(Exception):
    def format_error(self):
        raise NotImplementedError

    def __eq__(self, value):
        if not isinstance(value, APIError):
            return False
        return self.format_error() == value.format_error()


class APIServerError(APIError):
    '''
        Technical error, a priori not related to user input.
    '''
    def __init__(self, exception):
        self.exception = exception

    def format_error(self):
        return {
            'error_code': 500,
            'error_message': 'Internal Error',
            'error_data': (self.exception.args[0] if self.exception.args
                else 'Unknown Error'),
            }


class APIAuthorizationError(APIError):
    '''
        Will be triggered when trying to access an API a user is not allowed to
    '''
    def __init__(self, api):
        self.api = api
        self.user = Pool().get('res.user')(Transaction().user).rec_name

    def format_error(self):
        return {
            'error_code': 401,
            'error_message': 'Forbidden',
            'error_data': {
                'api_name': self.api,
                'user_name': self.user,
                },
            }


class APIInputError(APIError):
    '''
        Should only be raised during the validation phase.

        "data" should be a list of objects describing the various detected
        validation errors:

            raise APIInputError([{'type': 'json_schema', 'data': ...}])
    '''
    def __init__(self, data):
        self.data = data

    def format_error(self):
        return {
            'error_code': 400,
            'error_message': 'Input Validation Error',
            'error_data': self.data,
            }


class APIUserError(APIError):
    '''
        Used to convert user errors to api errors.

        Ideally, this should never happen, however unless the data validation
        phase is absolutely perfect, it will.
    '''
    def __init__(self, data):
        '''
            This will be an automatically converted error from
            raise_user_error
        '''
        self.data = data

    def format_error(self):
        return {
            'error_code': 400,
            'error_message': 'User Error',
            'error_data': self.data,
            }


class APIErrorHandler(ModelStorage):
    '''
        Overrides Model "raise_user_error" methods to transform user errors
        into api errors
    '''
    @classmethod
    def raise_user_error(cls, errors, error_args=None, error_description='',
            error_description_args=None, raise_exception=True):
        if (raise_exception and api_context() is not None):
            # TODO : investigate why this class is registered (in tests) even
            # when the 'api' module is not installed
            # We must get the api model inside the if because api_context will
            # protect us, but we should not have to
            API = Pool().get('api')
            if errors not in API._blacklisted_errors:
                error_data = {'type': errors}
                new_error_args = {}
                for k, v in (error_args or {}).items():
                    if isinstance(v, Decimal):
                        value = str(v)
                    elif isinstance(v, datetime.date):
                        value = v.strftime('%Y-%m-%d')
                    else:
                        value = v
                    new_error_args[k] = value
                new_error_args['message'] = super().raise_user_error(errors,
                    error_args, error_description, error_description_args,
                    raise_exception=False)
                error_data['data'] = new_error_args
                raise APIUserError(error_data)
        return super().raise_user_error(errors, error_args, error_description,
            error_description_args, raise_exception)


class APIModel(Model):
    '''
        API Model

        This model is designed to hold the functions which are common to all
        (or almost all) APIs. It is not included in the mixin so that we are
        able to override them properly in sub modules.

        It can be used to, for instance, add another authentification layer for
        APIs in a separate module, without having to override all APIs
    '''
    __name__ = 'api'

    # User Errors codes that will be treated as server errors
    _blacklisted_errors = {
        'access_error',
        'delete_xml_record',
        'digits_validation_record',
        'domain_validation_record',
        'foreign_model_exist',
        'foreign_model_missing',
        'read_error',
        'reference_syntax_error',
        'relation_not_found',
        'required_field',
        'required_validation_record',
        'selection_validation_record',
        'size_validation_record',
        'time_format_validation_record',
        'too_many_relations_found',
        'write_xml_record',
        'xml_id_syntax_error',
        }

    @classmethod
    def add_api(cls, Model, name, data):
        '''
            This method transforms a method (identified by the Model on which
            it is defined, and its name) into an API, according to its data
        '''
        # Add the API to the list of allowed RPC calls on the model
        Model.__rpc__.update({
                # The API itself
                name: RPC(
                    readonly=data['readonly'],
                    check_access=False,  # Access rights are managed manually
                    result=lambda x: cls.convert_result(Model, name, x)),
                # Its description
                '%s_description' % name: RPC(readonly=True),
                })

        # Precompute the input jsonschema for the method
        schema_method = getattr(Model, '_%s_schema' % name, None)
        data['input_schema'] = (
            schema_method() if schema_method else DEFAULT_INPUT_SCHEMA)
        data['compiled_input_schema'] = fastjsonschema.compile(
            data['input_schema'])

        # Precompute the input jsonschema for the method
        schema_method = getattr(Model, '_%s_output_schema' % name, None)
        data['output_schema'] = (
            schema_method() if schema_method else DEFAULT_OUTPUT_SCHEMA)
        data['compiled_output_schema'] = fastjsonschema.compile(
            data['output_schema'])

        # Define the validation / conversion method if they exist
        data['convert_input'] = getattr(Model, '_%s_convert_input' %
            name, lambda x: x)
        data['validate_input'] = getattr(
            Model, '_%s_validate_input' % name, lambda x: None)

        # Access policy is used to allow some methods to be accessible to
        # everyone
        data['access_policy'] = (
            'public' if data.get('public', False) else 'restricted')

        # Validate examples, and add them
        data['examples'] = []
        for example in getattr(Model, '_%s_examples' % name, DEFAULT_EXAMPLE)():

            finalize_method = getattr(Model,
                '_%s_example_finalize' % name, None)
            if finalize_method:
                finalize_method(example)
            data['examples'].append(example)

            # Only check for dev environments
            if api_logger.isEnabledFor(logging.DEBUG) and not example.get(
                    'disable_schema_tests', False):
                try:
                    data['compiled_input_schema'](example['input'])
                except fastjsonschema.exceptions.JsonSchemaException:
                    logging.getLogger('api').error(
                        'Invalid input example for api %s.%s' %
                        (cls.__name__, name))
                    raise
                try:
                    data['compiled_output_schema'](example['output'])
                except fastjsonschema.exceptions.JsonSchemaException:
                    logging.getLogger('api').error(
                        'Invalid output example for api %s.%s' %
                        (cls.__name__, name))
                    raise

        # Pre-compute the description (so that retrieving it does not require
        # any computation)
        data['description_complete'] = cls.description_generator(
            Model, name)

        # Create the description method
        setattr(Model, '%s_description' % name,
            lambda: data['description_complete'])

        # Transform the method into an api
        setattr(Model, name, apify(Model, name))

    @classmethod
    def add_input_error(cls, error_data):
        # For now, we will assume that APIs are properly executed with the
        # context manager set
        ServerContext().get('_api_input_errors').append(error_data)

    @classmethod
    def check_access(cls, klass, api_name):
        '''
            Checks whether the current user is authorized to access the API or
            not
        '''
        if klass._apis[api_name]['access_policy'] == 'public':
            return True
        api_string = '%s.%s' % (klass.__name__, api_name)
        if not Pool().get('ir.api.access').check_access(api_string):
            raise APIAuthorizationError(api_string)

    @classmethod
    def check_input(cls, klass, api_name, parameters):
        '''
            Validates and prepares the input for execution.

            Validation can be done via a jsonschema and / or a dedicated
            method. Preparation of the input (type conversions, etc...) can be
            parially performed by jsonschema (defaults) and through another
            dedicated method
        '''
        parameters = cls._check_schema(klass, api_name, parameters)
        parameters = cls._convert_input(klass, api_name, parameters)
        cls._check_validator(klass, api_name, parameters)
        return parameters

    @classmethod
    def _check_schema(cls, klass, api_name, parameters):
        if not klass._apis[api_name]['compiled_input_schema']:
            return parameters
        try:
            return klass._apis[api_name]['compiled_input_schema'](
                parameters)
        except fastjsonschema.exceptions.JsonSchemaException as e:
            # TODO (maybe) if it is performance wise: Use jsonschema in case of
            # failure to list all errors rather than just the first one
            cls.add_input_error({
                    'type': 'json_schema',
                    'data': e.message,
                    })

    @classmethod
    def _convert_input(cls, klass, api_name, parameters):
        return klass._apis[api_name]['convert_input'](parameters)

    @classmethod
    def _check_validator(cls, klass, api_name, parameters):
        klass._apis[api_name]['validate_input'](parameters)

    @classmethod
    def convert_result(cls, klass, api_name, result):
        '''
            Hook to modify the result (whether it's an error or not) of the
            call before it is actually sent back
        '''
        if isinstance(result, APIError):
            return result.format_error()
        return result

    @classmethod
    def description_generator(cls, klass, api_name):
        '''
            The contents that will be send back by the <api_name>_description
            API.

            It is intended to provide a data structure which can easily be
            transformed into a documentation, or just as a helper for
            developers (for instance by giving access to jsonschema for
            pre-validation)
        '''
        return {
            'model': klass.__name__,
            'name': api_name,
            'input_schema': klass._apis[api_name]['input_schema'],
            'output_schema': klass._apis[api_name]['output_schema'],
            'description': klass._apis[api_name]['description'],
            'description_api': '%s_description' % api_name,
            'examples': klass._apis[api_name]['examples'],
            }

    @classmethod
    def handle_error(cls, error):
        '''
            Method that will be called to handle some errors. Could be
            overriden to define a special behaviour for some particular errors
        '''
        if isinstance(error, APIError):
            return error
        # TODO: Trigger sentry if it is available + dump the trace somewhere in
        # the log
        return APIServerError(error)

    @classmethod
    def handle_result(cls, klass, api_name, parameters, result):
        '''
            Can be overriden to add some behaviour after an API call completed,
            right before the result is sent back
        '''
        if api_logger.isEnabledFor(logging.DEBUG) or config.getboolean(
                'env', 'testing') is True or (
                api_context().get('_validate_output', False)):
            try:
                klass._apis[api_name]['compiled_output_schema'](result)
            except fastjsonschema.exceptions.JsonSchemaException as e:
                api_logger.error('%s.%s:Invalid output:%s' %
                    (klass.__name__, api_name, e.message))
                if config.getboolean('env', 'testing') is True or (
                        api_context().get('_validate_output', False)):
                    raise
        return result

    @classmethod
    def update_transaction_context(cls, api_context):
        '''
            Can be used to update the transaction context in which the API will
            be executed based on the API specific context
        '''
        context = Transaction().context
        update = {}
        if 'language' in api_context:
            update['language'] = api_context.pop('language')
        elif 'language' not in context:
            update['language'] = config.get('database', 'language') or 'en'
        if 'language_direction' in api_context:
            update['language_direction'] = api_context.pop('language_direction')
        elif 'language_direction' not in context:
            update['language_direction'] = 'ltr'
        return update


class APIMixin(Model):
    '''
        All models implementing APIs should inherit from this one.

        An API model should only define APIs. It should not inherit from
        ModelSQL / ModelView. There should be one API class for a given
        namespace (ex: party, accounting, sales, etc.).

        To define an API, one should:

        - Define a class method with one "parameters" argument (which will hold
          the input for the method):

            @classmethod
            def my_api(cls, parameters):
                return min(
                    int(100 // parameters['price']), parameters['count'])

        - Add it to the "_apis" dict of the model in which it is defined. This
          allows to define some basic properties for the API:

            @classmethod
            def __setup__(cls):
                super().__setup__()
                cls._apis.update({
                        'my_api': {
                            'readonly': True,         # Nothing can be modified
                            'description': 'My API',  # Nice string
                            'public': True,           # No access check (opt)
                            },
                        })

        The following method can also be defined in order to refine the API
        behaviour:

        - _my_api_schema: returns a jsonschema against which the inputs will
          be checked

            @classmethod
            def _my_api_schema(cls):
                return {
                    'type': 'object',
                    'properties': {
                        'price': {
                            'type': 'string',
                            'pattern': '^-?[0-9]+(\.[0-9]+)?',
                            },
                        'name': {'type': 'string'},
                        'count': {'type': 'integer', 'default': 0},
                        },
                    'required': ['price', 'name'],
                    'additionalProperties': False,
                    }

        - _my_api_output_schema: returns a jsonschema that can be used to
          know the structure that can be expected from the API result

            @classmethod
            def _my_api_output_schema(cls):
                return {'type': 'integer'}

          Validation is not done by default, since it adds an unnessacary
          overhead. However, when running in debug mode, it will cause a
          warning log

        - _my_api_convert_input: will be called to transform the input. This is
          usually where type conversions will occur, as well as conversions
          from ids to records

            @classmethod
            def _my_api_convert_input(cls, parameters):
                parameters['price'] = Decimal(parameters['price'])
                return parameters

        - _my_api_validate_input: will be called for more detailed checks
          that cannot be performed reliably using a jsonschema. This will occur
          after the conversion

            @classmethod
            def _my_api_validate_input(cls, parameters):
                if parameters['count'] < 0:
                    return [{
                            'type': 'validation',
                            'data': {
                                'name': 'invalid_count',
                                'description': 'Count should be positive',
                                },
                            }]

        - _my_api_examples: Returns a list of examples that will be provided in
          the api description, and tested against the input / output schemas.
          If None is provided, it is assumed the API takes no parameters (an
          empty '{}') and returns nothing (an empty '{}' as well).

          The (optional) 'disable_schema_tests' flag allows to avoid running
          schema tests. This should be avoided unless for some reasons there
          are incompatibility between modules whose dependencies are not
          explicit.
          This flag will be ignored anyway when running unittests

            @classmethod
            def _my_api_examples(cls):
                return [
                    {
                        'input': {
                            'price': '20.12',
                            'name': 'Paper',
                            },
                        'output': 4,
                        },
                    ]

        When calling an API via JSON-RPC, one should pass the following
        parameters:

            my_api(parameters, api_context, tryton_context)

        - <parameters> are the actual parameters of the API. They must match
          the input json schema that was provided earlier

        - <api_context> is a dictionnary that can be used to provide some
          generic context for APIs. The whole context will be available anytime
          in API-related code by using the ServerContext "api_context" key.
          There are some special keys that will temporarily override the tryton
          context:

            - 'language': Overrides the language for the transaction
            - 'language_direction': Indicates the expected language direction
            - '_debug_server': If True, exceptions during handling of APIs
              will not be wrapped in API dedicated exceptions. This can greatly
              help when debugging 500s
            - '_validate': If True, only the validation pass will be done on
              the input, and nothing will actually be stored. This validation
              may be incomplete since part of it may require actually storing
              some of the information to detect
            - '_validate_output': If True, an invalid output (as in,
              inconsistent with the output schema) will cause an error.
              Requires that the server runs with a "DEBUG" logging level

          The api::update_transaction_context method can be overriden in
          modules which want to transfer other api_context values to the tryton
          context

        - <tryton_context>: The "standard" context for all JSON-RPC calls with
          Tryton. Usually irrelevant except in specific cases, since
          informations critical to the API's behaviour should be set in either
          the parameters or the api_context
    '''  # NOQA
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis = {}

    @classmethod
    def __post_setup__(cls):
        super().__post_setup__()
        Api = Pool().get('api')
        for api_name, api_data in cls._apis.items():
            Api.add_api(cls, api_name, api_data)

    @classmethod
    def _check_access(cls, api_name, parameters):
        '''
            Can be overriden in order to implement a custom access behaviour
            for a given API. Use with caution
        '''
        Pool().get('api').check_access(cls, api_name)

    @classmethod
    def _check_input(cls, api_name, parameters):
        return Pool().get('api').check_input(cls, api_name, parameters)


class APICore(APIMixin):
    '''
        API Core

        This model should be used for APIs that are not tied to particular
        business domain.

        This is where we should be careful not to add low-level APIs.
    '''
    __name__ = 'api.core'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'list_apis': {
                    'description': 'List available APIs',
                    'readonly': True,
                    'public': True,
                    },
                })

    @classmethod
    def list_apis(cls, parameters):
        api_list = getattr(cls, '__api_list', None)
        if api_list is not None:
            return api_list

        apis = {}
        for _, klass in Pool().iterobject():
            if not issubclass(klass, APIMixin):
                continue
            for api_name, api_data in klass._apis.items():
                apis[api_name] = api_data['description_complete']

        cls.__api_list = apis
        return apis

    @classmethod
    def _list_apis_output_schema(cls):
        return {
            'definitions': {
                'api': {
                    'type': 'object',
                    'properties': {
                        'description': {'type': 'string'},
                        'description_api': 'string',
                        'model': {'type': 'string'},
                        'name': {'type': 'string'},
                        'input_schema': {},
                        'output_schema': {},
                        'examples': {
                            'type': 'array',
                            'items': {'type': 'object'},
                            },
                        },
                    'additionalProperties': False,
                    },
                },
            'type': 'object',
            'additionalProperties': {'$ref': '#/definitions/api'},
            }

    @classmethod
    def _list_apis_examples(cls):
        return [{
                'input': {},
                'output': {
                    'list_apis': {
                        'description': 'List available APIs',
                        'description_api': 'list_apis_description',
                        # This could go out of hand fast...
                        'examples': [{'input': {}, 'output': {}}],
                        'input_schema': {
                            'additionalProperties': False,
                            'type': 'object'},
                        'model': 'api.core',
                        'name': 'list_apis',
                        'output_schema': {
                            'additionalProperties': {
                                '$ref': '#/definitions/api'},
                            'definitions': {
                                'api': {'additionalProperties': False,
                                    'properties': {
                                        'description': {'type': 'string'},
                                        'input_schema': {},
                                        'model': {'type': 'string'},
                                        'name': {'type': 'string'},
                                        'output_schema': {}},
                                    'type': 'object'}},
                            'type': 'object'}},
                    },
                }]
