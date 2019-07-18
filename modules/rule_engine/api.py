# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.server_context import ServerContext

__all__ = [
    'RuleEngine',
    ]


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    def execute(self, arguments, parameters=None, overrides=None):
        if overrides is None:
            overrides = ServerContext().get('api_rule_context', None)
        return super().execute(arguments, parameters, overrides)
