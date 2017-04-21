# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from sql import Null
from sql.aggregate import Max
from sql.operators import Not
from itertools import groupby

from trytond.pool import Pool
from trytond.transaction import Transaction

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
                    | (Max(contract_invoice.end) == None))))

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
