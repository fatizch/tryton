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

from trytond.pool import Pool
from trytond.model import Model
from trytond.transaction import Transaction
from trytond.config import config
from trytond.rpc import RPC
from trytond.error import UserError
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
    return ServerContext().get('_api_context')


def apify(klass, api_name):
    '''
        Transforms a standard method into an API. This mainly means:
        - calling the appropriate checks / input conversions
        - executing the method
        - handling of errors
    '''
    function = getattr(klass, api_name)
    # re-decorate everytime if needed
    function = getattr(function, '__api_function', function)

    def decorated(parameters, context):
        Api = Pool().get('api')
        with Transaction().set_context(
                **Api.update_transaction_context(context)):
            with ServerContext().set_context(_api_context=context):
                try:
                    klass._check_access(api_name, parameters)
                    parameters = klass._check_input(api_name, parameters)
                    result = function(parameters)
                    return Api.handle_result(
                        klass, api_name, parameters, result)
                except Exception as e:
                    if (api_logger.isEnabledFor(logging.DEBUG)
                             or config.getboolean('env', 'testing') is True):
                        if context.get('_debug_server', False):
                            raise
                    return Api.handle_error(e)

    decorated.__api_function = function
    return decorated


def amount_for_api(amount):
    assert isinstance(amount, Decimal)
    return str(amount)


def amount_from_api(amount):
    try:
        return Decimal(amount)
    except InvalidOperation:
        raise APIInputError([{
                'type': 'conversion',
                'data': {
                    'input': amount,
                    'target_type': 'Decimal',
                    },
                }])


def date_for_api(date):
    assert isinstance(date, datetime.date)
    return date.strftime('%Y-%m-%d')


def date_from_api(date):
    try:
        return datetime.datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise APIInputError([{
                'type': 'conversion',
                'data': {
                    'input': date,
                    'target_type': 'date',
                    },
                }])


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
            'error_data': self.exception.args[0],
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
    def __init__(self, user_error):
        assert isinstance(user_error, UserError)
        self.user_error = user_error

    def format_error(self):
        return {
            'error_code': 400,
            'error_message': 'User Error',
            # TODO: Override raise_user_error to store the error code on the
            # exception, so that we can have access to something static,
            # independant from the language / context
            'error_data': self.user_error.message,
            }


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

            data['compiled_input_schema'](example['input'])
            data['compiled_output_schema'](example['output'])
            data['examples'].append(example)

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
        errors, parameters = cls._check_schema(klass, api_name, parameters)
        if errors:
            raise APIInputError(errors)

        parameters = cls._convert_input(klass, api_name, parameters)
        errors = cls._check_validator(klass, api_name, parameters)
        if errors:
            raise APIInputError(errors)
        return parameters

    @classmethod
    def _check_schema(cls, klass, api_name, parameters):
        if not klass._apis[api_name]['compiled_input_schema']:
            return [], parameters
        try:
            return [], klass._apis[api_name]['compiled_input_schema'](
                parameters)
        except fastjsonschema.exceptions.JsonSchemaException as e:
            # TODO (maybe) if it is performance wise: Use jsonschema in case of
            # failure to list all errors rather than just the first one
            return [{
                    'type': 'json_schema',
                    'data': e.message,
                    }], None

    @classmethod
    def _convert_input(cls, klass, api_name, parameters):
        return klass._apis[api_name]['convert_input'](parameters)

    @classmethod
    def _check_validator(cls, klass, api_name, parameters):
        return klass._apis[api_name]['validate_input'](parameters)

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
        if isinstance(error, UserError):
            return APIUserError(error)
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
                'env', 'testing') is True:
            try:
                klass._apis[api_name]['compiled_output_schema'](result)
            except fastjsonschema.exceptions.JsonSchemaException as e:
                api_logger.error('%s.%s:Invalid output:%s' %
                    (klass.__name__, api_name, e.message))
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
          empty '{}') and returns nothing (an empty '{}' as well)

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
