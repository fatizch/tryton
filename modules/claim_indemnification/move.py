# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._error_messages.update({
                'indemnification_lines_only': 'Please check whether the lines '
                'to pay are all related to a claim invoice.'
                })

    def get_payment_journal(self):
        # checking hasattr() to skip this code when using a fake Line object
        if (hasattr(self, 'move') and self.move and self.move.origin
                and self.move.origin.__name__ == 'account.invoice'
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

    def _line_from_claim_invoices(self):
        return self.move.origin \
            and self.move.origin.__name__ == 'account.invoice' \
            and self.move.origin.business_kind == 'claim_invoice'

    @classmethod
    def get_configuration_journals_from_lines(cls, lines):
        if any(x._line_from_claim_invoices() for x in lines):
            if not all(x._line_from_claim_invoices() for x in lines):
                cls.raise_user_error('indemnification_lines_only')
            journals = []
            for invoice in [x.move.origin for x in lines]:
                if not invoice.lines or not invoice.lines[0].claim_details:
                    continue
                if not invoice.lines[0].claim_details[0].indemnification:
                    continue
                journal = \
                    invoice.lines[0].claim_details[0].indemnification.journal
                if journal:
                    journals.append(journal)
            return journals
        return super(MoveLine, cls).get_configuration_journals_from_lines(
            lines)
