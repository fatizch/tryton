# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import FIELD_SCHEMA, OBJECT_ID_SCHEMA
from trytond.modules.api.api.core import APIInputError
from trytond.modules.api.api.core import amount_for_api, date_for_api
from trytond.modules.api.api.core import amount_from_api, date_from_api
from trytond.modules.api.api.core import DATE_SCHEMA, AMOUNT_SCHEMA, RATE_SCHEMA


__all__ = [
    'APIProduct',
    'APIContract',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        pool = Pool()
        ApiCore = pool.get('api.core')
        ExtraData = pool.get('extra_data')
        result = super()._describe_product(product)
        if product.is_loan:
            result['loan_configuration'] = {
                'fields': cls._describe_loan(),
                'extra_data': ApiCore._extra_data_structure(
                    ExtraData.search([('kind', '=', 'loan')])),
                }
        return result

    @classmethod
    def _describe_loan(cls):
        Core = Pool().get('api.core')
        return [
            Core._field_description('loan', 'amount',
                required=True, sequence=10),
            Core._field_description('loan', 'kind',
                required=True, sequence=20),
            Core._field_description('loan', 'payment_frequency',
                required=True, sequence=30),
            Core._field_description('loan', 'rate',
                required=True, sequence=40),
            Core._field_description('loan', 'funds_release_date',
                required=True, sequence=50),
            Core._field_description('loan', 'first_payment_date',
                required=False, sequence=60),
            Core._field_description('loan', 'duration',
                required=True, sequence=70),
            Core._field_description('loan', 'duration_unit',
                required=True, sequence=80),
            Core._field_description('loan', 'deferral',
                required=False, sequence=90),
            Core._field_description('loan', 'deferral_duration',
                required=False, sequence=100),
            ]

    @classmethod
    def _describe_product_schema(cls):
        result = super()._describe_product_schema()
        result['properties']['loan_configuration'] = \
            cls._describe_loan_schema()
        return result

    @classmethod
    def _describe_loan_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'fields': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': FIELD_SCHEMA,
                    },
                'extra_data': Pool().get('api.core')._extra_data_schema(),
                },
            }


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'compute_loan': {
                    'description': 'Computes the payments from raw loan data',
                    'public': True,
                    'readonly': True,
                    },
                })

    @classmethod
    def compute_loan(cls, parameters):
        result = []
        for loan_data in parameters:
            loan = cls._loan_from_parameters(loan_data)
            loan.calculate()
            payments = cls._extract_loan_payments(loan)
            result.append({'id': loan_data['id'], 'payments': payments})
        return result

    @classmethod
    def _loan_from_parameters(cls, parameters):
        loan = Pool().get('loan')()
        loan.amount = parameters.get('amount', None)
        loan.kind = parameters.get('kind', None)
        loan.rate = parameters.get('rate', Decimal(0))
        loan.funds_release_date = parameters.get('funds_release_date', None)
        loan.payment_frequency = parameters.get('payment_frequency', None)
        loan.duration = parameters.get('duration', None)
        loan.duration_unit = parameters.get('duration_unit', None)
        loan.currency = parameters.get('currency', None)
        loan.increments = parameters.get('increments', [])

        loan.deferral = parameters.get('deferral', '')
        loan.deferral_duration = parameters.get('deferral_duration', None)

        if loan.kind == 'interest_free' and loan.deferral_duration:
            loan.deferral = 'fully'

        loan.first_payment_date = parameters.get('first_payment_date', None)
        if loan.first_payment_date is None:
            # Auto compute if not set
            loan.first_payment_date = loan.calculate_synch_first_payment_date()
        return loan

    @classmethod
    def _extract_loan_payments(cls, loan):
        return [
            {
                'number': p.number,
                'start': date_for_api(p.start_date),
                'amount': amount_for_api(p.amount or Decimal(0)),
                'principal': amount_for_api(p.principal or Decimal(0)),
                'interest': amount_for_api(p.interest or Decimal(0)),
                } for p in loan.payments[1:]  # Number 0 is the fund release
            ]

    @classmethod
    def _compute_loan_schema(cls):
        return {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'oneOf': [
                    cls._loan_interest_free_schema(),
                    cls._loan_fixed_rate_schema(),
                    cls._loan_intermediate_schema(),
                    cls._loan_graduated_schema(),
                    ],
                },
            }

    @classmethod
    def _loan_base_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': {'type': 'integer'},
                'amount': AMOUNT_SCHEMA,
                'funds_release_date': DATE_SCHEMA,
                'payment_frequency': {
                    'type': 'string',
                    'enum': ['month', 'quarter', 'half_year', 'year'],
                    'default': 'month',
                    },
                'duration': {'type': 'integer', 'minimum': 1},
                'duration_unit': {
                    'type': 'string', 'enum': ['month', 'year'],
                    'default': 'month',
                    },
                'first_payment_date': DATE_SCHEMA,
                'currency': {'type': 'string', 'default': 'EUR'},
                'deferral_duration': {'type': 'integer', 'minimum': 0},
                'deferral': {'type': 'string', 'enum': ['partially', 'fully']},
                },
            'required': ['id', 'kind', 'amount', 'funds_release_date',
                'duration'],
            'dependencies': {
                'deferral_duration': {'required': ['deferral']},
                },
            }

    @classmethod
    def _loan_interest_free_schema(cls):
        schema = cls._loan_base_schema()
        schema['properties']['kind'] = {'const': 'interest_free'}

        # In case of deferral, its kind is irrelevant
        del schema['properties']['deferral']
        del schema['dependencies']['deferral_duration']
        if len(schema['dependencies']) == 0:
            del schema['dependencies']
        return schema

    @classmethod
    def _loan_fixed_rate_schema(cls):
        schema = cls._loan_base_schema()
        schema['properties']['kind'] = {'const': 'fixed_rate'}
        schema['properties']['rate'] = RATE_SCHEMA
        schema['required'].append('rate')
        return schema

    @classmethod
    def _loan_intermediate_schema(cls):
        schema = cls._loan_base_schema()
        schema['properties']['kind'] = {'type': 'string',
            'enum': ['intermediate', 'balloon']}
        schema['properties']['rate'] = RATE_SCHEMA
        schema['required'].append('rate')

        # Always deferral, by definition
        del schema['properties']['deferral']
        del schema['properties']['deferral_duration']
        del schema['dependencies']['deferral_duration']
        if len(schema['dependencies']) == 0:
            del schema['dependencies']
        return schema

    @classmethod
    def _loan_graduated_schema(cls):
        schema = cls._loan_base_schema()
        schema['properties']['kind'] = {'const': 'graduated'}
        schema['properties']['increments'] = {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'number_of_payments': {'type': 'integer', 'minimum': 1},
                    'payment_amount': {
                        'oneOf': [AMOUNT_SCHEMA, {'type': 'null'}],
                        'default': None,
                        },
                    'rate': {
                        'oneOf': [RATE_SCHEMA, {'type': 'null'}],
                        'default': None,
                        },
                    'payment_frequency': {
                        'type': 'string',
                        'enum': ['day', 'week', 'month', 'quarter',
                            'half_year', 'year'],
                        'default': 'month',
                        },
                    },
                },
            'required': ['number_of_payments'],
            }
        schema['required'].append('increments')

        # This will be done through increments
        del schema['properties']['duration']
        schema['required'] = [x for x in schema['required'] if x != 'duration']

        del schema['properties']['duration_unit']
        del schema['properties']['deferral_duration']
        del schema['dependencies']['deferral_duration']
        if len(schema['dependencies']) == 0:
            del schema['dependencies']
        return schema

    @classmethod
    def _compute_loan_output_schema(cls):
        return {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'id': OBJECT_ID_SCHEMA,
                    'payments': {
                        'type': 'array',
                        'additionalItems': False,
                        'items': cls._loan_payment_schema(),
                        },
                    },
                },
            }

    @classmethod
    def _loan_payment_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'amount': AMOUNT_SCHEMA,
                'interest': AMOUNT_SCHEMA,
                'number': {'type': 'integer'},
                'principal': AMOUNT_SCHEMA,
                'start': DATE_SCHEMA,
                },
            'required': ['amount', 'interest', 'number', 'principal', 'start'],
            }

    @classmethod
    def _compute_loan_convert_input(cls, parameters):
        Currency = Pool().get('currency.currency')
        for parameter in parameters:
            parameter['amount'] = amount_from_api(parameter['amount'])
            parameter['funds_release_date'] = date_from_api(
                parameter['funds_release_date'])
            if 'first_payment_date' in parameter:
                parameter['first_payment_date'] = date_from_api(
                    parameter['first_payment_date'])
            if 'rate' in parameter:
                parameter['rate'] = amount_from_api(parameter['rate'])
            try:
                parameter['currency'] = Currency.get_instance_from_code(
                    parameter['currency'])
            except KeyError:
                raise APIInputError([{
                            'type': 'configuration_not_found',
                            'data': {
                                'model': 'currency.currency',
                                'code': parameter['currency'],
                                },
                            }])

            for increment in parameter.get('increments', []):
                if increment.get('payment_amount', None):
                    increment['payment_amount'] = amount_from_api(
                        increment['payment_amount'])
                else:
                    increment['payment_amount'] = None
                if increment.get('rate', None):
                    increment['rate'] = amount_from_api(increment['rate'])
                else:
                    increment['rate'] = None
        return parameters

    @classmethod
    def _compute_loan_examples(cls):
        # Will be used for tests, so inputs / outputs should be consistent
        return [
            {
                'input': [
                    {
                        'id': 1,
                        'amount': '100000.00',
                        'kind': 'fixed_rate',
                        'rate': '0.04',
                        'funds_release_date': '2020-01-01',
                        'duration': 10,
                        },
                    {
                        'id': 2,
                        'amount': '100000.00',
                        'kind': 'interest_free',
                        'funds_release_date': '2020-01-01',
                        'duration': 10,
                        },
                    {
                        'id': 3,
                        'amount': '100000.00',
                        'rate': '0.06',
                        'kind': 'intermediate',
                        'funds_release_date': '2020-01-01',
                        'duration': 10,
                        },
                    {
                        'id': 4,
                        'kind': 'graduated',
                        'amount': '1000000.00',
                        'funds_release_date': '2020-01-01',
                        'increments': [
                            {
                                'number_of_payments': 5,
                                'payment_amount': '512.02',
                                },
                            {
                                'number_of_payments': 5,
                                },
                            ],
                        },
                    ],
                'output': [{
                        'id': 1,
                        'payments': [{'amount': '10184.25',
                                'interest': '333.33',
                                'number': 1,
                                'principal': '9850.92',
                                'start': '2020-02-01'},
                            {'amount': '10184.25',
                                'interest': '300.50',
                                'number': 2,
                                'principal': '9883.75',
                                'start': '2020-03-01'},
                            {'amount': '10184.25',
                                'interest': '267.55',
                                'number': 3,
                                'principal': '9916.70',
                                'start': '2020-04-01'},
                            {'amount': '10184.25',
                                'interest': '234.50',
                                'number': 4,
                                'principal': '9949.75',
                                'start': '2020-05-01'},
                            {'amount': '10184.25',
                                'interest': '201.33',
                                'number': 5,
                                'principal': '9982.92',
                                'start': '2020-06-01'},
                            {'amount': '10184.25',
                                'interest': '168.05',
                                'number': 6,
                                'principal': '10016.20',
                                'start': '2020-07-01'},
                            {'amount': '10184.25',
                                'interest': '134.67',
                                'number': 7,
                                'principal': '10049.58',
                                'start': '2020-08-01'},
                            {'amount': '10184.25',
                                'interest': '101.17',
                                'number': 8,
                                'principal': '10083.08',
                                'start': '2020-09-01'},
                            {'amount': '10184.25',
                                'interest': '67.56',
                                'number': 9,
                                'principal': '10116.69',
                                'start': '2020-10-01'},
                            {'amount': '10184.24',
                                'interest': '33.83',
                                'number': 10,
                                'principal': '10150.41',
                                'start': '2020-11-01'}]},
                    {
                        'id': 2,
                        'payments': [{'amount': '10000.00',
                                'interest': '0',
                                'number': 1,
                                'principal': '10000.00',
                                'start': '2020-02-01'},
                            {'amount': '10000.00',
                                'interest': '0',
                                'number': 2,
                                'principal': '10000.00',
                                'start': '2020-03-01'},
                            {'amount': '10000.00',
                                'interest': '0',
                                'number': 3,
                                'principal': '10000.00',
                                'start': '2020-04-01'},
                            {'amount': '10000.00',
                                'interest': '0',
                                'number': 4,
                                'principal': '10000.00',
                                'start': '2020-05-01'},
                            {'amount': '10000.00',
                                'interest': '0',
                                'number': 5,
                                'principal': '10000.00',
                                'start': '2020-06-01'},
                            {'amount': '10000.00',
                                'interest': '0',
                                'number': 6,
                                'principal': '10000.00',
                                'start': '2020-07-01'},
                            {'amount': '10000.00',
                                'interest': '0',
                                'number': 7,
                                'principal': '10000.00',
                                'start': '2020-08-01'},
                            {'amount': '10000.00',
                                'interest': '0',
                                'number': 8,
                                'principal': '10000.00',
                                'start': '2020-09-01'},
                            {'amount': '10000.00',
                                'interest': '0',
                                'number': 9,
                                'principal': '10000.00',
                                'start': '2020-10-01'},
                            {'amount': '10000.00',
                                'interest': '0',
                                'number': 10,
                                'principal': '10000.00',
                                'start': '2020-11-01'}]},
                    {
                        'id': 3,
                        'payments': [{'amount': '500.00',
                                'interest': '500.00',
                                'number': 1,
                                'principal': '0',
                                'start': '2020-02-01'},
                            {'amount': '500.00',
                                'interest': '500.00',
                                'number': 2,
                                'principal': '0',
                                'start': '2020-03-01'},
                            {'amount': '500.00',
                                'interest': '500.00',
                                'number': 3,
                                'principal': '0',
                                'start': '2020-04-01'},
                            {'amount': '500.00',
                                'interest': '500.00',
                                'number': 4,
                                'principal': '0',
                                'start': '2020-05-01'},
                            {'amount': '500.00',
                                'interest': '500.00',
                                'number': 5,
                                'principal': '0',
                                'start': '2020-06-01'},
                            {'amount': '500.00',
                                'interest': '500.00',
                                'number': 6,
                                'principal': '0',
                                'start': '2020-07-01'},
                            {'amount': '500.00',
                                'interest': '500.00',
                                'number': 7,
                                'principal': '0',
                                'start': '2020-08-01'},
                            {'amount': '500.00',
                                'interest': '500.00',
                                'number': 8,
                                'principal': '0',
                                'start': '2020-09-01'},
                            {'amount': '500.00',
                                'interest': '500.00',
                                'number': 9,
                                'principal': '0',
                                'start': '2020-10-01'},
                            {'amount': '100500.00',
                                'interest': '500.00',
                                'number': 10,
                                'principal': '100000.00',
                                'start': '2020-11-01'}]},
                    {
                        'id': 4,
                        'payments': [{'amount': '512.02',
                                'interest': '0',
                                'number': 1,
                                'principal': '512.02',
                                'start': '2020-02-01'},
                            {'amount': '512.02',
                                'interest': '0',
                                'number': 2,
                                'principal': '512.02',
                                'start': '2020-03-01'},
                            {'amount': '512.02',
                                'interest': '0',
                                'number': 3,
                                'principal': '512.02',
                                'start': '2020-04-01'},
                            {'amount': '512.02',
                                'interest': '0',
                                'number': 4,
                                'principal': '512.02',
                                'start': '2020-05-01'},
                            {'amount': '512.02',
                                'interest': '0',
                                'number': 5,
                                'principal': '512.02',
                                'start': '2020-06-01'},
                            {'amount': '199487.98',
                                'interest': '0',
                                'number': 6,
                                'principal': '199487.98',
                                'start': '2020-07-01'},
                            {'amount': '199487.98',
                                'interest': '0',
                                'number': 7,
                                'principal': '199487.98',
                                'start': '2020-08-01'},
                            {'amount': '199487.98',
                                'interest': '0',
                                'number': 8,
                                'principal': '199487.98',
                                'start': '2020-09-01'},
                            {'amount': '199487.98',
                                'interest': '0',
                                'number': 9,
                                'principal': '199487.98',
                                'start': '2020-10-01'},
                            {'amount': '199487.98',
                                'interest': '0',
                                'number': 10,
                                'principal': '199487.98',
                                'start': '2020-11-01'},
                            ]},
                    ],
                },
            ]
