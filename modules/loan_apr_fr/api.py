# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.api.api.core import AMOUNT_SCHEMA, amount_for_api
from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA, CODE_SCHEMA


__all__ = [
    'APIContract',
    ]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _payment_schedule_from_contract(cls, contract):
        result = super()._payment_schedule_from_contract(contract)
        result['taea'] = [
            cls._payment_schedule_taea(loan) for loan in contract.loans]
        return result

    @classmethod
    def _payment_schedule_taea(cls, loan):
        return {
            'taea': amount_for_api(loan.taea),
            'loan': {
                'id': loan.id,
                'number': loan.number,
                },
            }

    @classmethod
    def _payment_schedule_output_schema(cls):
        schema = super()._payment_schedule_output_schema()
        schema['items']['properties']['taea'] = {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'taea': AMOUNT_SCHEMA,
                    'loan': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'id': OBJECT_ID_SCHEMA,
                            'number': CODE_SCHEMA,
                            },
                        }
                    },
                },
            }
        return schema

    @classmethod
    def _payment_schedule_examples(cls):
        examples = super()._payment_schedule_examples()
        examples[-1]['output'][0]['taea'] = [
            {
                'loan': {
                    'id': 31,
                    'number': 'A13512',
                    },
                'taea': '0.002513542',
                },
            ]
        return examples
