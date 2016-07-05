# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Benefit',
    'LossDescription',
    ]


class Benefit:
    __name__ = 'benefit'

    @classmethod
    def get_beneficiary_kind(cls):
        res = super(Benefit, cls).get_beneficiary_kind()
        res.append(['covered_person', 'Covered Person'])
        return res


class LossDescription:

    __name__ = 'benefit.loss.description'

    @classmethod
    def __setup__(cls):
        super(LossDescription, cls).__setup__()
        cls.item_kind.selection.append(('person', 'Person'))
        cls.loss_kind.selection.append(('life', 'Life'))
