from itertools import groupby
from sql.operators import Equal
from sql.aggregate import Count
from sql import Null

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import batch, coop_string


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
            def group_func():
                pool = Pool()
                Group = pool.get('account.payment.group')
                group = Group(**dict(key))
                group.save()
                groups.append(group)
                return group
            keys.append(key)
            grouped_payments = list(_grouped_payments)
            cls.logger.info('processing group %s of %s' % (key,
                coop_string.get_print_infos(grouped_payments, 'payment')))
            Payment.process(grouped_payments, group_func)
        cls.logger.info('%s processed' %
            coop_string.get_print_infos(groups, 'payments group'))
        return groups


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
        party = pool.get('party.party').__table__()

        query_table = move_line.join(party,
            condition=(move_line.party == party.id)
            ).join(account, condition=(
                (move_line.account == account.id)
                & ((account.kind == 'receivable') |
                    ((account.kind == 'payable') &
                        (party.block_payable_payments == False)))
                & (move_line.reconciliation == Null)
                & (move_line.payment_date <= treatment_date)))

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
        cls.logger.info('%s created' %
            coop_string.get_print_infos([x.id for x in objects], 'payment'))
