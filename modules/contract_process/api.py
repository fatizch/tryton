# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'APIContract',
    ]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _subscribe_contracts_execute_methods(cls, options):
        methods = super()._subscribe_contracts_execute_methods(options)

        if options.get('start_process', False):
            methods += [
                {
                    'priority': 0,
                    'name': 'attach_to_process',
                    'params': ['subscription'],
                    'error_type': 'failed_to_attach_to_process',
                    },
                ]

        if options.get('fast_forward', False):
            methods += [
                {
                    'priority': 1000,
                    'name': 'fast_forward_process',
                    'params': [False],
                    'error_type': 'failed_to_fast_forward_process',
                    },
                ]

        return methods

    @classmethod
    def _subscribe_contracts_options_schema(cls):
        schema = super()._subscribe_contracts_options_schema()
        schema['fast_forward'] = {'type': 'boolean'}
        schema['start_process'] = {'type': 'boolean'}
        return schema
