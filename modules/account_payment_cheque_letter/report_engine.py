# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model.exceptions import AccessError, ValidationError
from trytond.pool import Pool, PoolMeta


__all__ = [
    'ReportGenerate',
    ]


class ReportGenerate(metaclass=PoolMeta):
    __name__ = 'report.generate'

    @classmethod
    def execute(cls, ids, data):
        if data['model'] != 'account.payment.merged':
            return super(ReportGenerate, cls).execute(ids, data)
        Payment = Pool().get('account.payment')
        active_ids = data['ids']
        other = False
        cheque_letter = False
        prev_number = None
        merged_payments = Payment.browse(active_ids)

        # First check: do not print cheque_letter with another journal payment
        # at the same time
        for payment in merged_payments:
            if payment.journal.process_method == 'cheque_letter':
                cheque_letter = True
            else:
                other = True
        if cheque_letter and other:
            raise AccessError(gettext(
                    'account_payment_cheque_letter'
                    '.msg_journal_mixin_not_allowed'))

        if cheque_letter:
            # Sorting by cheque_number
            sorted_payments = sorted(merged_payments,
            key=lambda payment: int(payment.merged_id))
            # Second & contiguous check (for cheque number only)
            for payment in sorted_payments:
                if prev_number and (prev_number + 1 != int(payment.merged_id)):
                    raise ValidationError(gettext(
                            'account_payment_cheque_letter'
                            '.msg_cheque_number_sequence_broken',
                            from_=prev_number, to=int(payment.merged_id)))
                prev_number = int(payment.merged_id)
                data['ids'] = [x.id for x in sorted_payments]
        else:
            data['ids'] = [x.id for x in merged_payments]
        return super(ReportGenerate, cls).execute(ids, data)
