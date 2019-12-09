# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA, OBJECT_ID_SCHEMA

from trytond.modules.endorsement.wizard import EndorsementWizardStepMixin

__all__ = [
    'APIConfiguration',
    'APIEndorsement',
    ]


class APIConfiguration(metaclass=PoolMeta):
    __name__ = 'api.configuration'

    change_party_addresses_definition = fields.Many2One(
        'endorsement.definition', 'Change Party Addresses Definition',
        domain=[
            ('ordered_endorsement_parts.endorsement_part.view', '=',
                'change_party_address')],
        ondelete='RESTRICT',
        help='The endorsement definition that will be bound to endorsements '
        'generated from the change_party_addresses API')


class APIEndorsement(metaclass=PoolMeta):
    __name__ = 'api.endorsement'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'change_party_addresses': {
                    'description': 'Updates the current address of the party',
                    'public': False,
                    'readonly': False,
                    },
                'update_party_addresses': {
                    'description': 'Modify existing addresses on a party, '
                    'should be avoided in favor of change_party_addresses',
                    'public': False,
                    'readonly': False,
                    },
                })

    @classmethod
    def change_party_addresses(cls, parameters):
        pool = Pool()
        Endorsement = pool.get('endorsement')

        endorsement = Endorsement()
        endorsement.definition = parameters['endorsement_definition']
        endorsement.effective_date = parameters['date']

        cls._change_party_addresses_update_endorsement(endorsement, parameters)
        result = cls._complete_endorsement(
             endorsement, parameters.get('options', {}))
        return result

    @classmethod
    def _change_party_addresses_update_endorsement(cls, endorsement,
            parameters):
        pool = Pool()
        PartyEndorsement = pool.get('endorsement.party')

        party_endorsement = PartyEndorsement()
        party_endorsement.party = parameters['party']

        cls._change_party_addresses_update_party(parameters)

        EndorsementWizardStepMixin._update_endorsement(
            party_endorsement, parameters['party']._save_values)

        endorsement.party_endorsements = [party_endorsement]

    @classmethod
    def _change_party_addresses_update_party(cls, parameters):
        party = parameters['party']
        for address in party.addresses:
            if not address.end_date or address.end_date >= parameters['date']:
                address.end_date = parameters['date'] - relativedelta(days=1)

        addresses = list(party.addresses)
        for address_data in parameters['new_addresses']:
            new_address = cls._change_party_addresses_create_new_address(
                address_data)
            new_address.start_date = parameters['date']
            addresses.append(new_address)

        party.addresses = list(addresses)

    @classmethod
    def _change_party_addresses_create_new_address(cls, address_data):
        Address = Pool().get('party.address')

        address = Address()
        address.street = address_data['street']
        address.zip = address_data['zip']
        address.city = address_data['city']
        address.country = address_data['country']

        return address

    @classmethod
    def _change_party_addresses_schema(cls):
        PartyAPI = Pool().get('api.party')

        schema = cls._endorsement_base_schema()
        schema['properties'].update({
                'party': CODED_OBJECT_SCHEMA,
                'new_addresses': {
                    'type': 'array',
                    'minItems': 1,
                    'additionalItems': False,
                    'items': PartyAPI._party_address_schema(),
                    },
                })
        schema['required'] = ['party', 'new_addresses']
        return schema

    @classmethod
    def _change_party_addresses_output_schema(cls):
        return cls._endorsement_base_output_schema()

    @classmethod
    def _change_party_addresses_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        parameters = cls._endorsement_base_convert_input(
            'change_party_addresses', parameters)

        parameters['party'] = API.instantiate_code_object('party.party',
            parameters['party'])

        for address_data in parameters['new_addresses']:
            PartyAPI._party_address_convert(address_data, None, None)

        return parameters

    @classmethod
    def _change_party_addresses_examples(cls):
        return [
            {
                'input': {
                    'party': {
                        'code': '1234',
                        },
                    'date': '2020-05-12',
                    'new_addresses': [
                        {
                            'street': 'Somewhere',
                            'zip': '15234',
                            'city': 'Strasbourg',
                            'country': 'FR',
                            },
                        ]
                    },
                'output': {
                    'endorsements': [
                        {
                            'id': 4123,
                            'number': '1412398',
                            'state': 'applied',
                            'definition': 'default_change_address',
                            },
                        ],
                    },
                },
            {
                'input': {
                    'party': {
                        'id': 4123,
                        },
                    'new_addresses': [
                        {
                            'street': 'Somewhere Else',
                            'zip': '15234',
                            'city': 'Still Strasbourg',
                            'country': 'FR',
                            },
                        ],
                    'endorsement_definition': {
                        'code': 'my_custom_endorsement',
                        },
                    },
                'output': {
                    'endorsements': [
                        {
                            'id': 4123,
                            'number': '1412398',
                            'state': 'applied',
                            'definition': 'my_custom_endorsement',
                            },
                        {
                            'id': 4124,
                            'number': '1412399',
                            'state': 'applied',
                            'definition': 'my_auto_generated_endorsement',
                            },
                        {
                            'id': 4125,
                            'number': '1412400',
                            'state': 'draft',
                            'definition': 'my_auto_generated_endorsement',
                            },
                        ],
                    },
                },
            ]

    @classmethod
    def update_party_addresses(cls, parameters):
        pool = Pool()
        Endorsement = pool.get('endorsement')

        endorsement = Endorsement()
        endorsement.definition = parameters['endorsement_definition']

        cls._update_party_addresses_update_endorsement(endorsement, parameters)
        result = cls._complete_endorsement(
             endorsement, parameters.get('options', {}))
        return result

    @classmethod
    def _update_party_addresses_update_endorsement(cls, endorsement,
            parameters):
        pool = Pool()
        PartyEndorsement = pool.get('endorsement.party')

        party_endorsement = PartyEndorsement()
        party_endorsement.party = parameters['party']

        cls._update_party_addresses_update_party(parameters)

        EndorsementWizardStepMixin._update_endorsement(
            party_endorsement, parameters['party']._save_values)

        endorsement.effective_date = parameters['date']
        endorsement.party_endorsements = [party_endorsement]

    @classmethod
    def _update_party_addresses_update_party(cls, parameters):
        PartyAPI = Pool().get('api.party')

        party = parameters['party']
        per_id = {x['id']: x['new_values']
            for x in parameters['updated_addresses']}
        for address in party.all_addresses:
            if address.id not in per_id:
                continue
            PartyAPI._update_party_address(address, per_id[address.id], {})

        party.all_addresses = list(party.all_addresses)

    @classmethod
    def _update_party_addresses_schema(cls):
        PartyAPI = Pool().get('api.party')

        schema = cls._endorsement_base_schema()
        schema['properties'].update({
                'party': CODED_OBJECT_SCHEMA,
                'updated_addresses': {
                    'type': 'array',
                    'minItems': 1,
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalItems': False,
                        'required': ['id', 'new_values'],
                        'properties': {
                            'id': OBJECT_ID_SCHEMA,
                            'new_values': PartyAPI._party_address_schema(),
                            },
                        },
                    },
                })
        schema['required'] = ['party', 'updated_addresses']
        return schema

    @classmethod
    def _update_party_addresses_output_schema(cls):
        return cls._endorsement_base_output_schema()

    @classmethod
    def _update_party_addresses_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        parameters = cls._endorsement_base_convert_input(
            'change_party_addresses', parameters)
        parameters['party'] = API.instantiate_code_object('party.party',
            parameters['party'])

        for address_data in parameters['updated_addresses']:
            address_data['address'] = API.instantiate_code_object(
                'party.address', {'id': address_data['id']})

            if address_data['address'].party != parameters['party']:
                API.add_input_error({
                        'type': 'invalid_party_address',
                        'data': {
                            'party': parameters['party'].code,
                            'address_id': address_data['id'],
                            },
                        })

            PartyAPI._party_address_convert(
                address_data['new_values'], None, None)

        return parameters

    @classmethod
    def _update_party_addresses_examples(cls):
        return [
            {
                'input': {
                    'party': {
                        'code': '1234',
                        },
                    'date': '2020-05-12',
                    'updated_addresses': [
                        {
                            'id': 5315,
                            'new_values': {
                                'street': 'Somewhere',
                                'zip': '15234',
                                'city': 'Strasbourg',
                                'country': 'FR',
                                },
                            },
                        ]
                    },
                'output': {
                    'endorsements': [
                        {
                            'id': 4123,
                            'number': '1412398',
                            'state': 'applied',
                            'definition': 'default_change_address',
                            },
                        ],
                    },
                },
            ]
