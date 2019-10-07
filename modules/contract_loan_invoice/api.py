# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core.api import CODE_SCHEMA, OBJECT_ID_SCHEMA


__all__ = [
    'APIContract',
    ]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _payment_schedule_format_invoice_detail(cls, detail):
        invoice_detail = super()._payment_schedule_format_invoice_detail(detail)
        loan = detail['loan']
        if loan:
            invoice_detail['loan'] = {
                'id': loan.id,
                'number': loan.number,
                }
        return invoice_detail

    @classmethod
    def _payment_schedule_invoice_detail_schema(cls):
        schema = super()._payment_schedule_invoice_detail_schema()
        schema['properties']['loan'] = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'number': CODE_SCHEMA,
                },
            }
        return schema

    @classmethod
    def _payment_schedule_examples(cls):
        examples = super()._payment_schedule_examples()
        examples.append(
            {
                'input': {
                    'contracts': [{'id': 2}],
                    },
                'output': [
                    {
                        'contract': {
                            'id': 2,
                            'number': 'A4125',
                            },
                        'schedule': [
                            {
                                'currency_symbol': '€',
                                'details': [
                                    {
                                        'end': '2019-12-31',
                                        'fee': '0',
                                        'name': 'Death',
                                        'origin': {
                                            'covered': {
                                                'id': 10,
                                                'party': {
                                                    'id': 412,
                                                    'code': '51435',
                                                    },
                                                },
                                            'option': {
                                                'coverage': {
                                                    'code': 'death_coverage',
                                                    'id': 20,
                                                    },
                                                'id': 20,
                                                },
                                            },
                                        'loan': {
                                            'id': 31,
                                            'number': 'A13512',
                                            },
                                        'premium': '315.00',
                                        'start': '2019-01-01',
                                        'tax': '10.00',
                                        'total': '325.00',
                                        },
                                    {
                                        'end': '2019-12-31',
                                        'fee': '0',
                                        'name': 'Accident',
                                        'origin': {
                                            'covered': {
                                                'id': 10,
                                                'party': {
                                                    'id': 412,
                                                    'code': '51435',
                                                    },
                                                },
                                            'option': {
                                                'coverage': {
                                                    'code': 'accident_coverage',
                                                    'id': 10,
                                                    },
                                                'id': 10,
                                                },
                                            },
                                        'loan': {
                                            'id': 31,
                                            'number': 'A13512',
                                            },
                                        'premium': '56.00',
                                        'start': '2019-01-01',
                                        'tax': '10.00',
                                        'total': '66.00',
                                        },
                                    ],
                                'end': '2019-12-31',
                                'fee': '0',
                                'premium': '371.00',
                                'start': '2019-01-01',
                                'tax': '20.00',
                                'total': '391.00',
                                },
                            ],
                        'total': '391.00',
                        'total_fee': '0',
                        'total_premium': '371.00',
                        'total_tax': '20.00',
                        },
                    ],
                },
            )
        return examples
