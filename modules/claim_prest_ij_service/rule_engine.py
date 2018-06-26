# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.rule_engine import check_args


__all__ = [
    'RuleRuntime',
    ]


class RuleRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('indemnification')
    def _re_has_prest_ij_period(cls, args):
        return bool(getattr(args['indemnification'], 'prestij_periods', None))
