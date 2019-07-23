# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api.api.core import AMOUNT_SCHEMA, amount_from_api


__name__ = [
    'APIProduct',
    'APIContract',
    ]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _contract_option_schema(cls, minimum=False):
        schema = super()._contract_option_schema(minimum=minimum)
        schema['properties']['coverage_amount'] = AMOUNT_SCHEMA
        return schema

    @classmethod
    def _contract_option_convert(cls, data, options, parameters):
        super()._contract_option_convert(data, options, parameters)

        if 'coverage_amount' in data:
            data['coverage_amount'] = amount_from_api(data['coverage_amount'])

    @classmethod
    def _validate_contract_option_input(cls, data):
        super()._validate_contract_option_input(data)

        API = Pool().get('api')
        if data['coverage'].coverage_amount_rules:
            if 'coverage_amount' not in data:
                API.add_input_error({
                        'type': 'missing_coverage_amount',
                        'data': {
                            'coverage': data['coverage'].code,
                            },
                        })

    @classmethod
    def _create_covered_option(cls, option_data, covered, contract, created):
        option = super()._create_covered_option(option_data, covered, contract,
            created)
        if 'coverage_amount' in option_data:
            option.current_coverage_amount = option_data['coverage_amount']
            option.versions[-1].coverage_amount = option_data['coverage_amount']
        return option
