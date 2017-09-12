# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from itertools import groupby
from collections import defaultdict

from sql import Null, Literal
from sql.operators import Equal
from sql.aggregate import Count

from trytond.pool import Pool
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from trytond.config import config

from trytond.modules.coog_core import batch, coog_string


__all__ = [
    'PaymentTreatmentBatch',
    'PaymentGroupCreationBatch',
    'PaymentUpdateBatch',
    'PaymentGroupProcessBatch',
    'PaymentCreationBatch',
    'PaymentSucceedBatch',
    'PaymentAcknowledgeBatch',
    ]

PAYMENT_KINDS = ['receivable', 'payable']


class PaymentTreatmentBatch(batch.BatchRoot):
    "Payment Treatment Batch"

    __name__ = 'account.payment.process'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(PaymentTreatmentBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                'split': False,
                'payment_kind': '',
                'cache_size': config.getint('cache', 'record'),
                })

    @classmethod
    def parse_params(cls, params):
        params = super(PaymentTreatmentBatch, cls).parse_params(params)
        assert params.get('job_size') == 0
        return params

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.payment'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.payment'

    @classmethod
    def get_batch_domain(cls, treatment_date, payment_kind=None,
            journal_methods=None, **kwargs):
        res = [
            ('state', '=', 'approved'),
            ('date', '<=', treatment_date)]
        if journal_methods:
            journal_methods = [x.strip() for x in journal_methods.split(',')]
            res.append(('journal.process_method', 'in', journal_methods))
        if payment_kind:
            if payment_kind in PAYMENT_KINDS:
                res.append(('kind', '=', payment_kind))
            else:
                msg = "ignore payment_kind: '%s' not in %s" % (payment_kind,
                    PAYMENT_KINDS)
                cls.logger.error('%s. Aborting' % msg)
                raise Exception(msg)
        return res

    @classmethod
    def select_ids_regroup_key(cls, payment, payment_kind, **kwargs):
        return payment.party

    @classmethod
    def select_ids(cls, treatment_date, payment_kind=None,
            journal_methods=None, **kwargs):
        Payment = Pool().get('account.payment')
        res = super(PaymentTreatmentBatch, cls).select_ids(treatment_date,
            payment_kind, journal_methods)
        groups = defaultdict(list)
        for sub_res in grouped_slice(res):
            payments = Payment.browse([x[0] for x in sub_res])
            for payment in payments:
                key = cls.select_ids_regroup_key(payment, payment_kind)
                groups[key].append((payment.id,))
        res = []
        for k, v in groups.iteritems():
            if not k:
                res.extend(v)
            else:
                res.append(v)
        return res

    @classmethod
    def _group_payment_key(cls, payment):
        return (('journal', payment.journal.id), ('kind', payment.kind))

    @classmethod
    def execute(cls, objects, ids, treatment_date, payment_kind=None,
            journal_methods=None, **kwargs):
        with Transaction().set_context(
                _record_cache_size=int(kwargs.get('cache_size'))):
            groups = []
            Payment = Pool().get('account.payment')
            payments = sorted(objects, key=cls._group_payment_key)
            grouped_payments_list = groupby(payments,
                key=cls._group_payment_key)
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
                    coog_string.get_print_infos(grouped_payments, 'payment')))
                Payment.process(grouped_payments, group_func)
            cls.logger.info('%s processed' %
                coog_string.get_print_infos(groups, 'payments group'))
            return [group.id for group in groups]


