from trytond.pool import PoolMeta


class HealthContext():
    '''
        Context functions for Health.
    '''
    __name__ = 'ins_product.rule_sets.person'
    __metaclass__ = PoolMeta

    @classmethod
    def _re_health_regime(cls, args):
        person = cls.get_person(args)
        if person.health_complement:
            regime = person.health_complement[0].regime
            return regime.code if regime else ''
        cls.append_error(args, 'Cannot find the regime')
