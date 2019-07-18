# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
from stdnum import iban

from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA

__all__ = [
    'APICore',
    'APIParty',
    ]


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def model_definitions(cls, parameters):
        return super().model_definitions(parameters) + [
            cls._model_definitions_bank_account(),
            ]

    @classmethod
    def _model_definitions_party(cls):
        definition = super()._model_definitions_party()
        definition['fields'].append(
            dict(model='bank_account', **cls._field_description('party.party',
                    'bank_accounts', required=False, sequence=100,
                    force_type='ref')))
        return definition

    @classmethod
    def _model_definitions_bank_account(cls):
        return {
            'model': 'bank_account',
            'fields': [
                cls._field_description('bank.account', 'number',
                    required=True, sequence=0),
                cls._field_description('bank.account', 'bank',
                    required=True, sequence=10, force_type='string'),
                ],
            }


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _party_shared_schema(cls):
        schema = super()._party_shared_schema()
        schema['properties']['bank_accounts'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._party_bank_account_schema(),
            }
        return schema

    @classmethod
    def _party_bank_account_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'number': {'type': 'string'},
                'bank': {
                    'oneOf': [
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
                                'bic': {'type': 'string'},
                                },
                            'required': ['bic'],
                            },
                        ],
                    },
                },
            'required': ['number', 'bank'],
            }

    @classmethod
    def _party_convert(cls, data, options, parameters):
        super()._party_convert(data, options, parameters)

        data['bank_accounts'] = data.get('bank_accounts', [])
        for bank_account_data in data['bank_accounts']:
            cls._party_bank_account_convert(bank_account_data,
                options, parameters)

    @classmethod
    def _party_bank_account_convert(cls, data, options, parameters):
        pool = Pool()

        if 'bank' not in data:
            pool.get('api').add_input_error({
                    'type': 'missing_bank_information',
                    'data': {
                        'number': data['number'],
                        },
                    })
        else:
            data['bank'] = cls._bank_from_identifier(data['bank'])
        if not iban.is_valid(data['number']):
            pool.get('api').add_input_error({
                    'type': 'invalid_iban',
                    'data': {
                        'number': data['number'],
                        },
                    })

    @classmethod
    def _bank_from_identifier(cls, data):
        pool = Pool()
        Bank = pool.get('bank')

        if 'id' in data:
            return Bank(data['id'])
        elif 'bic' in data:
            matches = Bank.search([('bic', '=', data['bic'])])

            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 0:
                pool.get('api').add_input_error({
                        'type': 'multiple_bic_matches',
                        'data': {
                            'bic': data['bic'],
                            },
                        })
            else:
                pool.get('api').add_input_error({
                        'type': 'unknown_bic',
                        'data': {
                            'bic': data['bic'],
                            },
                        })

    @classmethod
    def _update_party(cls, party, data, options):
        super()._update_party(party, data, options)

        party.bank_accounts = getattr(party, 'bank_accounts', [])

        for bank_data in data['bank_accounts']:
            cls._update_party_bank_account(bank_data, party)

    @classmethod
    def _update_party_bank_account(cls, bank_data, party):
        if any(x.number == bank_data['number'] and x.type == 'iban'
                for x in party.bank_accounts):
            return

        pool = Pool()
        BankAccount = pool.get('bank.account.number')
        matches = BankAccount.search(cls._find_bank_account_domain(bank_data))

        if len(matches) == 0:
            new_account = cls._new_bank_account(bank_data)
            new_account.save()
            party.bank_accounts = list(party.bank_accounts) + [new_account]
        elif len(matches) == 1:
            party.bank_accounts = (list(party.bank_accounts) +
                [matches[0].account])
        elif len(matches) > 1:
            pool.get('api').add_input_error({
                    'type': 'duplicate',
                    'data': {
                        'model': 'bank.account.number',
                        'data': {
                            'number': bank_data['number'],
                            },
                        },
                    })

    @classmethod
    def _find_bank_account_domain(cls, data):
        return [
            ('type', '=', 'iban'),
            ('number', '=', data['number']),
            ]

    @classmethod
    def _new_bank_account(cls, data):
        return Pool().get('bank.account')(
            bank=data['bank'],
            numbers=[{'type': 'iban', 'number': data['number']}]
            )
