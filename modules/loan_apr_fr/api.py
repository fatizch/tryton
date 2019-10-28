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
        if contract.is_loan:
            result['taea'] = [
                cls._payment_schedule_taea(contract_loan)
                for contract_loan in contract.ordered_loans]
        return result

    @classmethod
    def _payment_schedule_taea(cls, contract_loan):
        return {
            'taea': amount_for_api(contract_loan.taea),
            'loan': {
                'id': contract_loan.loan.id,
                'number': contract_loan.loan.number,
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

    @classmethod
    def _simulate_cleanup_schedule(cls, schedule_data, created):
        super()._simulate_cleanup_schedule(schedule_data, created)
        for taea_data in schedule_data.get('taea', []):
            taea_data['loan'] = {
                'ref': created['loan_ref_per_id'][taea_data['loan']['id']],
                }

    @classmethod
    def _simulate_update_schedule_output_schema(cls, base):
        super()._simulate_update_schedule_output_schema(base)
        base['items']['properties']['taea']['items']['properties']['loan'][
            'properties'] = {
            'ref': {'type': 'string'},
            }
