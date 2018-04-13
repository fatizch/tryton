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
        pool = Pool()
        OptionBeneficiary = pool.get('contract.option.beneficiary')
        Option = pool.get('contract.option')
        benefitted_options_to_erase = OptionBeneficiary.search([
                ('party', '=', party_id)
                ])
        subscribed_options_to_erase = Option.search([
                ('contract.subscriber', '=', party_id)
                ])
        options_to_erase = [bo.id for bo in benefitted_options_to_erase] + \
            [so.id for so in subscribed_options_to_erase]
        to_erase.extend([
                (Option, [('id', 'in', options_to_erase)], True,
                    ['customized_beneficiary_clause'],
                    [None]),
                (OptionBeneficiary, [('party', '=', party_id)], True,
                    ['reference'],
                    [None])
                ])
        return to_erase
