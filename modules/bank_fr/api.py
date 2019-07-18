# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
from trytond.pool import PoolMeta, Pool

__all__ = [
    'APIParty',
    ]


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

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
