from trytond.pool import Pool, PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'ReportGenerate',
    ]


class ReportGenerate:
    __name__ = 'report.generate'

    @classmethod
    def execute(cls, ids, data, immediate_conversion=False):
        if data['model'] != 'account.payment.merged':
            return super(ReportGenerate, cls).execute(ids, data,
                immediate_conversion)
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
            Payment.raise_user_error('journal_mixin_not_allowed')

        if cheque_letter:
            # Sorting by cheque_number
            sorted_payments = sorted(merged_payments,
            key=lambda payment: int(payment.merged_id))
            # Second & contiguous check (for cheque number only)
            for payment in sorted_payments:
                if prev_number and (prev_number + 1 != int(payment.merged_id)):
                    Payment.raise_user_error('cheque_number_sequence_broken',
                        (prev_number, int(payment.merged_id)))
                prev_number = int(payment.merged_id)
                data['ids'] = [x.id for x in sorted_payments]
        else:
            data['ids'] = [x.id for x in merged_payments]
        return super(ReportGenerate, cls).execute(ids, data,
            immediate_conversion)
