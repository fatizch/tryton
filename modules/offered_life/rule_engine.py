from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:

    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_get_coverage_amount(cls, args):
        option = cls.get_option(args)
        if option.coverage_amount:
            return option.coverage_amount
        cls.append_error(args, 'Coverage amount undefined')
