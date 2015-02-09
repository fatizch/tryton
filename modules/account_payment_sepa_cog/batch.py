from trytond.pool import PoolMeta

from trytond.modules.cog_utils import coop_string

__metaclass__ = PoolMeta
__all__ = [
    'PaymentTreatmentBatch',
    ]


class MultipleWaitingSepaError(Exception):
    """Raised when processing a payment group having multiple sepa messages
    with 'waiting' status.
    """


class PaymentTreatmentBatch:
    __name__ = 'account.payment.process'

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        groups = super(PaymentTreatmentBatch, cls).execute(
            objects, ids, treatment_date)
        dirpath = cls.generate_filepath()
        dump_sepa_errors = []
        for payments_group in groups:
            out_filepaths = payments_group.dump_sepa_messages(dirpath)
            log_msg = "SEPA message of %s written to '%s'" % (
                    payments_group, out_filepaths[0])
            if len(out_filepaths) == 1:
                cls.logger.info(log_msg)
            if len(out_filepaths) > 1:
                cls.logger.warning('Only last ' + log_msg)
                dump_sepa_errors.append(payments_group)
        if dump_sepa_errors:
            raise MultipleWaitingSepaError("Multiple sepa messages with "
                "'waiting' status for  %s" %
                coop_string.get_print_infos(dump_sepa_errors))
        return groups
