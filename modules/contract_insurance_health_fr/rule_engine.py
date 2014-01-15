from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_health_hc_system(cls, args):
        person = cls.get_person(args)
        if person.health_complement:
            hc_system = person.health_complement[0].hc_system
            return hc_system.code if hc_system else ''
        cls.append_error(args, 'Cannot find the hc_system')