class PaymentGroupCreationBatch(batch.BatchRoot):
    'Payment Group Creation Batch'

    __name__ = 'account.payment.group.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(PaymentGroupCreationBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                'split': False,
                'payment_kind': '',
                })

    @classmethod
    def parse_params(cls, params):
        params = super(PaymentGroupCreationBatch, cls).parse_params(params)
        assert params.get('job_size') == 0
        return params

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.payment'

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return []

    @classmethod
    def _group_payment_key(cls, payment):
        return (payment.journal, payment.kind, payment.party)

    @classmethod
    def get_payment_where_clause(cls, payment, payment_kind, treatment_date,
            journal_methods):
        pool = Pool()
        journal = pool.get('account.payment.journal').__table__()
        clause = (payment.group == Null) & \
            (payment.kind == payment_kind) & \
            (payment.date <= treatment_date) & \
            (payment.state == 'approved')
        if journal_methods:
            journal_methods = [x.strip() for x in journal_methods.split(',')]
            journal_ids = journal.select(journal.id,
                where=(journal.process_method.in_(journal_methods)))
            clause &= (payment.journal.in_(journal_ids))
        return clause

    @classmethod
    def select_ids(cls, treatment_date, payment_kind=None,
            journal_methods=None):
        pool = Pool()
        payment = pool.get('account.payment').__table__()
        cursor = Transaction().connection.cursor()
        assert payment_kind in PAYMENT_KINDS
        query = payment.select(payment.id, *cls._group_payment_key(payment),
            where=(cls.get_payment_where_clause(payment, payment_kind,
                    treatment_date, journal_methods)),
                order_by=cls._group_payment_key(payment))
        cursor.execute(*query)
        results = cursor.fetchall()
        payment_ids = []
        for group_key, grouped_results in groupby(
                results, lambda x: x[1:]):
            payment_ids.append([(x[0],) for x in grouped_results])
        return payment_ids

    @classmethod
    def execute(cls, objects, ids, treatment_date, payment_kind=None,
            journal_methods=None):
        pool = Pool()
        Group = pool.get('account.payment.group')
        Payment = pool.get('account.payment')
        Event = pool.get('event')
        payment = Payment.__table__()
        cursor = Transaction().connection.cursor()
        query = payment.select(payment.id, *cls._group_payment_key(payment),
            where=(payment.id.in_(ids)),
            order_by=cls._group_payment_key(payment))
        cursor.execute(*query)
        results = cursor.fetchall()
        all_groups = []
        for group_key, grouped_results in groupby(
                results, key=cls.group_by_key_func):
            group = Group(journal=group_key[0], kind=group_key[1])
            group.save()
            all_groups.append(group)
            for payment_ids in grouped_slice([x[0] for x in grouped_results]):
                Payment._set_group(payment_ids, group)
        if all_groups:
            Event.notify_events(all_groups, 'payment_group_created')
        return [x.id for x in all_groups]

    @classmethod
    def group_by_key_func(cls, payment_row):
        # one group per journal and kind
        return payment_row[1:3]


class PaymentUpdateBatch(batch.BatchRoot):
    'Payment Updating Batch'
    __name__ = 'account.payment.update'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(PaymentUpdateBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 1000,
                'split': False,
                })

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return []

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.payment'

    @classmethod
    def select_ids(cls, treatment_date, update_method, payment_kind=None):
        if not update_method:
            return []
        assert payment_kind in PAYMENT_KINDS
        Group = Pool().get('account.payment.group')
        name = 'payments_update_select_ids_' + update_method
        select_ids = getattr(Group, name, None)
        if not select_ids:
            cls.logger.warning('There is no method %s. Nothing to do.' % name)
            return []
        return select_ids(treatment_date, payment_kind)

    @classmethod
    def execute(cls, objects, ids, treatment_date, update_method,
            payment_kind=None):
        pool = Pool()
        Payment = pool.get('account.payment')
        Group = pool.get('account.payment.group')
        update_method = getattr(Group, 'payments_update_' + update_method,
            None)
        if not update_method:
            return []
        for _ids in grouped_slice(ids):
            update_method(Payment.browse(_ids), payment_kind)


