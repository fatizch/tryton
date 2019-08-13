# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool

from trytond.modules.api.api.core import amount_for_api, date_for_api
from trytond.modules.api.api.core import amount_from_api, date_from_api
from trytond.modules.api.api.core import DATE_SCHEMA, AMOUNT_SCHEMA, RATE_SCHEMA
from trytond.modules.coog_core.api import FIELD_SCHEMA, OBJECT_ID_SCHEMA
from trytond.modules.coog_core.api import REF_ID_SCHEMA


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
            result.append({'ref': loan_data['ref'], 'payments': payments})
        return result

    @classmethod
    def _loan_from_parameters(cls, parameters):
        pool = Pool()
        Loan = pool.get('loan')
        Address = pool.get('party.address')

        loan = Loan()
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

        if parameters.get('lender_address', None):
            loan.lender_address = Address(parameters['lender_address'])
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
            'items': cls._loan_schema(mode='compute'),
            }

    @classmethod
    def _loan_schema(cls, mode='full'):
        '''
            Schema for a loan in APIs

            mode=full means ready for creation
            mode=compute means minimum required data for computing the payments
        '''
        return {
            'oneOf': [
                cls._loan_interest_free_schema(mode=mode),
                cls._loan_fixed_rate_schema(mode=mode),
                cls._loan_intermediate_schema(mode=mode),
                cls._loan_graduated_schema(mode=mode),
                ],
            }

    @classmethod
    def _loan_base_schema(cls, mode='full'):
        schema = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'ref': {'type': 'string'},
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
                'lender_address': {'type': 'integer'},
                },
            'required': ['ref', 'kind', 'amount', 'funds_release_date',
                'duration'],
            'dependencies': {
                'deferral_duration': {'required': ['deferral']},
                },
            }
        if mode == 'full':
            schema['required'].append('lender_address')
        return schema

    @classmethod
    def _loan_interest_free_schema(cls, mode='full'):
        schema = cls._loan_base_schema(mode=mode)
        schema['properties']['kind'] = {'const': 'interest_free'}

        # In case of deferral, its kind is irrelevant
        del schema['properties']['deferral']
        del schema['dependencies']['deferral_duration']
        if len(schema['dependencies']) == 0:
            del schema['dependencies']
        return schema

    @classmethod
    def _loan_fixed_rate_schema(cls, mode='full'):
        schema = cls._loan_base_schema(mode=mode)
        schema['properties']['kind'] = {'const': 'fixed_rate'}
        schema['properties']['rate'] = RATE_SCHEMA
        schema['required'].append('rate')
        return schema

    @classmethod
    def _loan_intermediate_schema(cls, mode='full'):
        schema = cls._loan_base_schema(mode=mode)
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
    def _loan_graduated_schema(cls, mode='full'):
        schema = cls._loan_base_schema(mode=mode)
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
                    'ref': {'type': 'string'},
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
        return [cls._create_loan_convert_input(x) for x in parameters]

    @classmethod
    def _create_loan_convert_input(cls, loan_data):
        API = Pool().get('api')
        loan_data['amount'] = amount_from_api(loan_data['amount'])
        loan_data['funds_release_date'] = date_from_api(
            loan_data['funds_release_date'])
        if 'first_payment_date' in loan_data:
            loan_data['first_payment_date'] = date_from_api(
                loan_data['first_payment_date'])
        if 'rate' in loan_data:
            loan_data['rate'] = amount_from_api(loan_data['rate'])
        loan_data['currency'] = API.instance_from_code(
            'currency.currency', loan_data['currency'])

        for increment in loan_data.get('increments', []):
            if increment.get('payment_amount', None):
                increment['payment_amount'] = amount_from_api(
                    increment['payment_amount'])
            else:
                increment['payment_amount'] = None
            if increment.get('rate', None):
                increment['rate'] = amount_from_api(increment['rate'])
            else:
                increment['rate'] = None

        if loan_data.get('lender_address', None):
            loan_data['lender_address'] = API.instantiate_code_object(
                'party.address', {'id': loan_data['lender_address']})
        return loan_data

    @classmethod
    def _compute_loan_examples(cls):
        # Will be used for tests, so inputs / outputs should be consistent
        return [
            {
                'input': [
                    {
                        'ref': '1',
                        'amount': '100000.00',
                        'kind': 'fixed_rate',
                        'rate': '0.04',
                        'funds_release_date': '2020-01-01',
                        'duration': 10,
                        },
                    {
                        'ref': '2',
                        'amount': '100000.00',
                        'kind': 'interest_free',
                        'funds_release_date': '2020-01-01',
                        'duration': 10,
                        },
                    {
                        'ref': '3',
                        'amount': '100000.00',
                        'rate': '0.06',
                        'kind': 'intermediate',
                        'funds_release_date': '2020-01-01',
                        'duration': 10,
                        },
                    {
                        'ref': '4',
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
                        'ref': '1',
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
                        'ref': '2',
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
                        'ref': '3',
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
                        'ref': '4',
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

    @classmethod
    def _subscribe_contracts_create_priorities(cls):
        return ['loans'] + \
            super()._subscribe_contracts_create_priorities()

    @classmethod
    def _subscribe_contracts_create_loans(cls, parameters, created, options):
        cls._create_loans(parameters, created, options)

    @classmethod
    def _subscribe_contracts_result(cls, created):
        result = super()._subscribe_contracts_result(created)

        if 'loans' in created:
            result['loans'] = []
            for ref, instance in created['loans'].items():
                result['loans'].append({'ref': ref, 'id': instance.id})
        return result

    @classmethod
    def _update_contract_parameters(cls, contract_data, created):
        super()._update_contract_parameters(contract_data, created)

        for covered in contract_data.get('covereds', []):
            for option in covered.get('coverages', []):
                for loan_share in option.get('loan_shares', []):
                    if isinstance(loan_share['loan'], dict):
                        loan_share['loan'] = created['loans'][
                            loan_share['loan']['ref']]

    @classmethod
    def _subscribe_contracts_convert_input(cls, parameters):
        parameters = super()._subscribe_contracts_convert_input(parameters)

        if 'loans' in parameters:
            parameters['loans'] = [cls._create_loan_convert_input(x)
                for x in parameters['loans']]
        return parameters

    @classmethod
    def _contract_option_convert(cls, data, options, parameters):
        super()._contract_option_convert(data, options, parameters)

        pool = Pool()
        API = pool.get('api')

        loan_shares = data.get('loan_shares', [])
        if loan_shares and not data['coverage'].is_loan:
            API.add_input_error({
                    'type': 'coverage_is_not_loan',
                    'data': {
                        'coverage': data['coverage'].code,
                        },
                    })

        parameters_loans = {x['ref'] for x in parameters.get('loans', [])}
        for share_data in loan_shares:
            if 'id' in share_data['loan']:
                # Instantiate, checking it actually exists
                share_data['loan'] = API.instantiate_code_object(
                    'loan', share_data['loan'])
            else:
                # Schema enforces ref
                if share_data['loan']['ref'] not in parameters_loans:
                    API.add_input_error({
                            'type': 'bad_reference',
                            'data': {
                                'model': 'loan',
                                'reference': share_data['loan']['ref'],
                                },
                            })
            share_data['share'] = amount_from_api(share_data['share'])

        if data['coverage'].is_loan and not loan_shares:
            API.add_input_error({
                    'type': 'missing_loan_shares',
                    'data': {
                        'coverage': data['coverage'].code,
                        },
                    })

    @classmethod
    def _create_loans(cls, parameters, created, options):
        loans = []
        for loan_data in parameters.get('loans', []):
            loans.append(cls._loan_from_parameters(loan_data))
            loans[-1].calculate()

        Pool().get('loan').save(loans)
        created['loans'] = {}
        for loan, loan_data in zip(loans, parameters.get('loans', [])):
            created['loans'][loan_data['ref']] = loan

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)

        ContractLoan = Pool().get('contract-loan')

        loans = set()
        for covered in contract.covered_elements:
            for option in covered.options:
                for share in option.loan_shares:
                    loans.add(share.loan.id)

        ordered_loans = []
        for idx, loan_id in enumerate(sorted(loans)):
            ordered_loans.append(ContractLoan(loan=loan_id, number=idx + 1))
        contract.ordered_loans = ordered_loans

        return contract

    @classmethod
    def _create_covered_option(cls, option_data, covered, contract, created):
        option = super()._create_covered_option(option_data, covered, contract,
            created)

        LoanShare = Pool().get('loan.share')
        loan_shares = []
        for share in option_data.get('loan_shares', []):
            loan_shares.append(LoanShare(
                    loan=share['loan'],
                    share=share['share'],
                    ))

        option.loan_shares = loan_shares
        return option

    @classmethod
    def _subscribe_contracts_schema(cls, minimum=False):
        schema = super()._subscribe_contracts_schema(minimum=minimum)
        schema['properties']['loans'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._loan_schema(mode='full'),
            }
        return schema

    @classmethod
    def _contract_option_schema(cls, minimum=False):
        schema = super()._contract_option_schema(minimum=minimum)
        schema['properties']['loan_shares'] = {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'loan': REF_ID_SCHEMA,
                    'share': RATE_SCHEMA,
                    },
                'required': ['loan', 'share'],
                },
            }
        return schema

    @classmethod
    def _subscribe_contracts_output_schema(cls):
        schema = super()._subscribe_contracts_output_schema()
        schema['properties']['loans'] = {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'ref': {'type': 'string'},
                    'id': OBJECT_ID_SCHEMA,
                    },
                'required': ['ref', 'id'],
                },
            }
        return schema

    @classmethod
    def _subscribe_contracts_examples(cls):
        examples = super()._subscribe_contracts_examples()
        examples.append({
                # We must do this because we add a new case, so depending on
                # the modules dependency resolution order the json schema might
                # fail
                # It will still be properly tested in unittests though
                'disable_schema_tests': True,
                'input': {
                    'loans': [
                        {
                            'ref': '1',
                            'amount': '100000.00',
                            'kind': 'fixed_rate',
                            'rate': '0.04',
                            'funds_release_date': '2020-01-01',
                            'duration': 10,
                            'lender_address': 3,
                            },
                        {
                            'ref': '2',
                            'amount': '100000.00',
                            'kind': 'interest_free',
                            'funds_release_date': '2020-01-01',
                            'duration': 10,
                            'lender_address': 3,
                            },
                        ],
                    'parties': [
                        {
                            'ref': '1',
                            'is_person': True,
                            'name': 'Doe',
                            'first_name': 'Mother',
                            'birth_date': '1978-01-14',
                            'gender': 'female',
                            'addresses': [
                                {
                                    'street': 'Somewhere along the street',
                                    'zip': '75002',
                                    'city': 'Paris',
                                    'country': 'fr',
                                    },
                                ],
                            },
                        {
                            'ref': '2',
                            'is_person': True,
                            'name': 'Doe',
                            'first_name': 'Father',
                            'birth_date': '1979-10-11',
                            'gender': 'male',
                            },
                        ],
                    'contracts': [
                        {
                            'ref': '1',
                            'product': {'code': 'my_loan_product'},
                            'subscriber': {'ref': '1'},
                            'extra_data': {},
                            'covereds': [
                                {
                                    'party': {'ref': '1'},
                                    'item_descriptor': {'code': 'person'},
                                    'coverages': [
                                        {
                                            'coverage': {
                                                'code': 'my_loan_coverage'},
                                            'extra_data': {},
                                            'loan_shares': [
                                                {
                                                    'loan': {'ref': '1'},
                                                    'share': '0.92',
                                                    },
                                                ],
                                            },
                                        ],
                                    },
                                {
                                    'party': {'ref': '2'},
                                    'item_descriptor': {'code': 'person'},
                                    'coverages': [
                                        {
                                            'coverage': {
                                                'code': 'my_loan_coverage'},
                                            'extra_data': {},
                                            'loan_shares': [
                                                {
                                                    'loan': {'ref': '1'},
                                                    'share': '0.5',
                                                    },
                                                {
                                                    'loan': {'ref': '2'},
                                                    'share': '0.8',
                                                    },
                                                ],
                                            },
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                'output': {
                    'loans': [
                        {'ref': '1', 'id': 1},
                        {'ref': '2', 'id': 2},
                        ],
                    'parties': [
                        {'ref': '1', 'id': 1},
                        {'ref': '2', 'id': 2},
                        ],
                    'contracts': [
                        {'ref': '1', 'id': 1, 'number': '12345'},
                        ],
                    },
                },
            )
        return examples
