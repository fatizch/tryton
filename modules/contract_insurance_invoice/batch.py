# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from sql import Null, Cast, Expression
from sql.aggregate import Max
from sql.functions import ToChar, CurrentTimestamp
from sql.operators import Not, Concat
from itertools import groupby

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.server_context import ServerContext

from trytond.modules.coog_core import batch, coog_string


__all__ = [
    'CreateInvoiceContractBatch',
    'PostInvoiceContractBatch',
    'SetNumberInvoiceContractBatch',
    'InvoiceAgainstBalanceBatch',
    'SetNumberInvoiceAgainstBalanceBatch',
    'PostInvoiceAgainstBalanceBatch',
    ]


class CreateInvoiceContractBatch(batch.BatchRoot):
    'Contract Invoice Creation Batch'

    __name__ = 'contract.invoice.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().connection.cursor()
        pool = Pool()

        contract = pool.get('contract').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()
        invoice = pool.get('account.invoice').__table__()

        query_table = contract.join(contract_invoice, condition=(
                contract.id == contract_invoice.contract)
            ).join(invoice, condition=(
                contract_invoice.invoice == invoice.id) &
            (invoice.state != 'cancel'))

        cursor.execute(*query_table.select(contract.id, group_by=contract.id,
                where=(contract.status == 'active'),
                having=(
                    (Max(contract_invoice.end) < treatment_date)
                    | (Max(contract_invoice.end) == Null))))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        invoices = Pool().get('contract').invoice(objects, treatment_date)
        cls.logger.info('%d invoices created for %s' %
            (len(invoices), coog_string.get_print_infos(ids, 'contracts')))


class PostInvoiceContractBatch(batch.BatchRoot):
    'Post Contract Invoice Batch'

    __name__ = 'contract.invoice.post'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().connection.cursor()
        pool = Pool()

        account_invoice = pool.get('account.invoice').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()
        contract = pool.get('contract').__table__()

        query_table = contract_invoice.join(account_invoice, 'LEFT',
            condition=(account_invoice.id == contract_invoice.invoice)
            ).join(contract,
                condition=(Not(contract.status.in_(['hold', 'quote'])) &
                    (contract.id == contract_invoice.contract)))

        cursor.execute(*query_table.select(account_invoice.id,
                where=((contract_invoice.start <= treatment_date) &
                    (account_invoice.state == 'validated')),
                    order_by=contract_invoice.start.asc))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Pool().get('account.invoice').post(objects)
        cls.logger.info('%d invoices posted' % len(objects))


class SetNumberInvoiceContractBatch(batch.BatchRoot):
    'Set Contract Invoice Number Batch'

    __name__ = 'contract.invoice.set_number'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def select_ids(cls, treatment_date):
        job_size = cls.get_conf_item('job_size')
        assert job_size == '0', 'Can not scale out'
        pool = Pool()
        post_batch = pool.get('contract.invoice.post')
        return post_batch.select_ids(treatment_date)

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        with ServerContext().set_context(disable_invoice_validation=True,
                forced_invoice_type='_invoice'):
            Pool().get('account.invoice').set_number(objects)
        cls.logger.info('%d invoices numbers set' % len(objects))


class InvoiceAgainstBalanceBatch(batch.BatchRoot):
    'Invoice Against Contract Balance Batch'

    __name__ = 'contract.invoice.against_balance.batch'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def select_ids(cls, treatment_date, ids_list):
        return [(int(x),) for x in ids_list[1:-1].split(',')]

    @classmethod
    def execute(cls, objects, ids, treatment_date, ids_list):
        for contract in objects:
            contract.reconcile()
            if contract.status not in ['void', 'declined', 'quote']:
                contract.invoice_against_balance()
        return ids


class SetNumberInvoiceAgainstBalanceBatch(batch.BatchRoot):
    'Number Invoice Against Contract Balance Batch'

    __name__ = 'contract.invoice.against_balance.set_number.batch'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def select_ids(cls, treatment_date, ids_list):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        account_invoice = pool.get('account.invoice').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()

        invoice_against_batch = pool.get(
            'contract.invoice.against_balance.batch')
        contracts = [x[0] for x in invoice_against_batch.select_ids(
                treatment_date, ids_list)]

        query_table = contract_invoice.join(account_invoice,
            condition=(
                (account_invoice.id == contract_invoice.invoice) &
                (contract_invoice.contract.in_(contracts))))
        cursor.execute(*query_table.select(account_invoice.id,
                contract_invoice.contract,
                where=account_invoice.state == 'validated',
                order_by=contract_invoice.contract))
        groups = cursor.fetchall()
        res = []
        for key, group in groupby(groups, key=lambda x: x[1]):
            res.append([x[0] for x in group])
        return res

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        for contract, invoices in groupby(objects, key=lambda x: x.contract):
            invoices = iter(sorted(invoices, key=lambda x: x.start))
            balance = contract.balance
            while balance < 0:
                invoice = next(invoices, None)
                if not invoice:
                    break
                invoice.set_number()
                balance += invoice.total_amount
        return ids


