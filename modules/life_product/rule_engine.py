from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:

    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_get_coverage_amount(cls, args):
        data = cls.get_covered_data(args)
        if data.coverage_amount:
            return data.coverage_amount
        cls.append_error(args, 'Coverage amount undefined')
