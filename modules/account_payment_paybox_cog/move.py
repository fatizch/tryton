# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    @classmethod
    def get_configuration_journals_from_lines(cls, lines):
        '''
        Paybox is systematically added in possible journals,
        so we remove it from product_journals
        '''
        return [x for x in
            super(MoveLine, cls).get_configuration_journals_from_lines(
                lines)
            if x.process_method != 'paybox']
