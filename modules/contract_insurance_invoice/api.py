# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext
from trytond.transaction import Transaction

from trytond.modules.coog_core import coog_date

from trytond.modules.api import DATE_SCHEMA, api_input_error_manager
from trytond.modules.api.api.core import POSITIVE_AMOUNT_SCHEMA, amount_for_api
from trytond.modules.api.api.core import date_for_api
from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA, CODE_SCHEMA
from trytond.modules.coog_core.api import MODEL_REFERENCE
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA
from trytond.modules.contract.api import CONTRACT_SCHEMA
from trytond.modules.party_cog.api import PARTY_RELATION_SCHEMA


DEFAULT_BANK_ACCOUNT_NUMBER_FOR_QUOTATION = 'NL39RABO4220533664'


__all__ = [
    'APIProduct',
    'APIContract',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        result = super()._describe_product(product)
        result['billing_configuration'] = {
            # Hack because order is not always set (though it should be)
            'billing_modes': [
                dict(sequence=idx, **cls._describe_billing_mode(x.billing_mode))
                for idx, x in enumerate(
                    product.billing_rules[0].ordered_billing_modes)],
            'billing_rule': bool(product.billing_rules[0].rule),
            'payer': cls._describe_payer(product),
            }
        return result

    @classmethod
    def _describe_payer(cls, product):
        return {
            'model': 'party',
            'required': ['name', 'first_name', 'birth_date', 'email',
                'address', 'bank_account'],
            'fields': ['name', 'first_name', 'birth_date', 'email',
                'phone_number', 'is_person', 'address', 'bank_account'],
            }

    @classmethod
    def _describe_billing_mode(cls, billing_mode):
        result = {
            'id': billing_mode.id,
            'name': billing_mode.name,
            'code': billing_mode.code,
            'frequency': billing_mode.frequency_string,
            'is_direct_debit': bool(billing_mode.direct_debit),
            }
        if billing_mode.direct_debit:
            result['direct_debit_days'] = [int(x[0])
                for x in billing_mode.get_allowed_direct_debit_days()]
        return result

    @classmethod
    def _describe_product_schema(cls):
        schema = super()._describe_product_schema()
        schema['properties']['billing_configuration'] = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'billing_modes': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._describe_billing_mode_schema(),
                    },
                'billing_rule': {'type': 'boolean'},
                'payer': MODEL_REFERENCE,
                },
            'required': ['billing_modes', 'billing_rule', 'payer'],
            }
        schema['required'].append('billing_configuration')
        return schema

    @classmethod
    def _describe_billing_mode_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'code': CODE_SCHEMA,
                'name': {'type': 'string'},
                'frequency': {'type': 'string'},
                'is_direct_debit': {'type': 'boolean'},
                'sequence': {'type': 'integer'},
                'direct_debit_days': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {'type': 'integer'},
                    },
                },
            'required': ['id', 'code', 'name', 'frequency',
                'is_direct_debit', 'sequence'],
            }

    @classmethod
    def _describe_products_examples(cls):
        examples = super()._describe_products_examples()
        for example in examples:
            for description in example['output']:
                description['billing_configuration'] = {
                    'billing_modes': [
                        {
                            'id': 1,
                            'code': 'freq_yearly',
                            'name': 'Yearly (synced on 01/01)',
                            'frequency': 'Yearly',
                            'is_direct_debit': False,
                            'sequence': 0,
                            },
                        ],
                    'billing_rule': False,
                    'payer': {
                        'model': 'party',
                        'required': ['name', 'first_name', 'birth_date',
                            'email', 'address', 'bank_account'],
                        'fields': ['name', 'first_name', 'birth_date', 'email',
                            'phone_number', 'is_person', 'address',
                            'bank_account'],
                        }
                    }
        return examples


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'compute_billing_modes': {
                    'public': False,
                    'readonly': True,
                    'description': 'Compute updated available billing modes '
                    'based on the quotation informations'
                    },
                'payment_schedule': {
                    'public': False,
                    'readonly': True,
                    'description': 'Returns the payment schedule for contracts',
                    },
                'simulate': {
                    'public': False,
                    'readonly': True,
                    'description': 'Compute predicted payments amounts based '
                    'on provided informations',
                    },
                },
            )

    @classmethod
    def _create_contract(cls, contract_data, created):
        contract = super()._create_contract(contract_data, created)
        contract.billing_informations = [
            cls._create_contract_billing_information(contract_data, created)]
        return contract

    @classmethod
    def _create_contract_billing_information(cls, contract_data, created):
        billing_information = Pool().get('contract.billing_information')()
        billing_mode = contract_data['billing']['billing_mode']

        billing_information.billing_mode = billing_mode
        billing_information.payer = contract_data['billing']['payer']
        billing_information.payment_term = \
            billing_mode.ordered_payment_terms[0].payment_term

        if billing_mode.direct_debit:
            if 'bank_account_number' in contract_data['billing']:
                account, = [x
                    for x in contract_data['billing']['payer'].bank_accounts
                    if x.numbers[0].number_compact ==
                    contract_data['billing']['bank_account_number']]
            elif contract_data['billing']['payer'].bank_accounts:
                account = contract_data['billing']['payer'].bank_accounts[-1]
            else:
                # When computing premiums, the billing account may not yet be
                # available
                account = None
            billing_information.direct_debit_account = account
            billing_information.direct_debit_day = contract_data['billing'][
                'direct_debit_day']

        return billing_information

    @classmethod
    def _update_contract_parameters(cls, contract_data, created):
        super()._update_contract_parameters(contract_data, created)
        if (isinstance(contract_data['billing']['payer'], dict) and
                    'ref' in contract_data['billing']['payer']):
            contract_data['billing']['payer'] = created['parties'][
                contract_data['billing']['payer']['ref']]
        elif contract_data['billing']['payer'] is None:
            contract_data['billing']['payer'] = contract_data['subscriber']

    @classmethod
    def _check_updated_contract_parameters(cls, contract_data):
        super()._check_updated_contract_parameters(contract_data)
        cls._check_contract_parameters_payer(contract_data)

    @classmethod
    def _check_contract_parameters_payer(cls, contract_data):
        API = Pool().get('api')

        billing_mode = contract_data['billing']['billing_mode']
        subscriber = contract_data['subscriber']
        payer = contract_data['billing']['payer']

        if billing_mode.direct_debit and not payer.bank_accounts:
            API.add_input_error({
                    'type': 'missing_bank_account',
                    'data': {
                        'party': payer.full_name,
                        },
                    })

        if payer != subscriber:
            if payer.id not in [x.to.id for x in subscriber.relations
                    if x.type.code == 'subsidized']:
                API.add_input_error({
                        'type': 'invalid_payer_subscriber_relation',
                        'data': {
                            'subscriber': subscriber.full_name,
                            'payer': payer.full_name,
                            },
                        })

        if 'bank_account_number' in contract_data['billing']:
            if len([x for x in payer.bank_accounts
                        if x.numbers[0].number_compact ==
                        contract_data['billing']['bank_account_number']]) != 1:
                API.add_input_error({
                        'type': 'unknown_bank_account_number',
                        'data': {
                            'number':
                            contract_data['billing']['bank_account_number'],
                            'party': payer.full_name,
                            },
                        })

    @classmethod
    def _contract_convert(cls, data, options, parameters, minimum=False):
        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        super()._contract_convert(data, options, parameters, minimum=minimum)

        if minimum is False or 'billing' in data:
            data['billing']['billing_mode'] = API.instantiate_code_object(
                'offered.billing_mode', data['billing']['billing_mode'])
            if 'payer' not in data['billing']:
                data['billing']['payer'] = data['subscriber']

            payer = PartyAPI._party_from_reference(
                data['billing']['payer'], parties=parameters['parties'])
            # Only if already exists
            if payer:
                data['billing']['payer'] = payer
        else:
            data['billing'] = {
                'payer': None,  # Will be set from the subscriber later on
                'billing_mode': data['product'].get_default_billing_mode(),
                }

    @classmethod
    def _validate_contract_input(cls, data):
        API = Pool().get('api')

        super()._validate_contract_input(data)

        billing_mode = data['billing']['billing_mode']
        if (billing_mode not in data['product'].billing_rules[0].billing_modes):
            API.add_input_error({
                    'type': 'invalid_billing_mode',
                    'data': {
                        'product': data['product'].code,
                        'billing_mode': billing_mode.code,
                        'allowed_billing_modes': sorted(x.code for x in
                            data['product'].billing_rules[0].billing_modes),
                        },
                    })
        if billing_mode.direct_debit:
            if 'direct_debit_day' not in data['billing']:
                API.add_input_error({
                        'type': 'missing_direct_debit_day',
                        'data': {
                            'product': data['product'].code,
                            'billing_mode': billing_mode.code,
                            },
                        })
        else:
            if 'direct_debit_day' in data['billing']:
                API.add_input_error({
                        'type': 'unused_direct_debit_day',
                        'data': {
                            'product': data['product'].code,
                            'billing_mode': billing_mode.code,
                            },
                        })
            if 'bank_account_number' in data['billing']:
                API.add_input_error({
                        'type': 'unused_bank_account_number',
                        'data': {
                            'product': data['product'].code,
                            'billing_mode': billing_mode.code,
                            },
                        })

    @classmethod
    def _contract_schema(cls, minimum=False):
        schema = super()._contract_schema(minimum=minimum)
        schema['properties']['billing'] = cls._contract_billing_schema()

        if not minimum:
            schema['required'].append('billing')

        return schema

    @classmethod
    def _contract_billing_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'payer': PARTY_RELATION_SCHEMA,
                'billing_mode': CODED_OBJECT_SCHEMA,
                'direct_debit_day': {'type': 'integer'},
                'bank_account_number': {'type': 'string'},
                },
            'required': ['billing_mode'],
            }

    @classmethod
    def _subscribe_contracts_example_finalize(cls, example):
        for contract in example['input']['contracts']:
            contract['billing'] = {
                'payer': {
                    'ref': example['input']['parties'][0]['ref']},
                'billing_mode': {'code': 'quarterly'},
                }
        return example

    @classmethod
    def compute_billing_modes(cls, parameters):
        APIProduct = Pool().get('api.product')

        result = []
        for contract_data in parameters['contracts']:
            result.append({
                    'ref': contract_data['ref'],
                    'billing_modes': [
                        dict(sequence=idx,
                            **APIProduct._describe_billing_mode(x))
                        for idx, x in enumerate(
                            cls._compute_billing_modes(
                                contract_data, parameters))],
                    }
                )

        return result

    @classmethod
    def _compute_billing_modes(cls, contract_data, parameters):
        billing_rule = contract_data['product'].billing_rules[0]

        APIRuleRuntime = Pool().get('api.rule_runtime')

        with ServerContext().set_context(
                api_rule_context=APIRuleRuntime.get_runtime()):
            args = cls._init_contract_rule_engine_parameters(contract_data,
                parameters)
            return billing_rule.calculate_available_billing_modes(args)

    @classmethod
    def _compute_billing_modes_convert_input(cls, parameters):
        return cls._subscribe_contracts_convert_input(parameters, minimum=True)

    @classmethod
    def _compute_billing_modes_schema(cls):
        return cls._subscribe_contracts_schema(minimum=True)

    @classmethod
    def _compute_billing_modes_output_schema(cls):
        APIProduct = Pool().get('api.product')

        return {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'ref': {'type': 'string'},
                    'billing_modes': {
                        'type': 'array',
                        'additionalItems': False,
                        'items': APIProduct._describe_billing_mode_schema(),
                        },
                    },
                'required': ['ref', 'billing_modes'],
                }
            }

    @classmethod
    def _compute_billing_modes_examples(cls):
        return [
            {
                'input': {
                    'parties': [
                        {
                            'ref': '1',
                            'is_person': True,
                            'name': 'Doe',
                            'first_name': 'John',
                            'birth_date': '1969-06-15',
                            'gender': 'male',
                            },
                        ],
                    'contracts': [
                        {
                            'ref': '1',
                            'subscriber': {'ref': '1'},
                            'product': {'code': 'my_product'},
                            'extra_data': {
                                'my_extra_1': True,
                                'my_extra_2': 'no',
                                },
                            },
                        ],
                    },
                'output': [
                    {
                        'ref': '1',
                        'billing_modes': [
                            {
                                'id': 1,
                                'code': 'freq_yearly',
                                'name': 'Yearly (synced on 01/01)',
                                'frequency': 'Yearly',
                                'is_direct_debit': False,
                                'sequence': 0,
                                },
                            {
                                'id': 4,
                                'code': 'freq_monthly',
                                'name': 'Monthly (sepa)',
                                'frequency': 'Yearly',
                                'is_direct_debit': True,
                                'sequence': 10,
                                'direct_debit_days': [1, 5, 10],
                                },
                            ],
                        }
                    ],
                },
            ]

    @classmethod
    def payment_schedule(cls, parameters):
        return [cls._payment_schedule_from_contract(contract)
            for contract in parameters['contracts']]

    @classmethod
    def _payment_schedule_from_contract(cls, contract):
        if contract.end_date:
            to_date = contract.end_date
        else:
            # Contract without an end date, we arbitrarly decide that we will
            # compute one year worth of invoices
            to_date = coog_date.add_day(
                coog_date.add_year(contract.initial_start_date, 1), -1)

        invoices = contract.get_future_invoices(contract, to_date=to_date)
        result = {
            'contract': {
                'id': contract.id,
                'number': contract.rec_name,
                },
            'schedule': [
                cls._payment_schedule_format_invoice(invoice)
                for invoice in invoices
                ],
            }
        total_amount, total_fee = Decimal(0), Decimal(0)
        total_tax, total_total = Decimal(0), Decimal(0)

        for invoice_data in invoices:
            total_amount += invoice_data['amount']
            total_fee += invoice_data['fee']
            total_tax += invoice_data['tax_amount']
            total_total += invoice_data['total_amount']

        result['total_premium'] = amount_for_api(total_amount)
        result['total_fee'] = amount_for_api(total_fee)
        result['total_tax'] = amount_for_api(total_tax)
        result['total'] = amount_for_api(total_total)
        return result

    @classmethod
    def _payment_schedule_format_invoice(cls, invoice):
        return {
            'premium': amount_for_api(invoice['amount']),
            'currency_symbol': invoice['currency_symbol'],
            'details': [
                cls._payment_schedule_format_invoice_detail(detail)
                for detail in invoice['details']
                ],
            'end': date_for_api(invoice['end']),
            'fee': amount_for_api(invoice['fee']),
            'start': date_for_api(invoice['start']),
            'tax': amount_for_api(invoice['tax_amount']),
            'total': amount_for_api(invoice['total_amount']),
        }

    @classmethod
    def _payment_schedule_format_invoice_detail(cls, detail):
        detail_json = {
            'premium': amount_for_api(detail['amount']),
            'end': date_for_api(detail['end']),
            'fee': amount_for_api(detail['fee']),
            'name': detail['name'],
            'start': date_for_api(detail['start']),
            'tax': amount_for_api(detail['tax_amount']),
            'total': amount_for_api(detail['total_amount']),
            'origin': cls._payment_schedule_invoice_detail_origin(detail),
            }

        return detail_json

    @classmethod
    def _payment_schedule_invoice_detail_origin(cls, detail):
        result = {}
        option = None

        if detail['premium'].option:
            option = detail['premium'].option
        elif detail['premium'].extra_premium:
            option = detail['premium'].extra_premium.option
            result['extra_premium'] = {
                'id': detail['premium'].extra_premium.motive.id,
                'code': detail['premium'].extra_premium.motive.code,
                }
        if option is not None:
            result['option'] = {
                'id': option.id,
                'coverage': {
                    'code': option.coverage.code,
                    'id': option.coverage.id,
                    },
                }
            if option.covered_element:
                result['covered'] = {
                    'id': option.covered_element.id,
                    }
                if option.covered_element.party:
                    result['covered']['party'] = {
                        'id': option.covered_element.party.id,
                        'code': option.covered_element.party.code,
                        'name': option.covered_element.party.full_name,
                        }
        if detail['premium'].fee:
            result['fee'] = {
                'id': detail['premium'].fee.fee.id,
                'code': detail['premium'].fee.fee.code,
                }
        return result

    @classmethod
    def _payment_schedule_convert_input(cls, parameters):
        parameters['contracts'] = [
            cls._get_contract(x) for x in parameters['contracts']]
        return parameters

    @classmethod
    def _payment_schedule_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'contracts': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': CONTRACT_SCHEMA,
                    'minItems': 1,
                    }
                },
            'required': ['contracts'],
            }

    @classmethod
    def _payment_schedule_output_schema(cls):
        return {
            'type': 'array',
            'additionalItems': False,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'contract': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'id': OBJECT_ID_SCHEMA,
                            'number': CODE_SCHEMA,
                            }
                        },
                    'schedule': {
                        'type': 'array',
                        'additionalItems': False,
                        'items': cls._payment_schedule_invoice_schema(),
                        },
                    'total_premium': POSITIVE_AMOUNT_SCHEMA,
                    'total_fee': POSITIVE_AMOUNT_SCHEMA,
                    'total_tax': POSITIVE_AMOUNT_SCHEMA,
                    'total': POSITIVE_AMOUNT_SCHEMA,
                    },
                },
            }

    @classmethod
    def _payment_schedule_invoice_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'currency_symbol': {'type': 'string'},
                'details': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._payment_schedule_invoice_detail_schema(),
                    },
                'end': DATE_SCHEMA,
                'fee': POSITIVE_AMOUNT_SCHEMA,
                'premium': POSITIVE_AMOUNT_SCHEMA,
                'start': DATE_SCHEMA,
                'tax': POSITIVE_AMOUNT_SCHEMA,
                'total': POSITIVE_AMOUNT_SCHEMA,
                },
            }

    @classmethod
    def _payment_schedule_invoice_detail_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'end': DATE_SCHEMA,
                'fee': POSITIVE_AMOUNT_SCHEMA,
                'name': {'type': 'string'},
                'premium': POSITIVE_AMOUNT_SCHEMA,
                'start': DATE_SCHEMA,
                'tax': POSITIVE_AMOUNT_SCHEMA,
                'total': POSITIVE_AMOUNT_SCHEMA,
                'origin': cls._payment_schedule_detail_origin_schema(),
                },
            }

    @classmethod
    def _payment_schedule_detail_origin_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'covered': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'id': OBJECT_ID_SCHEMA,
                        'party': {
                            'type': 'object',
                            'additionalProperties': False,
                            'properties': {
                                'id': OBJECT_ID_SCHEMA,
                                'code': CODE_SCHEMA,
                                'name': {'type': 'string'},
                                },
                            },
                        },
                    },
                'option': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['coverage'],
                    'properties': {
                        'id': OBJECT_ID_SCHEMA,
                        'coverage': {
                            'type': 'object',
                            'additionalProperties': False,
                            'properties': {
                                'id': OBJECT_ID_SCHEMA,
                                'code': CODE_SCHEMA,
                                },
                            },
                        },
                    },
                'extra_premium': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'id': OBJECT_ID_SCHEMA,
                        'code': CODE_SCHEMA,
                        },
                    },
                'fee': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'id': OBJECT_ID_SCHEMA,
                        'code': CODE_SCHEMA,
                        },
                    },
                },
            }

    @classmethod
    def _payment_schedule_examples(cls):
        return [
            {
                'input': {
                    'contracts': [{'id': 1}],
                    },
                'output': [
                    {
                        'contract': {
                            'id': 1,
                            'number': '1',
                            },
                        'schedule': [
                            {
                                'currency_symbol': '€',
                                'details': [
                                    {
                                        'end': '2019-12-31',
                                        'fee': '0',
                                        'name': 'Fire Damage',
                                        'origin': {
                                            'covered': {'id': 1},
                                            'option': {
                                                'coverage': {
                                                    'code': 'fire_coverage',
                                                    'id': 2,
                                                    },
                                                'id': 2,
                                                },
                                            },
                                        'premium': '1323.00',
                                        'start': '2019-01-01',
                                        'tax': '0.00',
                                        'total': '1323.00',
                                        },
                                    {
                                        'end': '2019-12-31',
                                        'fee': '0',
                                        'name': 'Fire Damage 10%',
                                        'origin': {
                                            'covered': {'id': 1},
                                            'extra_premium': {
                                                'id': 10,
                                                'code': 'earthquakes',
                                                },
                                            'option': {
                                                'coverage': {
                                                    'code': 'fire_coverage',
                                                    'id': 2,
                                                    },
                                                'id': 2,
                                                },
                                            },
                                        'premium': '132.30',
                                        'start': '2019-01-01',
                                        'tax': '0.00',
                                        'total': '132.30',
                                        },
                                    {
                                        'end': '2019-12-31',
                                        'fee': '0',
                                        'name': 'Water Damage',
                                        'origin': {
                                            'covered': {'id': 1},
                                            'option': {
                                                'coverage': {
                                                    'code': 'water_coverage',
                                                    'id': 1,
                                                    },
                                                'id': 1,
                                                },
                                            },
                                        'premium': '56.26',
                                        'start': '2019-01-01',
                                        'tax': '0.00',
                                        'total': '56.26',
                                        },
                                    ],
                                'end': '2019-12-31',
                                'fee': '0',
                                'premium': '1511.56',
                                'start': '2019-01-01',
                                'tax': '0.00',
                                'total': '1511.56',
                                },
                            ],
                        'total': '1511.56',
                        'total_fee': '0',
                        'total_premium': '1511.56',
                        'total_tax': '0.00',
                        },
                    ],
                },
            ]

    @classmethod
    def simulate(cls, parameters):
        with Transaction().new_transaction() as transaction:
            with Transaction().set_context(_will_be_rollbacked=True,
                    _disable_validations=True):
                with Transaction().set_user(0):
                    try:
                        created = cls._simulate_create_contracts(
                            parameters)

                        cls._simulate_parse_created(created)
                        contracts = created['contract_instances']
                        cls._simulate_prepare_contracts(contracts,
                            parameters)

                        results = []
                        for contract in contracts:
                            result = cls._simulate_get_schedule(
                                contract, parameters, created)
                            result.pop('contract')
                            result['ref'] = created['contract_ref_per_id'][
                                contract.id]
                            results.append(result)
                        return results
                    finally:
                        transaction.rollback()

    @classmethod
    def _simulate_parse_created(cls, created):
        Contract = Pool().get('contract')
        created['party_ref_per_id'] = {
            x['id']: x['ref'] for x in created['parties']}
        created['contract_ref_per_id'] = {
            x['id']: x['ref'] for x in created['contracts']}
        created['contract_instances'] = Contract.browse(
            [x['id'] for x in created['contracts']])

    @classmethod
    def _simulate_create_contracts(cls, parameters):
        # Make sure we do not inadvertently activate the contract :)
        parameters['options'] = {}

        # Hardcore
        with api_input_error_manager():
            Pool().get('api').ignore_input_errors('missing_bank_account')

            return getattr(cls.subscribe_contracts, '__origin_function')(
                cls, parameters)

    @classmethod
    def _simulate_prepare_contracts(cls, contracts, parameters):
        Contract = Pool().get('contract')
        Contract.calculate(contracts)

    @classmethod
    def _simulate_get_schedule(cls, contract, parameters, created):
        schedule_data = cls._payment_schedule_from_contract(contract)
        cls._simulate_cleanup_schedule(schedule_data, created)
        return schedule_data

    @classmethod
    def _simulate_cleanup_schedule(cls, schedule_data, created):
        for invoice_data in schedule_data['schedule']:
            for detail_data in invoice_data['details']:
                cls._simulate_cleanup_schedule_detail(
                    detail_data, created)

    @classmethod
    def _simulate_cleanup_schedule_detail(cls, detail, created):
        if 'option' in detail['origin']:
            del detail['origin']['option']['id']
        if 'covered' in detail['origin']:
            del detail['origin']['covered']['id']
            if 'party' in detail['origin']['covered']:
                party_id = detail['origin']['covered']['party']['id']
                if party_id in created['party_ref_per_id']:
                    del detail['origin']['covered']['party']['id']
                    del detail['origin']['covered']['party']['code']
                    detail['origin']['covered']['party']['ref'] = created[
                        'party_ref_per_id'][party_id]

    @classmethod
    def _simulate_schema(cls):
        schema = cls._subscribe_contracts_schema(minimum=True)
        for kind in schema['properties']['parties']['items']['oneOf']:
            kind['required'] = ['ref']
        return schema

    @classmethod
    def _simulate_convert_input(cls, parameters):
        cls._simulate_convert_input_parties(parameters)
        result = cls._subscribe_contracts_convert_input(parameters,
            minimum=True)
        cls._simulate_convert_contract_input(parameters)
        return result

    @classmethod
    def _simulate_convert_input_parties(cls, parameters):
        for party_data in parameters.get('parties', []):
            if 'name' not in party_data:
                party_data['name'] = 'Temp Name %s' % party_data['ref']
            if 'is_person' in party_data:
                if 'first_name' not in party_data:
                    party_data['first_name'] = \
                        'Temp First Name %s' % party_data['ref']
                if 'gender' not in party_data:
                    party_data['gender'] = 'male'

    @classmethod
    def _simulate_convert_contract_input(cls, parameters):
        for contract_data in parameters['contracts']:
            if 'direct_debit_day' in contract_data['billing']:
                continue
            billing_mode = contract_data['billing']['billing_mode']
            if billing_mode.direct_debit:
                if billing_mode.allowed_direct_debit_days:
                    contract_data['billing']['direct_debit_day'] = \
                        billing_mode.get_allowed_direct_debit_days()[0][0]
                else:
                    contract_data['billing']['direct_debit_day'] = '1'

    @classmethod
    def _simulate_output_schema(cls):
        base = cls._payment_schedule_output_schema()
        del base['items']['properties']['contract']
        base['items']['properties']['ref'] = {'type': 'string'}

        cls._simulate_update_schedule_output_schema(base)
        return base

    @classmethod
    def _simulate_update_schedule_output_schema(cls, base):
        detail_schema = base['items']['properties']['schedule']['items'][
            'properties']['details']['items']
        cls._simulate_update_schedule_detail_output_schema(
            detail_schema)

    @classmethod
    def _simulate_update_schedule_detail_output_schema(cls,
            base):
        origin = base['properties']['origin']['properties']
        del origin['option']['properties']['id']
        del origin['covered']['properties']['id']
        del origin['covered']['properties']['party']['properties']['id']
        del origin['covered']['properties']['party']['properties']['code']
        origin['covered']['properties']['party']['properties']['ref'] = {
            'type': 'string'}

    @classmethod
    def _simulate_examples(cls):
        return [
            {
                'input': {
                    'parties': [
                        {
                            'ref': '1',
                            'is_person': True,
                            'birth_date': '1954-02-15',
                            },
                        {
                            'ref': '2',
                            'is_person': True,
                            'birth_date': '1992-01-12',
                            }
                        ],
                    'contracts': [
                        {
                            'ref': '1',
                            'subscriber': {
                                'ref': '1',
                                },
                            'product': {
                                'code': 'life_product',
                                },
                            'extra_data': {
                                'analyse_forcee': 'non',
                                },
                            'covereds': [
                                {
                                    'party': {
                                        'ref': '1',
                                        },
                                    'item_descriptor': {
                                        'code': 'life_person_item_desc',
                                        },
                                    'extra_data': {
                                        'job_category': 'csp2',
                                        },
                                    'coverages': [
                                        {
                                            'coverage': {
                                                'code': 'death_coverage',
                                                },
                                            'extra_data': {
                                                'double_for_accidents': True,
                                                },
                                            },
                                        ],
                                    },
                                {
                                    'party': {
                                        'ref': '2',
                                        },
                                    'item_descriptor': {
                                        'code': 'life_person_item_desc',
                                        },
                                    'extra_data': {
                                        'job_category': 'csp2',
                                        },
                                    'coverages': [
                                        {
                                            'coverage': {
                                                'code': 'death_coverage',
                                                },
                                            'extra_data': {
                                                'double_for_accidents': True,
                                                },
                                            },
                                        {
                                            'coverage': {
                                                'code': 'unemployment_coverage',
                                                },
                                            'extra_data': {
                                                'deductible_duration': '30',
                                                'per_day_amount': '150',
                                                },
                                            },
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                'output': [
                    {
                        'schedule': [
                            {
                                'premium': '254.59',
                                'currency_symbol': '€',
                                'details': [
                                    {
                                        'premium': '22.99',
                                        'end': '2020-10-10',
                                        'fee': '0',
                                        'name': 'Death',
                                        'start': '2019-10-11',
                                        'tax': '0.00',
                                        'total': '22.99',
                                        'origin': {
                                            'option': {
                                                'coverage': {
                                                    'code': 'death_coverage',
                                                    'id': 3,
                                                    },
                                                },
                                            'covered': {
                                                'party': {
                                                    'name': 'M. TEMP NAME 1 '
                                                    'Temp First Name 1',
                                                    'ref': '1',
                                                    },
                                                },
                                            },
                                        },
                                    {
                                        'premium': '70.90',
                                        'end': '2020-10-10',
                                        'fee': '0',
                                        'name': 'Death',
                                        'start': '2019-10-11',
                                        'tax': '0.00',
                                        'total': '70.90',
                                        'origin': {
                                            'option': {
                                                'coverage': {
                                                    'code': 'death_coverage',
                                                    'id': 3,
                                                    },
                                                },
                                            'covered': {
                                                'party': {
                                                    'name': 'M. TEMP NAME 2 '
                                                    'Temp First Name 2',
                                                    'ref': '2',
                                                    },
                                                },
                                            },
                                        },
                                    {
                                        'premium': '160.70',
                                        'end': '2020-10-10',
                                        'fee': '0',
                                        'name': 'Unemployment',
                                        'start': '2019-10-11',
                                        'tax': '0.00',
                                        'total': '160.70',
                                        'origin': {
                                            'option': {
                                                'coverage': {
                                                    'code':
                                                    'unemployment_coverage',
                                                    'id': 5,
                                                    },
                                                },
                                            'covered': {
                                                'party': {
                                                    'name': 'M. TEMP NAME 2 '
                                                    'Temp First Name 2',
                                                    'ref': '2',
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                'end': '2020-10-10',
                                'fee': '0',
                                'start': '2019-10-11',
                                'tax': '0.00',
                                'total': '254.59',
                                },
                            ],
                        'total_premium': '254.59',
                        'total_fee': '0',
                        'total_tax': '0.00',
                        'total': '254.59',
                        'ref': '1',
                        },
                    ],
                },
            ]