class PostInvoiceAgainstBalanceBatch(batch.BatchRoot):
    'Post Invoice Against Contract Balance Batch'

    __name__ = 'contract.invoice.against_balance.post.batch'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def select_ids(cls, treatment_date, ids_list):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        account_invoice = pool.get('account.invoice').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()

        invoice_against_batch = pool.get(
            'contract.invoice.against_balance.batch')
        contracts = [x[0] for x in invoice_against_batch.select_ids(
                treatment_date, ids_list)]

        query_table = contract_invoice.join(account_invoice,
            condition=(
                (account_invoice.id == contract_invoice.invoice) &
                (contract_invoice.contract.in_(contracts))))
        cursor.execute(*query_table.select(account_invoice.id,
                contract_invoice.contract,
                where=((account_invoice.state == 'validated') &
                    (account_invoice.number != Null)),
                order_by=contract_invoice.contract))
        groups = cursor.fetchall()

        res = []
        for key, group in groupby(groups, key=lambda x: x[1]):
            res.append([x[0] for x in group])
        return res

    @classmethod
    def execute(cls, objects, ids, treatment_date, ids_list):
        Invoice = Pool().get('account.invoice')

        for contract, invoices in groupby(objects, key=lambda x: x.contract):
            Invoice.post(list(invoices))
            contract.reconcile(limit_date=False)
        return ids


class RowNumber(Expression):
    def __str__(self):
        return 'ROW_NUMBER() over ()'

    @property
    def params(self):
        return []


class BulkSetNumberInvoiceContractBatch(batch.BatchRoot):
    'Set Contract Invoice Number Batch'

    __name__ = 'contract.invoice.bulk_set_number'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(BulkSetNumberInvoiceContractBatch, cls).__setup__()
        cls._error_messages.update({
                'no_period': 'No periods found for invoice date: %s',
                })
        cls._default_config_items.update({'job_size': '1'})

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return []

    @classmethod
    def select_ids(cls, treatment_date):
        job_size = cls.get_conf_item('job_size')
        assert job_size == '1', 'job_size must be set to 1, current value: %s' \
            % (job_size)

        cursor = Transaction().connection.cursor()
        pool = Pool()

        account_invoice = pool.get('account.invoice').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()
        contract = pool.get('contract').__table__()

        query_table = contract_invoice.join(account_invoice, 'LEFT',
            condition=(account_invoice.id == contract_invoice.invoice)
            ).join(contract,
                condition=(Not(contract.status.in_(['hold', 'quote',
                                'declined'])) &
                    (contract.id == contract_invoice.contract)))
        cursor.execute(*query_table.select(
                account_invoice.company,
                account_invoice.invoice_date,
                account_invoice.id,
                where=((contract_invoice.start <= treatment_date) &
                    (account_invoice.state == 'validated') &
                    (account_invoice.number == Null)),
                order_by=(account_invoice.company,
                    account_invoice.invoice_date,
                    contract_invoice.start.asc)))
        results = cursor.fetchall()
        invoice_ids = []
        for company_date, grouped_results in groupby(results,
                lambda x: (x[0], x[1])):
            invoice_ids.append([(x[2],) for x in grouped_results])
        return invoice_ids

    @classmethod
    def bulk_set_number(cls, ids):
        pool = Pool()
        Period = pool.get('account.period')
        AccountInvoice = pool.get('account.invoice')
        if not ids:
            return
        ids_list = [x[0] for x in ids]

        # all the invoices have the same company and the same invoice date
        invoice = AccountInvoice(ids_list[0])
        tax_identifier = invoice.get_tax_identifier()
        if not tax_identifier:
            tax_identifier = Null
        period_id = Period.find(invoice.company.id,
            date=invoice.invoice_date, test_state=True)
        period = Period(period_id)
        if not period:
            cls.raise_user_error('no_period', invoice.invoice_date)
        invoice_type = 'out_invoice'
        sequence = period.get_invoice_sequence(invoice_type)

        with Transaction().set_context(date=invoice.invoice_date):
            transaction = Transaction()
            transaction.database.lock(transaction.connection, sequence._table)
            prefix = sequence._process(sequence.prefix, invoice.invoice_date)
            suffix = sequence._process(sequence.suffix, invoice.invoice_date)
            nbr_next = sequence.number_next_internal
            increment = sequence.number_increment
            number_query = None
            if not sequence.padding:
                number_query = Concat(Concat(prefix, Cast((RowNumber() - 1)
                            * increment + nbr_next, 'VARCHAR')),
                    suffix).as_('number')
            else:
                number_query = Concat(Concat(prefix, ToChar((RowNumber() - 1)
                            * increment + nbr_next,
                            'FM' + ('0' * sequence.padding))),
                    suffix).as_('number')
            account_invoice = AccountInvoice.__table__()
            to_update = account_invoice.select(account_invoice.id.as_('inv_id'),
                number_query,
                where=account_invoice.id.in_(ids_list))
            query = account_invoice.update(columns=[account_invoice.number,
                account_invoice.tax_identifier, account_invoice.write_date],
                from_=[to_update],
                values=[to_update.number, tax_identifier, CurrentTimestamp()],
                where=account_invoice.id == to_update.inv_id)
            cursor = transaction.connection.cursor()
            cursor.execute(*query)
            sequence.number_next_internal = nbr_next + len(ids_list) * increment
            sequence.save()
            return ids

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        res = cls.bulk_set_number(ids)
        cls.logger.info('%d invoices numbers set' % len(ids))
        return res
