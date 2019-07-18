# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext

from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA, CODE_SCHEMA
from trytond.modules.coog_core.api import MODEL_REFERENCE
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA
from trytond.modules.party_cog.api import PARTY_RELATION_SCHEMA

__name__ = [
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
            else:
                account = contract_data['billing']['payer'].bank_accounts[-1]
            billing_information.direct_debit_account = account
            billing_information.direct_debit_day = contract_data['billing'][
                'direct_debit_day']

        return billing_information

    @classmethod
    def _update_contract_parameters(cls, contract_data, created):
        super()._update_contract_parameters(contract_data, created)
        if 'ref' in contract_data['billing']['payer']:
            contract_data['billing']['payer'] = created['parties'][
                contract_data['billing']['payer']['ref']]

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
    def _contract_convert(cls, data, options, parameters):
        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        super()._contract_convert(data, options, parameters)

        if 'billing' in data:
            data['billing']['billing_mode'] = API.instantiate_code_object(
                'offered.billing_mode', data['billing']['billing_mode'])
            payer = PartyAPI._party_from_reference(data['billing']['payer'],
                parties=parameters['parties'])
            if payer:
                data['billing']['payer'] = payer

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
            'required': ['billing_mode', 'payer'],
            }

    @classmethod
    def _subscribe_contracts_examples(cls):
        examples = super()._subscribe_contracts_examples()
        for example in examples:
            for contract in example['input']['contracts']:
                contract['billing'] = {
                    'payer': {
                        'ref': example['input']['parties'][0]['ref']},
                    'billing_mode': {'code': 'quarterly'},
                    }
        return examples

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
                            cls._compute_billing_modes(contract_data))],
                    }
                )

        return result

    @classmethod
    def _compute_billing_modes(cls, contract_data):
        billing_rule = contract_data['product'].billing_rules[0]

        APIRuleRuntime = Pool().get('api.contract.rule_runtime')

        with ServerContext().set_context(
                api_rule_context=APIRuleRuntime.get_runtime()):
            args = cls._init_contract_rule_engine_parameters(contract_data)
            return billing_rule.calculate_available_billing_modes(args)

    @classmethod
    def _compute_billing_modes_convert_input(cls, parameters):
        return cls._subscribe_contracts_convert_input(parameters)

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
