# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from sql import Null

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch, coog_string


__all__ = [
    'CreateCommissionInvoiceBatch',
    'PostCommissionInvoiceBatch',
    ]


class CreateCommissionInvoiceBatch(batch.BatchRoot):
    'Commission Invoice Creation Batch'

    __name__ = 'commission.invoice.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'party.party'

    @classmethod
    def select_ids(cls, treatment_date, agent_type):
        cursor = Transaction().connection.cursor()
        pool = Pool()

        agent = pool.get('commission.agent').__table__()
        commission = pool.get('commission').__table__()

        if not agent_type:
            cls.logger.warning('No agent_type defined. '
                'Batch execution aborted')
            return

        query_table = agent.join(commission, condition=(
                commission.agent == agent.id))

        cursor.execute(*query_table.select(agent.party,
                where=((commission.invoice_line == Null) &
                    (commission.date <= treatment_date) &
                    (agent.type_ == agent_type)),
                group_by=[agent.party]))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date, agent_type):
        pool = Pool()
        Commission = pool.get('commission')
        Invoice = pool.get('account.invoice')
        CreateInvoiceWizard = pool.get('commission.create_invoice',
            type='wizard')
        if not agent_type:
            cls.logger.warning('No agent_type defined. '
                'Batch execution aborted')
            return
        commissions = CreateInvoiceWizard.fetch_commmissions_to_invoice(
            to=treatment_date, agent_party_ids=ids)
        invoices = Commission.invoice(commissions)
        Invoice.write(invoices, {'invoice_date': treatment_date})
        cls.logger.info('Commissions invoices created for %s' %
            coog_string.get_print_infos(ids,
                'brokers' if agent_type == 'agent'
                else 'insurers'))


class PostCommissionInvoiceBatch(batch.BatchRoot):
    'Post Commission Invoice Batch'

    __name__ = 'commission.invoice.post'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def select_ids(cls, agent_type, with_draft=False):
        pool = Pool()
        AccountInvoice = pool.get('account.invoice')

        if not agent_type:
            cls.logger.warning('No agent_type defined. '
                'Batch execution aborted')
            return

        status = ['validated']
        if with_draft:
            status += ['draft']
        domain = [('state', 'in', status)]

        if agent_type == 'agent':
            domain.append(('business_kind', '=', 'broker_invoice'),)
        elif agent_type == 'principal':
            domain.append(('business_kind', '=', 'insurer_invoice'),)

        invoices = AccountInvoice.search(domain)
        return [(invoice.id,) for invoice in invoices]

    @classmethod
    def execute(cls, objects, ids, agent_type, with_draft=False):
        Pool().get('account.invoice').post(objects)
        cls.logger.info('%d commissions invoices posted' % len(objects))
