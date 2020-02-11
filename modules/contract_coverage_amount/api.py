# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api.api.core import POSITIVE_AMOUNT_SCHEMA
from trytond.modules.api.api.core import amount_for_api, amount_from_api
from trytond.modules.coog_core.api import FIELD_SCHEMA
from trytond.modules.rule_engine import check_args


__name__ = [
    'APIProduct',
    'APIContract',
    'APIRuleRuntime',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_coverage(cls, coverage):
        Core = Pool().get('api.core')
        result = super()._describe_coverage(coverage)

        if coverage.coverage_amount_rules:
            rule = coverage.coverage_amount_rules[-1]
            if rule.amount_mode == 'calculated_amount':
                return result
            field_base = Core._field_description('contract.option.version',
                'coverage_amount', required=True, sequence=0,
                force_type='amount')
            if rule.amount_mode == 'selection':
                field_base['enum'] = [
                    str(x) for x in rule.calculate_rule({})]
            result['coverage_amount'] = field_base
        return result

    @classmethod
    def _describe_coverage_schema(cls):
        schema = super()._describe_coverage_schema()
        schema['properties']['coverage_amount'] = FIELD_SCHEMA
        return schema


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _create_option(cls, option_data, contract, created):
        option = super(APIContract, cls)._create_option(option_data, contract,
            created)
        if (option.coverage.coverage_amount_rules and
                option.coverage.coverage_amount_rules[0].amount_mode ==
                'calculated_amount'):
            option.versions[0].coverage_amount = \
                option.coverage.get_coverage_amount_rule_result({
                        'date': contract.start_date,
                        'person': contract.subscriber,
                        'contract': contract,
                        })
        return option

    @classmethod
    def _contract_option_schema(cls, minimum=False):
        schema = super()._contract_option_schema(minimum=minimum)
        schema['properties']['coverage_amount'] = POSITIVE_AMOUNT_SCHEMA
        return schema

    @classmethod
    def _contract_option_convert(cls, data, options, parameters, package=None,
            minimum=False):
        super()._contract_option_convert(data, options, parameters, package,
            minimum=minimum)

        if 'coverage_amount' in data:
            data['coverage_amount'] = amount_from_api(data['coverage_amount'])

    @classmethod
    def _validate_contract_option_input(cls, data):
        super()._validate_contract_option_input(data)

        API = Pool().get('api')
        if data['coverage'].coverage_amount_rules:
            rule = data['coverage'].coverage_amount_rules[0]
            if (rule.amount_mode != 'calculated_amount'
                    and 'coverage_amount' not in data):
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

    @classmethod
    def _simulate_contract_extract_option(cls, option):
        result = super(APIContract, cls)._simulate_contract_extract_option(
            option)
        if not option.coverage_amount_mode:
            return result
        result['coverage_amount'] = {
            'amount': amount_for_api(option.current_coverage_amount),
            'label': option.coverage.coverage_amount_rules[0].label or '',
            }
        return result

    @classmethod
    def _simulate_coverages_output_schema(cls):
        schema = super(APIContract, cls)._simulate_coverages_output_schema()
        schema['items']['properties'].update({
                'coverage_amount': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'amount': POSITIVE_AMOUNT_SCHEMA,
                        'label': {'type': 'string'},
                        },
                    'required': ['amount'],
                    }
                })
        return schema


class APIRuleRuntime(metaclass=PoolMeta):
    __name__ = 'api.rule_runtime'

    @classmethod
    @check_args('api.option')
    def _re_api_get_coverage_amount(cls, args):
        result = args['api.option'].get('coverage_amount', None)
        if result is None:
            Pool().get('api').add_input_error({
                    'type': 'missing_rule_engine_argument',
                    'data': {
                        'field': 'option.coverage_amount',
                        },
                    })
        return result
