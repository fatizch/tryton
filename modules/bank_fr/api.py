# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA

__all__ = [
    'APIParty',
    ]


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update(
            {
                'bank_from_number': {
                    'description': 'Extracts the bank information from the'
                    'account number',
                    'public': True,
                    'readonly': True,
                }
            }
        )

    @classmethod
    def bank_from_number(cls, parameters):
        pool = Pool()
        BankAccount = pool.get('bank.account')

        number = parameters['number']
        bank = BankAccount.get_bank_from_number(number)
        if not bank:
            return {}
        data = {
            'id': bank.id,
            'name': bank.rec_name,
            'bic': bank.bic,
        }
        return data

    @classmethod
    def _bank_from_number_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'number': {'type': 'string'}},
            'required': ['number'],
        }

    @classmethod
    def _bank_from_number_output_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'name': {'type': 'string'},
                'bic': {'type': 'string'},
            },
        }

    @classmethod
    def _bank_from_number_examples(cls):
        return [
            {
                'input': {'number': '123425425'},
                'output': {
                    'id': 1,
                    'name': 'Ma banque',
                    'bic': 'XXXXXXXXXX',
                },
            }
        ]

    @classmethod
    def _party_bank_account_schema(cls):
        schema = super()._party_bank_account_schema()
        schema['required'] = [x for x in schema['required'] if x != 'bank']
        return schema

    @classmethod
    def _party_bank_account_convert(cls, data, options, parameters):
        pool = Pool()
        if not data.get('bank', None):
            bank = pool.get('bank.account').get_bank_from_number(
                data['number'])
            if not bank:
                pool.get('api').add_input_error({
                        'type': 'cannot_detect_bank',
                        'data': {
                            'number': data['number'],
                            },
                        })
            else:
                data['bank'] = {'id': bank.id}
        else:
            super()._party_bank_account_convert(data, options, parameters)


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def translate_api_input_error_data(cls, error_type, error_data):
        if error_type == 'cannot_detect_bank':
            message = gettext(
                'bank_fr.msg_no_bank_detected_for_number',
                number=error_data['number'])
            return message
        return super().translate_api_input_error_data(error_type,
            error_data)
