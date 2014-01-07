from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def get_lowest_level_object(cls, args):
        if 'comp_option' in args:
            return args['comp_option']
        return super(RuleEngineRuntime, cls).get_lowest_level_object(args)
