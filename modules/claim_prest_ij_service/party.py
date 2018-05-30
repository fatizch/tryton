# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields


__all__ = [
    'Party',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    prest_ij_subscription = fields.One2Many('claim.ij.subscription', 'party',
        'Prest IJ Subscription', readonly=True, delete_missing=True, size=1)
