# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from sql.aggregate import Max
from sql.operators import Not

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch, coog_string


__all__ = [
    'CreateInvoiceContractBatch',
    'PostInvoiceContractBatch',
    'SetNumberInvoiceContractBatch',
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
                condition=(Not(contract.status.in_(['hold', 'quote']))
                    & (contract.id == contract_invoice.contract)))

        cursor.execute(*query_table.select(account_invoice.id,
                where=((contract_invoice.start <= treatment_date)
                    & (account_invoice.state == 'validated'))))

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
        for obj in objects:
            obj.set_number()
        cls.logger.info('%d invoices numbers set' % len(objects))
