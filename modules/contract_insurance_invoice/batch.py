from sql.aggregate import Max

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import batch


__all__ = [
    'CreateInvoiceContractBatch',
    'PostInvoiceContractBatch',
    ]


class CreateInvoiceContractBatch(batch.BatchRoot):
    'Contract Invoice Creation Batch'

    __name__ = 'contract.invoice.create'

    logger = batch.get_logger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().cursor
        pool = Pool()

        contract = pool.get('contract').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()

        query_table = contract.join(contract_invoice, 'LEFT', condition=(
                contract.id == contract_invoice.contract))

        cursor.execute(*query_table.select(contract.id, group_by=contract.id,
                where=(contract.status == 'active'),
                having=(
                    (Max(contract_invoice.end) < treatment_date)
                    | (Max(contract_invoice.end) == None))))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Pool().get('contract').invoice(objects, treatment_date)
        cls.logger.info('%d invoices created' % len(objects))


class PostInvoiceContractBatch(batch.BatchRoot):
    'Post Contract Invoice Batch'

    __name__ = 'contract.invoice.post'

    logger = batch.get_logger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().cursor
        pool = Pool()

        account_invoice = pool.get('account.invoice').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()

        query_table = contract_invoice.join(account_invoice, 'LEFT',
            condition=(account_invoice.id == contract_invoice.invoice))

        cursor.execute(*query_table.select(account_invoice.id,
                where=((contract_invoice.start <= treatment_date)
                    & (account_invoice.state == 'validated'))))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Pool().get('account.invoice').post(objects)
        cls.logger.info('%d invoices posted' % len(objects))
