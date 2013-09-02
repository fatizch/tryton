from trytond.modules.rule_engine import RuleEngineContext

__all__ = [
    'OfferedContext',
    ]


class OfferedContext(RuleEngineContext):
    'Offered Context'

    __name__ = 'offered.rule_sets'

    @classmethod
    def _re_fare_class(cls, args):
        return args['fare_class'].code if 'fare_class' in args else None

    @classmethod
    def _re_fare_class_group(cls, args):
        return args['fare_class_group'].code if 'fare_class_group' in args else None
