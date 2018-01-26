# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Move',
    'MoveLine',
    ]


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls.kind.selection.append(('manual_payment', 'Manual Payment'))
        cls.kind.selection.append(
            ('rejected_manual_payment', 'Rejected Manual Payment'))
        cls._error_messages.update({
                'already_cancelled': 'The statement is already cancelled'
                })

    def get_kind(self, name):
        if self.origin:
            if self.origin.__name__ == 'account.statement':
                return 'manual_payment'
            elif self.origin_item.__name__ == 'account.statement':
                return 'rejected_manual_payment'
        return super(Move, self).get_kind(name)


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    def get_synthesis_rec_name(self, name):
        if (not self.origin_item
                or self.origin_item.__name__ != 'account.statement'):
            return super(MoveLine, self).get_synthesis_rec_name(name)
        name = '%s - %s' % (self.origin_item.journal.rec_name,
            self.description)
        if self.move.description:
            name += ' [%s]' % self.move.description
        return name
