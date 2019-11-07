# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
from trytond.modules.coog_core.api import CODED_OBJECT_ARRAY_SCHEMA
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
