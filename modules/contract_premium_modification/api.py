# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
from decimal import Decimal

from trytond.modules.coog_core.api import CODED_OBJECT_ARRAY_SCHEMA, CODE_SCHEMA
from trytond.modules.api.api.core import AMOUNT_SCHEMA, amount_for_api
from trytond.pool import Pool, PoolMeta

__all__ = [
    'APIContract',
    ]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _contract_convert(cls, data, options, parameters, minimum=False):
        super()._contract_convert(data, options, parameters, minimum)
        API = Pool().get('api')
        data['discounts'] = [
            API.instantiate_code_object('commercial_discount', discount_data)
            for discount_data in data.get('discounts', [])]

    @classmethod
    def _validate_contract_input(cls, data):
        super()._validate_contract_input(data)
        API = Pool().get('api')
        all_coverages = [y['coverage'] for x in data['covereds']
            for y in x['coverages']]
        all_coverages.extend(x['coverage'] for x in data['coverages'])
        for discount in data['discounts']:
            if not any(coverage.is_discount_allowed(discount)
                    for coverage in all_coverages):
                API.add_input_error({
                        'type': 'invalid_discount_for_coverages',
                        'data': {
                            'discount': discount.code,
                            },
                        })

    @classmethod
    def _subscribe_contracts_create_contracts(cls, parameters, created,
            options):
        DiscountModification = Pool().get(
            'contract.premium_modification.discount')
        super()._subscribe_contracts_create_contracts(parameters, created,
            options)

        discount_modifications = []
        for contract_data in parameters['contracts']:
            contract_discounts = contract_data.get('discounts')
            if contract_discounts is None:
                continue
            contract = created['contracts'][contract_data['ref']]
            options = list(contract.covered_element_options) + list(
                contract.options)
            new_modifications = contract.get_new_modifications(
                options, contract.start_date, contract.end_date,
                modifications=contract_discounts)
            discount_modifications.extend(new_modifications)
            contract.discounts = discount_modifications

        if discount_modifications:
            DiscountModification.save(discount_modifications)

    @classmethod
    def _contract_schema(cls, minimum=False):
        schema = super()._contract_schema(minimum=minimum)
        schema['properties']['discounts'] = CODED_OBJECT_ARRAY_SCHEMA
        return schema

    @classmethod
    def _subscribe_contracts_examples(cls):
        examples = super()._subscribe_contracts_examples()
        for example in examples:
            example['input']['contracts'][0]['discounts'] = [
                {'code': 'welcome_discount'},
                {'id': 26},
                ]
        return examples

    @classmethod
    def _payment_schedule_format_invoice_detail(cls, detail):
        res = super(APIContract, cls)._payment_schedule_format_invoice_detail(
            detail)
        if 'discount' in detail:
            res['discount'] = {
                'code': detail['discount']['code'],
                'amount': amount_for_api(detail['discount']['amount']),
                }
        return res

    @classmethod
    def _payment_schedule_invoice_detail_schema(cls):
        schema = super(APIContract,
            cls)._payment_schedule_invoice_detail_schema()
        schema['properties']['discount'] = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'code': CODE_SCHEMA,
                'amount': AMOUNT_SCHEMA,
                }
            }
        schema['properties']['premium'] = AMOUNT_SCHEMA
        schema['properties']['total'] = AMOUNT_SCHEMA
        return schema

    @classmethod
    def _simulate_update_premium_field(cls, target, source):
        super(APIContract,
            cls)._simulate_update_premium_field(target, source)
        if 'discount' in source:
            amount = source['discount']['amount']
            code = source['discount']['code']
            discount = next((d for d in target['discounts']
                    if d['code'] == code), None)
            if discount:
                discount['amount'] += Decimal(amount)
            else:
                target['discounts'].append({
                        'code': code,
                        'amount': Decimal(amount),
                        })
            target['total'] += Decimal(amount)

    @classmethod
    def _simulate_init_premium_field(cls):
        res = super(APIContract, cls)._simulate_init_premium_field()
        res['premium']['discounts'] = []
        return res

    @classmethod
    def _simulate_convert_premium_field(cls, premium):
        for total in premium:
            if total == 'discounts':
                premium['discounts'] = [{
                        'code': discount['code'],
                        'amount': amount_for_api(discount['amount']),
                        } for discount in premium['discounts']]
            else:
                premium[total] = amount_for_api(premium[total])

    @classmethod
    def _simulate_premium_output_schema(cls):
        schema = super(APIContract, cls)._simulate_premium_output_schema()
        schema['premium']['properties']['discounts'] = {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'code': CODE_SCHEMA,
                    'amount': AMOUNT_SCHEMA,
                    }
                }
            }
        return schema
