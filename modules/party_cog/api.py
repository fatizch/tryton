# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api import APIMixin, DATE_SCHEMA
from trytond.modules.api import date_from_api
from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA

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
                'id': OBJECT_ID_SCHEMA,
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
        if self.party:
            context['party'] = {
                'id': self.party.id,
                'name': self.party.full_name,
                }
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
        schema['properties']['party'] = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'name': {'type': 'string'},
                },
            'required': ['id', 'name'],
            }
        return schema

    @classmethod
    def _identity_context_examples(cls):
        examples = super()._identity_context_examples()
        examples.append({
                'input': {'kind': 'generic', 'identifier': '425341'},
                'output': {'user': {'id': 2, 'login': 'my_user'},
                    'party': {'id': 20, 'name': 'Mr. Bond'}},
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
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'create_party': {
                    'public': False,
                    'readonly': False,
                    'description': 'Create or update a party',
                    },
                })

    @classmethod
    def create_party(cls, parameters):
        options = parameters.get('options', {})
        created = {}

        cls._create_parties(parameters, created, options)
        cls._create_relations(parameters, created, options)

        return cls._create_parties_result(created)

    @classmethod
    def _create_parties(cls, parameters, created, options):
        Party = Pool().get('party.party')

        parties = []
        for party in parameters.get('parties', []):
            parties.append(cls._create_or_update_party(party, options))
        Party.save(parties)

        created['parties'] = {}
        for party, data in zip(parties, parameters.get('parties', [])):
            created['parties'][data['ref']] = party

    @classmethod
    def _create_relations(cls, parameters, created, options):
        Relation = Pool().get('party.relation.all')
        relations = []
        for relation in parameters.get('relations', []):
            cls._update_relation_parameters(relation, created)
            relations.append(cls._create_or_update_relation(relation, options))
        Relation.save(relations)

        created['relations'] = {}
        for relation, data in zip(relations, parameters.get('relations', [])):
            created['relations'][data['ref']] = relation

    @classmethod
    def _create_parties_result(cls, created):
        result = {}
        for ref, instance in created.get('parties', {}).items():
            if 'parties' not in result:
                result['parties'] = []
            result['parties'].append(
                {'ref': ref, 'id': instance.id})
        return result

    @classmethod
    def _create_party_convert_input(cls, parameters):
        options = parameters.get('options', {})
        for party_data in parameters['parties']:
            cls._party_convert(party_data, options, parameters)
        for relation_data in parameters.get('relations', []):
            cls._relation_convert(relation_data, options, parameters)

        return parameters

    @classmethod
    def _create_party_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'parties': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._party_schema(),
                    },
                'relations': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._relation_schema(),
                    },
                },
            'required': ['parties'],
            }

    @classmethod
    def _create_party_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'parties': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'ref': {'type': 'string'},
                            'id': OBJECT_ID_SCHEMA,
                            },
                        'required': ['ref', 'id'],
                        },
                    },
                },
            'required': ['parties'],
            }

    @classmethod
    def _create_party_examples(cls):
        return [
            {
                'input': {
                    'parties': [{
                            'ref': '1',
                            'is_person': False,
                            'name': 'My company',
                            'contacts': [
                                {
                                    'type': 'email',
                                    'value': '123@456.com',
                                    },
                                ],
                            },
                        ],
                    },
                'output': {
                    'parties': [{'ref': '1', 'id': 1}],
                    },
                },
            {
                'input': {
                    'parties': [{
                            'ref': '2',
                            'is_person': True,
                            'name': 'Doe',
                            'first_name': 'John',
                            'birth_date': '1986-05-12',
                            'gender': 'male',
                            'identifiers': [
                                {
                                    'type': 'external_identifier',
                                    'code': '12345',
                                    },
                                ],
                            },
                        ],
                    },
                'output': {
                    'parties': [{'ref': '2', 'id': 2}],
                    },
                },
            {
                'input': {
                    'parties': [{
                            'ref': '3',
                            'is_person': False,
                            'name': 'My company',
                            'addresses': [
                                {
                                    'street': 'Somewhere',
                                    'zip': '15234',
                                    'city': 'Venice',
                                    'country': 'FR',
                                    },
                                ],
                            },
                        {
                            'ref': '4',
                            'is_person': True,
                            'name': 'Doe',
                            'first_name': 'Jane',
                            'birth_date': '1974-06-10',
                            'gender': 'female',
                            'relations': [
                                {
                                    'ref': '1',
                                    'type': 'employee',
                                    'to': {'ref': '3'},
                                    },
                                ],
                            },
                        ],
                    },
                'output': {
                    'parties': [{'ref': '3', 'id': 3}, {'ref': '4', 'id': 4}],
                    },
                },
            ]

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
        relation_from_party_schema = cls._relation_schema()
        del relation_from_party_schema['properties']['from']
        relation_from_party_schema['required'] = [
            x for x in relation_from_party_schema['required']
            if x != 'from']

        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'ref': {'type': 'string'},
                'id': OBJECT_ID_SCHEMA,
                'code': {'type': 'string'},
                'name': {'type': 'string'},
                'phone': {'type': 'string'},
                'email': {'type': 'string'},
                'addresses': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._party_address_schema(),
                    },
                'contacts': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._party_contact_schema(),
                    },
                'relations': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': relation_from_party_schema,
                    },
                'identifiers': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._party_identifier_schema(),
                    },
                },
            'required': ['name'],
            'anyOf': [
                {'required': ['ref']},
                {'required': ['code']},
                {'required': ['id']},
                ],
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
    def _party_identifier_schema(cls):
        return {
            'additionalProperties': False,
            'properties': {
                'type': {'type': 'string'},
                'code': {'type': 'string'},
                },
            'required': ['type', 'code'],
            }

    @classmethod
    def _party_contact_schema(cls):
        ContactMechanism = Pool().get('party.contact_mechanism')
        return {
            'additionalProperties': False,
            'properties': {
                'type': {
                    'type': 'string',
                    'enum': [x[0] for x in ContactMechanism.type.selection],
                    },
                'value': {'type': 'string'},
                },
            'required': ['type', 'value'],
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
    def _party_convert(cls, data, options, parameters):
        pool = Pool()
        API = pool.get('api')
        PartyIdentifier = pool.get('party.identifier')

        if 'birth_date' in data:
            data['birth_date'] = date_from_api(data['birth_date'])
        for address in data.get('addresses', []):
            cls._party_address_convert(address, options, parameters)
        parameters['relations'] = parameters.get('relations', [])
        for relation in data.get('relations', []):
            for fname in ['id', 'code', 'ref']:
                if fname in data:
                    relation['from'] = {fname: data[fname]}
            parameters['relations'].append(relation)

        identifier_types = [x[0] for x in PartyIdentifier.get_types() if x[0]]
        for identifier in data.get('identifiers', []):
            if identifier['type'] not in identifier_types:
                API.add_input_error({
                        'type': 'unknown_party_identifier',
                        'data': {
                            'type': identifier['type'],
                            'allowed_types': identifier_types,
                            },
                        })

    @classmethod
    def _party_address_convert(cls, data, options, parameters):
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
    def _relation_convert(cls, data, options, parameters):
        data['type'] = Pool().get('api').instance_from_code(
            'party.relation.type', data['type'])

        for key in ['from', 'to']:
            party = cls._party_from_reference(data[key],
                parties=parameters['parties'])

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
            return party
        else:
            API.add_input_error({
                    'type': 'bad_instance',
                    'data': {
                        'model': 'party.party',
                        'data': ref_data,
                        },
                    })

    @classmethod
    def _create_or_update_party(cls, data, options):
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
        party.identifiers = []
        party.contact_mechanisms = []

        # This is stupidly necessary because this field is stupid
        party.all_addresses = []
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
            if fname in data and getattr(party, fname, None) != data[fname]:
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
            if fname in data and getattr(party, fname, None) != data[fname]:
                setattr(party, fname, data[fname])

        cls._update_party_addresses(party, data, options)
        cls._update_party_identifiers(party, data, options)
        cls._update_party_contacts(party, data, options)

    @classmethod
    def _update_party_addresses(cls, party, data, options):
        party.addresses = getattr(party, 'addresses', [])
        if data.get('addresses', None):
            # For now, the rules for update if multiple addresses are given are
            # not known
            # TODO: Maybe add options to define alternative behaviours
            # (always_append, always_replace, etc...)
            assert len(data['addresses']) == 1

            address_data = data['addresses'][0]
            address = cls._find_party_address(party, address_data)
            address.street = address_data['street']
            address.zip = address_data['zip']
            address.city = address_data['city']
            address.country = address_data['country']

    @classmethod
    def _update_party_identifiers(cls, party, data, options):
        if data.get('identifiers', None):
            for identifier_data in data['identifiers']:
                party.update_identifier(
                    identifier_data['type'], identifier_data['code'])

    @classmethod
    def _update_party_contacts(cls, party, data, options):
        ContactMechanism = Pool().get('party.contact_mechanism')
        contact_mechanisms = list(party.contact_mechanisms)
        keys = {(x.type, x.value) for x in contact_mechanisms}
        for contact_data in data.get('contacts', []):
            if (contact_data['type'], contact_data['value']) in keys:
                pass
            contact_mechanisms.append(ContactMechanism(
                    type=contact_data['type'],
                    value=contact_data['value'],
                    ))
        party.contact_mechanisms = contact_mechanisms

    @classmethod
    def _update_party_fields(cls):
        return ['name', 'email', 'phone']

    @classmethod
    def _find_party_address(cls, party, address_data):
        pool = Pool()
        Address = pool.get('party.address')

        matches = [x for x in party.addresses
            if cls._party_address_matches(x, address_data)]

        if len(matches) == 0:
            new_address = Address()
            party.addresses = list(party.addresses) + [new_address]
            return new_address

        if len(matches) == 1:
            return matches[0]

        pool.get('api').add_input_error({
                'type': 'duplicate',
                'data': {
                    'model': 'party.address',
                    'data': {
                        'party': party.full_name,
                        'address': matches[0].full_address,
                        },
                     },
                 })

    @classmethod
    def _party_address_matches(cls, address, address_data):
        return ((address.city == address_data['city'])
            and (address.zip == address_data['zip'])
            and (address.country == address_data['country'])
            and (address.street == address_data['street']))

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
