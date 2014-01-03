from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_health_regime(cls, args):
        person = cls.get_person(args)
        if person.health_complement:
            regime = person.health_complement[0].regime
            return regime.code if regime else ''
        cls.append_error(args, 'Cannot find the regime')
