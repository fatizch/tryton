# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool

__all__ = [
        'MoveLine',
    ]


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    def get_payment_journal(self):
        if (self.move.origin and self.move.origin.__name__ == 'account.invoice'
                and self.move.origin.business_kind == 'claim_invoice'):
            claim_details = self.origin.lines[0].claim_details
            default_journal = Pool().get('claim.configuration'
                ).get_singleton().payment_journal
            if claim_details and claim_details[0].indemnification:
                indemnification = claim_details[0].indemnification
                if indemnification and indemnification.journal:
                    return indemnification.journal
                else:
                    return default_journal
            else:
                return default_journal

        return super(MoveLine, self).get_payment_journal()
