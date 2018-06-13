# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta
from trytond.modules.coog_core import fields


__all__ = [
    'Party',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    ij_subscriptions = fields.Function(fields.Many2One('claim.ij.subscription',
            'Ij Subscription'), 'getter_claim_ij_subscription')

    def getter_claim_ij_subscription(self, name=None):
        if not self.ssn and not self.ssn:
            return None
        return [x.id for x in Pool().get('claim.ij.subscription').search(
                [
                    ['OR',
                        [('ssn', '=', self.ssn)],
                        [('siren', '=', self.siren)],
                        ]
                    ]
                )]
