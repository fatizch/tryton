# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _subscribe_contracts_options_schema(cls):
        schema = super()._subscribe_contracts_options_schema()
        schema.update({
            'decline_non_eligible': {'type': 'boolean'},
            })
        return schema

    @classmethod
    def _simulate_default_options(cls):
        options = super()._simulate_default_options()
        options.update({
            'decline_non_eligible': True,
                })
        return options

    @classmethod
    def _contract_option_schema(cls, minimum=False):
        schema = super()._contract_option_schema(minimum=minimum)
        schema['properties']['eligibility'] = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'eligible': {'type': 'boolean'},
                'message': {'type': 'string'},
                }
            }
        return schema

    @classmethod
    def _subscribe_contracts_execute_methods(cls, options):
        methods = super()._subscribe_contracts_execute_methods(options)
        if options.get('decline_non_eligible', False):
            methods.extend([
                {
                        'priority': 16,
                        'name': 'calculate_activation_dates',
                        'params': [],
                        'error_type': 'failed_to_calculate_activation_dates',
                }, {
                        'priority': 18,
                        'name': 'update_options_automatic_end_date',
                        'params': [],
                        'error_type': 'failed_to_calculate_options_end_date',
                }, {
                        'priority': 20,
                        'name': 'decline_non_eligible_options',
                        'params': [],
                        'error_type': 'failed_to_decline_non_eligible_options',
                }])
        return methods

    @classmethod
    def _simulate_contract_extract_covered_option(cls, option):
        extraction = super()._simulate_contract_extract_covered_option(option)
        if option.status == 'active':
            extraction.update({'eligibility': {'eligible': True}})
        elif option.status == 'declined' and option.sub_status and \
                option.sub_status.code == 'automatically_declined':
            extraction.update({'eligibility': {'eligible': False,
                        'message': option.eligibility_message}})
        return extraction

    @classmethod
    def _simulate_option_schema(cls):
        schema = super(APIContract, cls)._simulate_option_schema()
        schema['properties']['eligibility'] = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'eligible': {'type': 'boolean'},
                'message': {'type': 'string'},
                }
            }
        return schema
