from trytond.pool import PoolMeta

__all__ = [
    'OfferedContext',
    ]


class OfferedContext():
    'Offered Context'

    __name__ = 'commission.rule_sets.commission'
    __metaclass__ = PoolMeta

    @classmethod
    def get_lowest_level_object(cls, args):
        if 'comp_option' in args:
            return args['comp_option']
        return super(OfferedContext, cls).get_lowest_level_object(args)
