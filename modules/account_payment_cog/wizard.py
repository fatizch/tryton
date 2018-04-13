# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

__all__ = [
    'PartyErase',
    ]


class PartyErase:
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    def to_erase(self, party_id):
        to_erase = super(PartyErase, self).to_erase(party_id)
        Payment = Pool().get('account.payment')
        to_erase.append(
            (Payment, [('party', '=', party_id)], True,
                ['description'],
                [None]))
        return to_erase
