from itertools import groupby
from sql.operators import Equal
from sql.aggregate import Count

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import batch


__all__ = [
    'PaymentTreatmentBatch',
    'PaymentCreationBatch'
    ]


class PaymentTreatmentBatch(batch.BatchRoot):
    "Payment Treatment Batch"

    __name__ = 'account.payment.process'

    logger = batch.get_logger(__name__)

    @classmethod
    def __setup__(cls):
        super(PaymentTreatmentBatch, cls).__setup__()
        cls._default_config_items.update({'split_size': 1})

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
        grouped_payments_list = groupby(payments, key=cls._group_payment_key)
        keys = []
        for key, _grouped_payments in grouped_payments_list:
            def group():
                pool = Pool()
                Group = pool.get('account.payment.group')
                group = Group(**dict(key))
                group.save()
                groups.append(group)
                return group
            keys.append(key)
            grouped_payments = list(_grouped_payments)
            cls.logger.info('processing group %s of %s' % (key,
                batch.get_print_infos(grouped_payments, 'payment')))
            payments_group = Payment.process(list(grouped_payments), group)
            for sepa_msg in payments_group.sepa_messages:
                filename = cls.generate_filepath(sepa_msg.filename)
                with open(filename, 'w') as _file:
                    _file.write(sepa_msg.message.encode('utf-8'))
                    cls.logger.info('SEPA message written to %s' %
                        filename)
            Message = Pool().get('account.payment.sepa.message')
            Message.do(payments_group.sepa_messages)
            cls.logger.info("apply transition 'done' to %s" %
                payments_group.sepa_messages)
        cls.logger.success('%s processed' %
            batch.get_print_infos(keys, 'payments group'))


class PaymentCreationBatch(batch.BatchRoot):
    "Payment Creation Batch"
    __name__ = 'account.payment.create'

    logger = batch.get_logger(__name__)

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
        cls.logger.success('%s created' %
            batch.get_print_infos([x.id for x in objects], 'payment'))
