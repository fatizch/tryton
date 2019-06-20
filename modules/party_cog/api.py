# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields


__all__ = [
    'APIIdentity',
    'Party',
    'APICore',
    ]


class APIIdentity(metaclass=PoolMeta):
    __name__ = 'ir.api.identity'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        select=True, help='If set, the identity will be bound to this party, '
        'which will limit what may be available in consultation APIs')

    def get_api_context(self):
        context = super().get_api_context()
        context['party'] = self.party.id if self.party else None
        return context


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    identities = fields.One2Many('ir.api.identity', 'party', 'Identities',
        delete_missing=True, target_not_required=True,
        help='The list of identities which will be associated to this party')


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _identity_context_output_schema(cls):
        schema = super()._identity_context_output_schema()
        schema['properties']['party'] = {'type': ['null', 'integer']}
        schema['required'].append('party')
        return schema

    @classmethod
    def _identity_context_examples(cls):
        examples = super()._identity_context_examples()
        for example in examples:
            example['output']['party'] = None
        examples.append({
                'input': {'kind': 'generic', 'identifier': '425341'},
                'output': {'user': 3, 'party': 20},
                })
        return examples

    @classmethod
    def _person_description(cls, **kwargs):
        result = [
            cls._field_description('party.party', 'name',
                required=True, sequence=0),
            cls._field_description('party.party', 'first_name',
                required=True, sequence=10),
            ]
        if kwargs.get('with_birth_date', False):
            result.append(cls._field_description(
                    'party.party', 'birth_date',
                    required=kwargs.get('with_birth_date_required', False),
                    sequence=20))
        if kwargs.get('with_email', False):
            result.append(cls._field_description(
                    'party.party', 'email',
                    required=kwargs.get('with_email_required', False),
                    sequence=30))
            result[-1]['type'] = 'email'
        if kwargs.get('with_phone', False):
            result.append(cls._field_description(
                    'party.party', 'phone_number',
                    required=kwargs.get('with_phone_required', False),
                    sequence=40))
            result[-1]['type'] = 'phone'
        return result

    @classmethod
    def _company_description(cls, **kwargs):
        result = [
            cls._field_description('party.party', 'name',
                required=True, sequence=0),
            ]
        if kwargs.get('with_email', False):
            result.append(cls._field_description(
                    'party.party', 'birth_date',
                    required=kwargs.get('with_email_required', False),
                    sequence=30))
            result[-1]['type'] = 'email'
        if kwargs.get('with_phone', False):
            result.append(cls._field_description(
                    'party.party', 'birth_date',
                    required=kwargs.get('with_phone_required', False),
                    sequence=40))
            result[-1]['type'] = 'phone'
        return result

    @classmethod
    def _party_description(cls, **kwargs):
        result = cls._person_description(**kwargs)
        result.append(cls._field_description('party.party',
                'is_person', required=True, sequence=-10))
        for elem in result:
            if elem['name'] in cls._person_only_fields():
                elem['conditions'] = [
                    {'name': 'is_person', 'operator': '=', 'value': True}]
            if elem['name'] in cls._company_only_fields():
                elem['conditions'] = [
                    {'name': 'is_person', 'operator': '=', 'value': False}]
        return result

    @classmethod
    def _person_only_fields(cls):
        '''
            The list of fields that will only be displayed if the party is a
            person
        '''
        return ['birth_date', 'first_name']

    @classmethod
    def _company_only_fields(cls):
        '''
            The list of fields that will only be displayed if the party is not
            a person
        '''
        return []
