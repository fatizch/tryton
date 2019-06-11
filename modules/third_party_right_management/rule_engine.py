# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


class RuleTools(metaclass=PoolMeta):
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_event_code(cls, args):
        return args.get('event_code')
