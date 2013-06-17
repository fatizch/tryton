from trytond.pool import PoolMeta

__all__ = [
    'OfferedContext',
    ]


class OfferedContext():
    'Offered Context'

    __name__ = 'offered.rule_sets'
    __metaclass__ = PoolMeta

    @classmethod
    def get_lowest_level_object(cls, args):
        if 'data' in args:
            return args['data']
        return super(OfferedContext, cls).get_lowest_level_object(args)