class PaymentGroupProcessBatch(batch.BatchRoot):
    'Payment Group Processing Batch'
    __name__ = 'account.payment.group.process'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(PaymentGroupProcessBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 1,
                'split': False,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.payment.group'

    @classmethod
    def select_ids(cls, treatment_date, payment_kind=None,
            journal_methods=None):
        pool = Pool()
        payment = pool.get('account.payment').__table__()
        journal = pool.get('account.payment.journal').__table__()
        group = pool.get('account.payment.group').__table__()
        cursor = Transaction().connection.cursor()
        assert payment_kind in PAYMENT_KINDS
        where_clause = (payment.kind == payment_kind) & \
            (payment.group != Null) & \
            (payment.date <= treatment_date) & \
            (payment.state == 'approved')
        if journal_methods:
            journal_methods = [x.strip() for x in journal_methods.split(',')]
            by_journal = group.join(journal, condition=(
                    (group.journal == journal.id) &
                    (journal.process_method.in_(journal_methods)))
                ).select(group.id)
            where_clause &= (payment.group.in_(by_journal))

        query = payment.select(payment.group, where=where_clause,
            group_by=payment.group)
        cursor.execute(*query)
        return cursor.fetchall()

    @classmethod
    def _process_group(cls, group):
        Group = Pool().get('account.payment.group')
        process_method = getattr(Group,
            'process_%s' % group.journal.process_method, None)
        if process_method:
            process_method(group)
            group.save()

    @classmethod
    def execute(cls, objects, ids, treatment_date, payment_kind=None,
            journal_methods=None, **kwargs):
        pool = Pool()
        Payment = pool.get('account.payment')
        Event = pool.get('event')
        if not ids:
            return
        groups = []
        with Transaction().set_context(_record_cache_size=int(
                    kwargs.get('cache_size'))):
            for group in objects:
                for payments_slice in grouped_slice(group.payments):
                    Payment.write(list(payments_slice), {'state': 'processing'})
                cls._process_group(group)
                Payment.set_description(group.payments)
                Event.notify_events(group.payments, 'process_payment')
        return [group.id for group in groups]


class PaymentCreationBatch(batch.BatchRoot):
    "Payment Creation Batch"
    __name__ = 'account.payment.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(PaymentCreationBatch, cls).__setup__()
        cls._default_config_items.update({
                'payment_kind': '',
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'party.party'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.move.line'

    @classmethod
    def select_ids(cls, treatment_date, payment_kind):
        cursor = Transaction().connection.cursor()
        tables, query_table, where_clause = cls.get_query(treatment_date,
            payment_kind)
        move_line = tables['move_line']
        cursor.execute(*query_table.select(move_line.party,
            where=where_clause, group_by=move_line.party))
        return cursor.fetchall()

    @classmethod
    def get_query(cls, treatment_date, payment_kind=None):
        pool = Pool()
        payment = pool.get('account.payment').__table__()
        move_line = pool.get('account.move.line').__table__()
        account = pool.get('account.account').__table__()
        party = pool.get('party.party').__table__()
        if payment_kind and payment_kind not in PAYMENT_KINDS:
            msg = "ignore payment_kind: '%s' not in %s" % (payment_kind,
                PAYMENT_KINDS)
            cls.logger.error('%s. Aborting' % msg)
            raise Exception(msg)
        tables = {
            'move_line': move_line,
            'party': party,
            'account': account,
            }
        join_acc_cond = (
            (move_line.account == account.id)
            & ((account.kind == 'receivable') |
                ((account.kind == 'payable') &
                    (party.block_payable_payments == Literal(False))))
            & (move_line.reconciliation == Null)
            & (move_line.payment_date <= treatment_date))
        if payment_kind == 'receivable':
            join_acc_cond &= (move_line.debit > 0) | (move_line.credit < 0)
        elif payment_kind == 'payable':
            join_acc_cond &= (move_line.debit < 0) | (move_line.credit > 0)
        query_table = move_line.join(party,
            condition=(move_line.party == party.id)
        ).join(account, condition=join_acc_cond)

        where_clause = Equal(payment.select(Count(payment.id),
                where=((payment.state != 'failed')
                    & (payment.line == move_line.id))), 0)
        return tables, query_table, where_clause

    @classmethod
    def execute(cls, objects, ids, treatment_date, payment_kind):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        # TODO : handle generically
        # If no ids: log that there is nothing to do
        # and manage the "no select" batch case
        if not ids:
            return

        cursor = Transaction().connection.cursor()
        tables, query_table, where_clause = cls.get_query(treatment_date,
            payment_kind)
        move_line = tables['move_line']
        cursor.execute(*query_table.select(move_line.id,
                where=where_clause & move_line.party.in_(ids),
                group_by=move_line.id))

        move_lines = MoveLine.browse([x[0] for x in cursor.fetchall()])
        MoveLine.create_payments(move_lines)
        cls.logger.info('%s created' %
            coog_string.get_print_infos([x.id for x in move_lines], 'payment'))


class PaymentValidationBatchBase(batch.BatchRoot):
    'Payment Validation Batch Base'

    @classmethod
    def base_domain_select_ids(cls, payment_kind, **kwargs):
        domain = [
            ('payment_date_min', '<=', kwargs.get('treatment_date')),
            ]
        if kwargs.get('auto_acknowledge', None):
            domain.append(('state', 'in',
                    ['to_acknowledge', 'processing']))
        else:
            domain.append(('state', '=', 'to_acknowledge'))
        if payment_kind:
            domain.append(('payments.kind', '=', payment_kind))
        return domain

    @classmethod
    def select_ids(cls, treatment_date, group_reference=None,
            payment_kind=None, journal_methods=None, auto_acknowledge=None):
        pool = Pool()
        Group = pool.get('account.payment.group')
        domain = []
        if group_reference:
            groups = Group.search([
                    ('number', '=', group_reference)])
            if len(groups) != 1:
                msg = "Payment Group Reference %s invalid" % group_reference
                cls.logger.error('%s. Aborting' % msg)
                raise Exception(msg)
            return [(groups[0].id,)]
        if payment_kind and payment_kind not in PAYMENT_KINDS:
            msg = "ignoring payment_kind: '%s' not in %s" % (payment_kind,
                PAYMENT_KINDS)
            cls.logger.error('%s. Aborting' % msg)
            raise Exception(msg)
        domain = cls.base_domain_select_ids(payment_kind,
            treatment_date=treatment_date, auto_acknowledge=auto_acknowledge)
        if journal_methods:
            journal_methods = [x.strip() for x in journal_methods.split(',')]
            domain.append(
                ('journal.process_method', 'in', journal_methods))
        return [(group.id,) for group in Group.search(domain)]


class PaymentSucceedBatch(PaymentValidationBatchBase):
    'Payment Succeed Batch'
    __name__ = 'account.payment.succeed'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(PaymentSucceedBatch, cls).__setup__()
        cls._default_config_items.update({
                'payment_kind': '',
                })

    @classmethod
    def enqueue_filter_objects(cls, records):
        filtered_records = super(
            PaymentSucceedBatch, cls).enqueue_filter_objects(records)
        for record in records:
            if record.__name__ == 'account.payment.group':
                filtered_records.extend(record.processing_payments)
        return filtered_records

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.payment'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.payment'

    @classmethod
    def select_ids(cls, **kwargs):
        pool = Pool()
        Payment = pool.get('account.payment')
        cursor = Transaction().connection.cursor()
        payment = Payment.__table__()
        payments_per_group = defaultdict(list)

        group_ids = [x[0] for x in
            super(PaymentSucceedBatch, cls).select_ids(**kwargs)]

        if group_ids:
            cursor.execute(*payment.select(payment.group, payment.id,
                    where=payment.group.in_(group_ids) &
                    (payment.state == 'processing')))
            for group, payment in cursor.fetchall():
                payments_per_group[group].append(payment)
            for group, payments in payments_per_group.iteritems():
                yield [(x,) for x in payments]
        if not group_ids:
            yield []

    @classmethod
    def execute(cls, objects, ids, treatment_date, group_reference=None,
            payment_kind=None, journal_methods=None, auto_acknowledge=None):
        pool = Pool()
        Payment = pool.get('account.payment')
        with Transaction().set_context(disable_auto_aggregate=True,
                reconcile_to_date=treatment_date):
            Payment.succeed(objects)
        cls.logger.info('%s succeed' %
            coog_string.get_print_infos([x.id for x in objects], 'payment'))


class PaymentAcknowledgeBatch(PaymentValidationBatchBase):
    'Payment Acknowledge Batch'
    __name__ = 'account.payment.acknowledge'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.payment.group'

    @classmethod
    def payment_invalid(cls, payment):
        return payment.state == 'processing'

    @classmethod
    def select_ids(cls, treatment_date, group_reference=None,
            payment_kind=None, journal_methods=None, auto_acknowledge=None):
        pool = Pool()
        Group = pool.get('account.payment.group')
        Payment = pool.get('account.payment')
        group_ids = [x[0] for x in
            super(PaymentAcknowledgeBatch, cls).select_ids(treatment_date,
                group_reference, payment_kind, journal_methods,
                auto_acknowledge)]

        to_process_groups = []
        groups = Group.browse(group_ids)
        for group in groups:
            for sliced_payments in grouped_slice(Payment.search([
                    ('group', '=', group.id)])):
                if any(cls.payment_invalid(p) for p in sliced_payments):
                    break
            else:
                to_process_groups.append(group)

        for group in to_process_groups:
            yield (group.id,)

    @classmethod
    def execute(cls, objects, ids, treatment_date, group_reference=None,
            payment_kind=None, journal_methods=None, auto_acknowledge=None):
        Pool().get('account.payment.group').acknowledge(objects)
        return ids
