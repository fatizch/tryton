# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api import APIMixin, DATE_SCHEMA
from trytond.modules.api import date_from_api
from trytond.modules.coog_core import fields


PARTY_RELATION_SCHEMA = {
    'oneOf': [
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'ref': {'type': 'string'},
                },
            'required': ['ref'],
            },
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': {'type': 'integer'},
                },
            'required': ['id'],
            },
        {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'code': {'type': 'string'},
                },
            'required': ['code'],
            },
        ],
    }

__all__ = [
    'APIIdentity',
    'Party',
    'APICore',
    'APIParty',
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
    def model_definitions(cls, parameters):
        return super().model_definitions(parameters) + [
            cls._model_definitions_party(),
            cls._model_definitions_address(),
            ]

    @classmethod
    def _model_definitions_party(cls):
        return {
            'model': 'party',
            'fields': [
                cls._field_description('party.party', 'is_person',
                    required=True, sequence=0),
                cls._field_description('party.party', 'name',
                    required=True, sequence=10),
                cls._field_description('party.party', 'first_name',
                    required=False, sequence=20, conditions=[
                        {'name': 'is_person', 'operator': '=', 'value': True}]),
                cls._field_description('party.party', 'birth_date',
                    required=False, sequence=30, conditions=[
                        {'name': 'is_person', 'operator': '=', 'value': True}]),
                cls._field_description('party.party', 'email',
                    required=False, sequence=40, force_type='email'),
                cls._field_description('party.party', 'phone',
                    required=False, sequence=50, force_type='phone_number'),
                dict(model='address', **cls._field_description('party.party',
                        'main_address', required=False, sequence=60,
                        force_type='ref')),
                ],
            }

    @classmethod
    def _model_definitions_address(cls):
        return {
            'model': 'address',
            'fields': [
                cls._field_description('party.address', 'street',
                    required=True, sequence=0),
                cls._field_description('party.address', 'zip',
                    required=True, sequence=10),
                cls._field_description('party.address', 'city',
                    required=True, sequence=20),
                cls._field_description('party.address', 'country',
                    required=True, sequence=30, force_type='string'),
                ],
            }


class APIParty(APIMixin):
    'API Party'
    __name__ = 'api.party'

    @classmethod
    def _party_schema(cls):
        return {
            'oneOf': [
                cls._party_person_schema(),
                cls._party_company_schema(),
                ],
            }

    @classmethod
    def _party_shared_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'ref': {'type': 'string'},
                'id': {'type': 'integer'},
                'code': {'type': 'string'},
                'name': {'type': 'string'},
                'phone': {'type': 'string'},
                'email': {'type': 'string'},
                'addresses': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._party_address_schema(),
                    }
                },
            # Ideally, there should be a oneOf on 'ref' / 'id' / 'code'
            'required': ['name'],
            }

    @classmethod
    def _party_address_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'street': {'type': 'string'},
                'zip': {'type': 'string'},
                'city': {'type': 'string'},
                'country': {'type': 'string'},
                },
            'required': ['city', 'zip', 'country', 'street'],
            }

    @classmethod
    def _party_person_schema(cls):
        schema = cls._party_shared_schema()
        schema['properties']['is_person'] = {'const': True}
        schema['properties']['first_name'] = {'type': 'string'}
        schema['properties']['birth_date'] = DATE_SCHEMA
        schema['properties']['gender'] = {
            'type': 'string',
            'enum': [
                x[0] for x in Pool().get('party.party').gender.selection
                if x[0]],
            }
        schema['required'] += ['is_person', 'first_name', 'birth_date',
            'gender']
        return schema

    @classmethod
    def _party_company_schema(cls):
        schema = cls._party_shared_schema()
        schema['properties']['is_person'] = {'const': False}
        schema['required'].append('is_person')
        return schema

    @classmethod
    def _party_convert(cls, data, options, created=None):
        if 'birth_date' in data:
            data['birth_date'] = date_from_api(data['birth_date'])
        for address in data.get('addresses', []):
            cls._party_address_convert(address, options, created)

    @classmethod
    def _party_address_convert(cls, data, options, created=None):
        data['country'] = Pool().get('api').instance_from_code(
            'country.country', data['country'].upper())

    @classmethod
    def _relation_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'ref': {'type': 'string'},
                'type': {'type': 'string'},
                'to': PARTY_RELATION_SCHEMA,
                'from': PARTY_RELATION_SCHEMA,
                },
            'required': ['type', 'from', 'to', 'ref'],
            }

    @classmethod
    def _relation_convert(cls, data, options, parties=None):
        data['type'] = Pool().get('api').instance_from_code(
            'party.relation.type', data['type'])

        for key in ['from', 'to']:
            party = cls._party_from_reference(data[key], parties=parties)

            # Some could be references to not yet created data, in that case
            # they will be fetched later
            if party is not None:
                data[key] = party

    @classmethod
    def _party_from_reference(cls, ref_data, parties=None):
        '''
            Checks that references to parties are okay.

            If parties is set, it will be assumed to be a list of dict
            containing the "ref" flag for identification. Those parties will
            typically be parties which will be created by the API call.
        '''
        API = Pool().get('api')
        if 'ref' in ref_data:
            if parties is None or all(
                    ref_data['ref'] != x['ref'] for x in parties):
                API.add_input_error({
                        'type': 'bad_reference',
                        'data': {
                            'model': 'party.party',
                            'ref': ref_data['ref'],
                            }
                        })
        elif 'id' in ref_data or 'code' in ref_data:
            party = cls._find_party(ref_data)
            if party is None:
                API.add_input_error({
                        'type': 'bad_instance',
                        'model': 'party.party',
                        'data': ref_data,
                        })
        else:
            API.add_input_erro({
                    'type': 'bad_instance',
                    'data': {
                        'model': 'party.party',
                        'data': ref_data,
                        },
                    })

    @classmethod
    def _create_or_update_party(cls, data, options):
        assert data

        instance = cls._find_party(data, options)
        if instance is None:
            instance = cls._init_new_party(data, options)
        cls._update_existing_party(instance, data, options)
        return instance

    @classmethod
    def _find_party(cls, data, options=None):
        pool = Pool()
        Party = pool.get('party.party')

        domain = cls._find_party_domain(data, options)
        parties = Party.search(domain)
        if len(parties) == 0:
            return None
        if len(parties) == 1:
            return parties[0]
        pool.get('api').add_input_error({
                 'type': 'duplicate',
                 'data': {
                     'model': 'party',
                     'data': data,
                     },
                 })

    @classmethod
    def _find_party_domain(cls, data, options):
        if 'id' in data:
            return [('id', '=', data['id'])]
        if 'code' in data:
            return [('code', '=', data['code'])]
        if data.get('is_person', None):
            return [
                ('name', '=', data['name']),
                ('first_name', '=', data['first_name']),
                ('birth_date', '=', data['birth_date']),
                ]
        return [('name', '=', data['name'])]

    @classmethod
    def _init_new_party(cls, data, options):
        if data.get('is_person', False):
            party = cls._init_new_person(data, options)
        else:
            party = cls._init_new_company(data, options)
        party.addresses = []
        return party

    @classmethod
    def _init_new_person(cls, data, options):
        party = Pool().get('party.party')()
        party.is_person = True
        party.name = data['name']
        party.first_name = data['first_name']
        party.birth_date = None
        party.gender = data['gender']
        return party

    @classmethod
    def _init_new_company(cls, data, options):
        party = Pool().get('party.party')()
        party.is_person = False
        party.name = data['name']
        return party

    @classmethod
    def _update_existing_party(cls, party, data, options):
        if party.is_person:
            cls._update_person(party, data, options)
        else:
            cls._update_company(party, data, options)
        cls._update_party(party, data, options)

    @classmethod
    def _update_person(cls, party, data, options):
        for fname in cls._update_person_fields():
            if fname in data and getattr(party, fname) != data[fname]:
                setattr(party, fname, data[fname])

    @classmethod
    def _update_person_fields(cls):
        return ['gender', 'first_name', 'birth_date']

    @classmethod
    def _update_company(cls, party, data, options):
        for fname in cls._update_company_fields():
            if fname in data and getattr(party, fname) != data[fname]:
                setattr(party, fname, data[fname])

    @classmethod
    def _update_company_fields(cls):
        return []

    @classmethod
    def _update_party(cls, party, data, options):
        for fname in cls._update_party_fields():
            if fname in data and getattr(party, fname) != data[fname]:
                setattr(party, fname, data[fname])

        if data.get('addresses', None):
            # For now, the rules for update if multiple addresses are given are
            # not known
            assert len(data['addresses']) == 1

            address_data = data['addresses'][0]
            if party.addresses:
                address = [x for x in party.addresses
                    if x.id == party.main_address.id]
            else:
                address = cls._init_new_address()
                party.addresses = [address]
            address.street = address_data['street']
            address.zip = address_data['zip']
            address.city = address_data['city']
            address.country = address_data['country']
            party.addresses = list(party.addresses)

    @classmethod
    def _update_party_fields(cls):
        return ['name', 'email', 'phone']

    @classmethod
    def _init_new_address(cls):
        return Pool().get('party.address')()

    @classmethod
    def _update_relation_parameters(cls, data, created):
        for key in ['from', 'to']:
            if 'ref' in data[key]:
                data[key] = created['parties'][data[key]['ref']]

    @classmethod
    def _create_or_update_relation(cls, data, options):
        assert data
        instance = cls._find_relation(data, options)
        if instance:
            # No update for now
            return instance
        return Pool().get('party.relation.all')(
            type=data['type'], from_=data['from'], to=data['to'])

    @classmethod
    def _find_relation(cls, data, options):
        pool = Pool()
        Relation = pool.get('party.relation.all')

        relations = Relation.search([
                ('type', '=', data['type'].id),
                ('from_', '=', data['from']),
                ('to', '=', data['to']),
                ])
        if len(relations) == 0:
            return None
        if len(relations) == 1:
            return relations[0]
        pool.get('api').add_input_error({
                'type': 'duplicate',
                'data': {
                    'model': 'relation',
                    'type': data['type'].code,
                    },
                })
