# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
from trytond.pool import PoolMeta

from trytond.modules.api import APIInputError

__all__ = [
    'APICore',
    'APIParty',
    ]


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _model_definitions_party(cls):
        definition = super()._model_definitions_party()
        definition['fields'].append(
            dict(model='bank_account', **cls._field_description('party.party',
                    'bank_accounts', required=False, sequence=100,
                    force_type='ref')))
        definition['fields'].append(
            cls._field_description('party.party', 'claim_bank_account',
                required=False, sequence=110, force_type='string')
            )
        return definition


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _update_party(cls, party, data, options):
        super()._update_party(party, data, options)

        if 'claim_bank_account' in data:
            account_data = data['claim_bank_account']
            if 'id' in account_data:
                field_name, value = 'id', account_data['id']
            else:
                field_name, value = 'number_compact', account_data['number']

            for account in party.bank_accounts:
                if getattr(account, field_name) == value:
                    match = account
                    break
            else:
                raise APIInputError([{
                        'type': 'unknown_bank_account_number',
                        'data': account_data,
                        }])
            party._set_forced_claim_bank_account(match)

    @classmethod
    def _party_shared_schema(cls):
        schema = super()._party_shared_schema()
        schema['properties']['claim_bank_account'] = {
            'oneOf': [
                {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'number': {'type': 'string'},
                        },
                    'required': ['number'],
                    },
                {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'id': {'type': 'integer'},
                        },
                    'required': ['id'],
                    },
                ],
            }
        return schema
