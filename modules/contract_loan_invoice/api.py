# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

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

    @classmethod
    def _simulate_prepare_contracts(cls, contracts, parameters):
        Contract = Pool().get('contract')

        super()._simulate_prepare_contracts(contracts, parameters)

        loan_contracts = [x for x in contracts if x.is_loan]
        if loan_contracts:
            Contract.calculate_prices(loan_contracts)

    @classmethod
    def _simulate_parse_created(cls, created):
        super()._simulate_parse_created(created)
        if 'loans' in created:
            created['loan_ref_per_id'] = {
                x['id']: x['ref'] for x in created['loans']}

    @classmethod
    def _simulate_cleanup_schedule_detail(cls, detail, created):
        super()._simulate_cleanup_schedule_detail(detail, created)
        if 'loan' in detail:
            detail['loan'] = {
                'ref': created['loan_ref_per_id'][detail['loan']['id']],
                }

    @classmethod
    def _simulate_convert_input(cls, parameters):
        Party = Pool().get('party.party')

        # Look for a default lender (with a valid address!)
        default_lender_address = Party.search([
                ('is_lender', '=', True),
                ('addresses.id', '!=', None),
                ], limit=1)[0].addresses[0]

        result = super()._simulate_convert_input(parameters)
        if 'loans' in parameters:
            for loan_data in parameters['loans']:
                if 'lender_address' not in loan_data:
                    # Add a random lender for compatibility
                    loan_data['lender_address'] = default_lender_address
        return result

    @classmethod
    def _simulate_update_schedule_detail_output_schema(cls, base):
        super()._simulate_update_schedule_detail_output_schema(base)
        base['properties']['loan']['properties'] = {
            'ref': {'type': 'string'},
            }
