from trytond.pool import PoolMeta


__metaclass__ = PoolMeta
__all__ = [
    'PaymentTreatmentBatch',
    ]


class PaymentTreatmentBatch:
    __name__ = 'account.payment.process'

    @classmethod
    def __setup__(cls):
        super(PaymentTreatmentBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': '0',
                })

    @classmethod
    def _group_payment_key(cls, payment):
        res = super(PaymentTreatmentBatch, cls)._group_payment_key(payment)
        journal = payment.journal
        if journal.process_method == 'sepa' and \
                journal.split_sepa_messages_by_sequence_type:
            res = res + (('sequence_type', payment.sepa_mandate_sequence_type
                    or payment.sepa_mandate.sequence_type),)
        return res

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        groups = super(PaymentTreatmentBatch, cls).execute(
            objects, ids, treatment_date, extra_args)
        dirpath = cls.generate_filepath()
        for payments_group in groups:
            out_filepaths = payments_group.dump_sepa_messages(dirpath)
            log_msg = "SEPA message of %s written to '%s'" % (
                    payments_group, out_filepaths[0])
            if len(out_filepaths) == 1:
                cls.logger.info(log_msg)
            if len(out_filepaths) > 1:
                cls.logger.warning('Only last ' + log_msg)
                raise Exception("Multiple sepa messages with "
                    "'waiting' status for  %s" % payments_group)
        return groups
