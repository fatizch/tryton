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
        pool = Pool()
        API = pool.get('api')
        Contract = pool.get('contract')

        super()._subscribe_contracts_create_contracts(parameters, created,
            options)

        to_save = []
        for contract_data in parameters['contracts']:
            contract_discounts = contract_data.get('discounts')
            auto_discounts = [x for x in contract_discounts if
                any(rule.automatic for rule in x.rules)]
            if auto_discounts:
                API.add_input_error({
                        'type': 'forced_discount_is_automatic',
                        'data': [x.code for x in auto_discounts],
                        })

            contract = created['contracts'][contract_data['ref']]
            if contract_discounts:
                options = list(contract.covered_element_options) + list(
                    contract.options)
                new_modifications = contract.get_new_modifications(
                    options, contract.start_date, contract.end_date,
                    filter_on=contract_discounts)
                contract.discounts = new_modifications
            contract.init_automatic_discount()
            to_save.append(contract)

        if to_save:
            Contract.save(to_save)

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
        else:
            super(APIContract,
                cls)._simulate_update_premium_field(target, source)

    @classmethod
    def _simulate_init_premium_field(cls):
        res = super(APIContract, cls)._simulate_init_premium_field()
        res['premium']['discounts'] = []
        res['premium']['total_discounts'] = Decimal(0)
        return res

    @classmethod
    def _simulate_convert_premium_field(cls, premium):
        for key in premium:
            if key == 'discounts':
                premium['total_discounts'] = amount_for_api(
                    sum(discount['amount']
                        for discount in premium['discounts']) or Decimal(0))
                premium['discounts'] = [{
                        'code': discount['code'],
                        'amount': amount_for_api(discount['amount']),
                        } for discount in premium['discounts']]
            elif key != 'total_discounts':
                premium[key] = amount_for_api(premium[key])

    @classmethod
    def _simulate_premium_output_schema(cls):
        schema = super(APIContract, cls)._simulate_premium_output_schema()
        schema['premium']['properties']['total_discounts'] = AMOUNT_SCHEMA
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
