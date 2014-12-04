from itertools import groupby
from celery.utils.log import get_task_logger
from sql.operators import Equal
from sql.aggregate import Count

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import batch, coop_string


_all__ = [
    'PaymentTreatmentBatch',
    'PaymentCreationBatch'
    ]

logger = get_task_logger(__name__)


class PaymentTreatmentBatch(batch.BatchRoot):
    "Payment Treatment Batch"
    __name__ = 'account.payment.treatment'

    @classmethod
    def __setup__(cls):
        super(PaymentTreatmentBatch, cls).__setup__()
        cls._default_config_items.update({'dump_sepa_xml': u'no'})

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.payment'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.payment'

    @classmethod
    def get_batch_domain(cls, treatment_date):
        return [
            ('state', '=', 'approved'),
            ('date', '<=', treatment_date)]

    @classmethod
    def _group_payment_key(cls, payment):
        return (('journal', payment.journal.id), ('kind', payment.kind))

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        groups = []
        Payment = Pool().get('account.payment')
        payments = sorted(objects, key=cls._group_payment_key)
        for key, grouped_payments in groupby(payments,
                key=cls._group_payment_key):
            def group():
                pool = Pool()
                Group = pool.get('account.payment.group')
                group = Group(**dict(key))
                group.save()
                groups.append(group)
                return group
            grouped_payments = list(grouped_payments)
            payments_group = Payment.process(list(grouped_payments), group)
            if coop_string.coerce_to_bool(cls.get_conf_item('dump_sepa_xml')):
                for sepa_msg in payments_group.sepa_messages:
                    cls.write_batch_output(sepa_msg.message.encode('utf-8'),
                        sepa_msg.filename)


class PaymentCreationBatch(batch.BatchRoot):
    "Payment Creation Batch"
    __name__ = 'account.payment.creation'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.move.line'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.move.line'

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().cursor
        pool = Pool()
        payment = pool.get('account.payment').__table__()
        move_line = pool.get('account.move.line').__table__()
        account = pool.get('account.account').__table__()

        query_table = move_line.join(account, condition=(
                (move_line.account == account.id)
                & (account.kind == 'receivable'))
                & (move_line.reconciliation == None)
                & (move_line.payment_date <= treatment_date))

        cursor.execute(*query_table.select(move_line.id,
            where=Equal(
                payment.select(Count(payment.id), where=(
                        (payment.state != 'failed')
                        & (payment.line == move_line.id))), 0),
            group_by=move_line.id))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        MoveLine.create_payments(objects)
