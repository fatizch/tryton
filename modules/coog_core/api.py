# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique

from trytond.modules.api import APIInputError
from trytond.modules.coog_core import model, fields


IDENTIFIER_KINDS = [
    ('generic', 'Generic'),
    ('google', 'Google'),
    ('facebook', 'Facebook'),
    ('salesforce', 'SalesForce'),
    ]


__all__ = [
    'APIIdentity',
    'APIResource',
    'APICore',
    ]


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
        return {'user': self.user.id if self.user else None}


class APIResource(model.CoogSQL, model.CoogView):
    'API Resource'
    __name__ = 'api.resource'

    origin = fields.Reference('Origin', 'select_resource_models',
        required=True, help='The record to which this resource will be linked')
    key = fields.Char('Key', required=True, help='The identifier for this '
        'particular resource for this origin')
    value = fields.Text('Value', help='The value for this origin / key pair')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('key_unique', Unique(t, t.origin, t.key),
                'The origin / key pair must be unique'),
            ]

    @classmethod
    def select_resource_models(cls):
        # We can do this this way because we do not really care about
        # translations
        if hasattr(cls, '__resource_models'):
            return cls.__resource_models
        result = []
        for _, klass in Pool().iterobject():
            if not issubclass(klass, APIResourceMixin):
                continue
            result.append((klass.__name__, klass.__name__))
        return result


class APIResourceMixin(model.CoogSQL):
    '''
        A Model inheriting this Mixin will have a list of api_resources that
        will be available to easily set custom properties
    '''
    api_resources = fields.One2Many('api.resource', 'origin', 'API Resources',
        delete_missing=True, target_not_indexed=True,
        help='A list of resources which will only be used through the APIs')


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'identity_context': {
                    'public': False,
                    'readonly': True,
                    'description': 'Describe an identity',
                    },
                })

    @classmethod
    def identity_context(cls, parameters):
        Identity = Pool().get('ir.api.identity')
        domain = cls._identity_domain(parameters)
        identities = Identity.search(domain)
        if identities:
            assert len(identities) == 1  # Should be ok because unicity
            return identities[0].get_api_context()
        raise APIInputError({
                'type': 'unknown_identifier',
                })

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
            'properties': {
                'user': {'type': ['null', 'integer']},
                },
            'additionalProperties': False,
            'required': ['user'],
            }

    @classmethod
    def _identity_context_examples(cls):
        return [
            {
                'input': {'kind': 'google', 'identifier': '12345aze'},
                'output': {'user': None},
                },
            {
                'input': {'kind': 'google', 'identifier': '12345aze'},
                'output': {'user': 2},
                },
            ]
