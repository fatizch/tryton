# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSingleton, Unique, fields as tryton_fields
from trytond.config import config

from trytond.modules.coog_core import model, fields, coog_string

OBJECT_ID_SCHEMA = {
    'type': 'integer',
    'minimum': 1,
    }

OBJECT_ID_NULL_SCHEMA = {
    'oneOf': [
        OBJECT_ID_SCHEMA,
        {'type': 'null'},
        ],
    }

CODE_SCHEMA = {'type': 'string', 'minLength': 1}

REF_ID_SCHEMA = {
    'oneOf': [
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'id': OBJECT_ID_SCHEMA},
            'required': ['id'],
            },
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'ref': {'type': 'string'}},
            'required': ['ref'],
            },
        ],
    }

CODED_OBJECT_SCHEMA = {
    'anyOf': [
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'id': OBJECT_ID_SCHEMA},
            'required': ['id'],
            },
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'code': CODE_SCHEMA},
            'required': ['code'],
            },
        ],
    }

CODED_OBJECT_ARRAY_SCHEMA = {
    'type': 'array',
    'items': CODED_OBJECT_SCHEMA,
    'minItems': 1,
    'additionalItems': False,
    }

FIELD_CONDITIONS = {
    'type': 'array',
    'additionalItems': False,
    'items': {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'name': {'type': 'string'},
            'operator': {'type': 'string', 'enum': ['=']},
            'value': {
                'type': ['string', 'integer', 'boolean'],
                },
            },
        'required': ['name', 'operator', 'value'],
        },
    }

MODEL_REFERENCE = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'model': {'type': 'string'},
        'required': {
            'type': 'array',
            'additionalItems': False,
            'items': {'type': 'string'},
            },
        'fields': {
            'type': 'array',
            'additionalItems': False,
            'items': {'type': 'string'},
            },
        'conditions': FIELD_CONDITIONS,
        },
    'required': ['model'],
    }

FIELD_SCHEMA = {
    'oneOf': [
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'type': {
                    'type': 'string',
                    'enum': ['string', 'date', 'email', 'phone_number',
                        'percentage', 'amount', 'boolean', 'integer'],
                    },
                'required': {'type': 'boolean'},
                'label': {'type': 'string'},
                'help': {'type': 'string'},
                'sequence': {'type': 'integer'},
                'name': {'type': 'string'},
                'conditions': FIELD_CONDITIONS,
                'enum': {'type': 'array'},
                },
            'required': ['name', 'label', 'required', 'type', 'sequence'],
            },
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'type': {'type': 'string', 'enum': ['ref', 'array']},
                'required': {'type': 'boolean'},
                'label': {'type': 'string'},
                'help': {'type': 'string'},
                'sequence': {'type': 'integer'},
                'name': {'type': 'string'},
                'conditions': FIELD_CONDITIONS,
                'model_conditions': FIELD_CONDITIONS,
                'model': {'type': 'string'},
                },
            'required': ['name', 'label', 'required', 'type', 'sequence',
                'model'],
            },
        ],
    }

SIMPLE_FIELD_SCHEMA = {
    'type': 'object',
    'properties': {
        'code': {'type': 'string'},
        'required': {'type': 'boolean'},
        'visible': {'type': 'boolean'},
        },
    'required': ['code'],
    'additionalProperties': False,
    }

DOMAIN_SCHEMA = {
    'type': 'object',
    'properties': {
        'fields': {
            'type': 'array',
            'additionalItems': False,
            'items': SIMPLE_FIELD_SCHEMA,
            },
        'conditions': FIELD_CONDITIONS,
        },
    'required': ['fields'],
    'additionalProperties': False,
    }

IDENTIFIER_KINDS = [
    ('generic', 'Generic'),
    ('google', 'Google'),
    ('facebook', 'Facebook'),
    ('salesforce', 'SalesForce'),
    ]

__all__ = [
    'APIConfiguration',
    'APIAccess',
    'APIIdentity',
    'API',
    'APICore',
    ]


class APIConfiguration(ModelSingleton, model.CoogSQL, model.CoogView):
    'Api Configuration'

    __name__ = 'api.configuration'


class APIAccess(metaclass=PoolMeta):
    __name__ = 'ir.api.access'

    @classmethod
    def check_access(cls, api_name):
        if config.getboolean('env', 'testing') is True:
            return True
        return super().check_access(api_name)


class APIIdentity(model.CoogSQL, model.CoogView):
    'API Identity'

    __name__ = 'ir.api.identity'

    identifier = fields.Char('Identifier', required=True,
        help='The identifier to match against')
    kind = fields.Selection(IDENTIFIER_KINDS, 'Kind',
        help='The type of identifier. Identifiers must be unique across a '
        'given type')
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE',
        help='If set, this identity will be bound to this user')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('identity_unique', Unique(t, t.identifier, t.kind),
                'The identifier must be unique per kind'),
            ]

    @classmethod
    def default_kind(cls):
        return 'generic'

    def get_api_context(self):
        if self.user:
            return {'user': {
                    'id': self.user.id,
                    'login': self.user.login,
                    },
                }
        return {}


