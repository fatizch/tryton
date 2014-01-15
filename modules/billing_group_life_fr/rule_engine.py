from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_fare_class(cls, args):
        return args['fare_class'].code if 'fare_class' in args else None

    @classmethod
    def _re_fare_class_group(cls, args):
        return (args['fare_class_group'].code
            if 'fare_class_group' in args else None)