class API(metaclass=PoolMeta):
    __name__ = 'api'

    @classmethod
    def instance_from_code(cls, model, code):
        Target = Pool().get(model)
        if hasattr(Target, 'get_instance_from_code'):
            try:
                return Target.get_instance_from_code(code)
            except KeyError:
                cls.add_input_error({
                        'type': 'configuration_not_found',
                        'data': {
                            'model': model,
                            'code': code,
                            },
                        })
        elif 'code' in Target._fields:
            # For the odd case where we cannot use the CodedMixin
            matches = Target.search([('code', '=', code)])
            if len(matches) == 1:
                return matches[0]
            elif len(matches) == 0:
                cls.add_input_error({
                        'type': 'configuration_not_found',
                        'data': {
                            'model': model,
                            'code': code,
                            },
                        })
            else:
                cls.add_input_error({
                        'type': 'duplicate_configuration_found',
                        'data': {
                            'model': model,
                            'code': code,
                            },
                        })

    @classmethod
    def instantiate_code_object(cls, model, identifier):
        pool = Pool()
        Model = pool.get(model)

        assert len(identifier) == 1, 'Invalid key'  # Should not happen (schema)
        key, value = list(identifier.items())[0]
        if key == 'id':
            # Check the id actually exists. Maybe cache it someday
            matches = Model.search([('id', '=', value)])
            if matches:
                return matches[0]
            pool.get('api').add_input_error({
                    'type': 'invalid_id',
                    'data': {
                        'model': model,
                        'id': value,
                        },
                    })
        elif key == 'code':
            return cls.instance_from_code(model, value)
        else:
            raise ValueError  # Should not happen (schema)


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'model_definitions': {
                    'public': True,
                    'readonly': True,
                    'description': 'Technical descriptions for the models '
                    'that will be used in the APIs',
                    },
                'identity_context': {
                    'public': False,
                    'readonly': True,
                    'description': 'Describe an identity',
                    },
                })

    @classmethod
    def identity_context(cls, parameters):
        pool = Pool()
        Identity = pool.get('ir.api.identity')

        domain = cls._identity_domain(parameters)
        identities = Identity.search(domain)
        if identities:
            assert len(identities) == 1  # Should be ok because unicity
            return identities[0].get_api_context()
        pool.get('api').add_input_error({'type': 'unknown_identifier'})

    @classmethod
    def _identity_domain(cls, parameters):
        return [
            ('kind', '=', parameters['kind']),
            ('identifier', '=', parameters['identifier']),
            ]

    @classmethod
    def _identity_context_schema(cls):
        Identity = Pool().get('ir.api.identity')
        return {
            'type': 'object',
            'properties': {
                'kind': {
                    'type': 'string',
                    'enum': [x[0] for x in Identity.kind.selection],
                    },
                'identifier': {'type': 'string'},
                },
            'additionalProperties': False,
            'required': ['kind', 'identifier'],
            }

    @classmethod
    def _identity_context_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'user': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'id': OBJECT_ID_SCHEMA,
                        'login': {'type': 'string'},
                        },
                    'required': ['id', 'login'],
                    },
                },
            }

    @classmethod
    def _identity_context_examples(cls):
        return [
            {
                'input': {'kind': 'google', 'identifier': '12345aze'},
                'output': {},
                },
            {
                'input': {'kind': 'google', 'identifier': '12345aze'},
                'output': {'user': {'id': 2, 'login': 'my_user'}},
                },
            ]

    @classmethod
    def model_definitions(cls, parameters):
        # Will be overriden to add business models
        return []

    @classmethod
    def _model_definitions_output_schema(cls):
        return {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'model': {'type': 'string'},
                    'fields': {
                        'type': 'array',
                        'additionalItems': False,
                        'items': FIELD_SCHEMA,
                        },
                    },
                'required': ['model', 'fields'],
                },
            }

    @classmethod
    def _model_definitions_examples(cls):
        return [
            {
                'input': {},
                'output': [
                    {
                        'model': 'party',
                        'fields': [
                            {
                                'name': 'is_person',
                                'required': True,
                                'label': 'Is Person',
                                'type': 'boolean',
                                'sequence': -10,
                                },
                            {
                                'name': 'name',
                                'required': True,
                                'label': 'Name',
                                'type': 'string',
                                'sequence': 0,
                                },
                            {
                                'name': 'first_name',
                                'required': True,
                                'label': 'First Name',
                                'type': 'string',
                                'sequence': 10,
                                'conditions': [
                                    {'name': 'is_person', 'operator': '=',
                                        'value': True},
                                    ],
                                },
                            {
                                'name': 'birth_date',
                                'required': True,
                                'label': 'Birth Date',
                                'type': 'string',
                                'sequence': 20,
                                'conditions': [
                                    {'name': 'is_person', 'operator': '=',
                                        'value': True},
                                    ],
                                },
                            {
                                'name': 'father',
                                'required': False,
                                'label': 'Father',
                                'type': 'ref',
                                'model': 'party',
                                'sequence': 30,
                                'conditions': [
                                    {'name': 'is_person', 'operator': '=',
                                        'value': True},
                                    ],
                                'model_conditions': [
                                    {'name': 'is_person', 'operator': '=',
                                        'value': True},
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ]

    @classmethod
    def _field_description(cls, model, field_name, required=False, sequence=0,
            conditions=None, force_type=None):
        result = {
            'name': field_name,
            'required': required,
            'sequence': sequence,
            }

        # Required for translations
        Model = Pool().get(model)
        instance = Model()
        result['label'] = coog_string.translate_label(instance, field_name)
        result['help'] = coog_string.translate_help(instance, field_name)

        if force_type is not None:
            result['type'] = force_type
            return result

        field = getattr(Model, field_name)
        if hasattr(field, '_field'):
            field = field._field
        if isinstance(field, tryton_fields.Char):
            result['type'] = 'string'
        elif isinstance(field, tryton_fields.Integer):
            result['type'] = 'integer'
        elif isinstance(field, tryton_fields.Numeric):
            result['type'] = 'amount'
        elif isinstance(field, tryton_fields.Boolean):
            result['type'] = 'boolean'
        elif isinstance(field, tryton_fields.Selection):
            result['type'] = 'string'
        elif isinstance(field, tryton_fields.Date):
            result['type'] = 'date'
        return result
