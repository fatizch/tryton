from sql import Null

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import batch, coop_string


__all__ = [
    'CreateCommissionInvoiceBatch',
    'PostCommissionInvoiceBatch',
    ]


class CreateCommissionInvoiceBatch(batch.BatchRoot):
    'Commission Invoice Creation Batch'

    __name__ = 'commission.invoice.create'

    logger = batch.get_logger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'party.party'

    @classmethod
    def select_ids(cls, treatment_date, extra_args):
        cursor = Transaction().cursor
        pool = Pool()

        agent = pool.get('commission.agent').__table__()
        commission = pool.get('commission').__table__()

        if 'agent_type' not in extra_args:
            cls.logger.warning('No agent_type defined. '
                'Batch execution aborted')
            return

        query_table = agent.join(commission, condition=(
                commission.agent == agent.id))

        cursor.execute(*query_table.select(agent.party,
                where=((commission.invoice_line == Null) &
                    (commission.date <= treatment_date) &
                    (agent.type_ == extra_args['agent_type'])),
                group_by=[agent.party]))

        return cursor.fetchall()

    @classmethod
    def commission_domain(cls, treatment_date, parties):
        domain = [
            ('invoice_line', '=', None),
            ('date', '<=', treatment_date),
            ('agent.party', 'in', parties)]
        return domain

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        pool = Pool()
        Commission = pool.get('commission')
        Invoice = pool.get('account.invoice')
        if 'agent_type' not in extra_args:
            cls.logger.warning('No agent_type defined. '
                'Batch execution aborted')
            return
        commissions = Commission.search(cls.commission_domain(
            treatment_date, ids),
            order=[('agent', 'DESC'), ('date', 'DESC')])
        invoices = Commission.invoice(commissions)
        Invoice.write(invoices, {'invoice_date': treatment_date})
        cls.logger.info('Commissions invoices created for %s' %
            coop_string.get_print_infos(ids,
                'brokers' if extra_args['agent_type'] == 'agent'
                else 'insurers'))


class PostCommissionInvoiceBatch(batch.BatchRoot):
    'Post Commission Invoice Batch'

    __name__ = 'commission.invoice.post'

    logger = batch.get_logger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def select_ids(cls, treatment_date, extra_args):
        pool = Pool()
        AccountInvoice = pool.get('account.invoice')

        if 'agent_type' not in extra_args:
            cls.logger.warning('No agent_type defined. '
                'Batch execution aborted')
            return

        status = ['validated']
        if extra_args.get('with_draft', False):
            status += ['draft']
        domain = [('state', 'in', status)]

        if extra_args['agent_type'] == 'agent':
            domain.append(('is_broker_invoice', '=', True),)
        elif extra_args['agent_type'] == 'principal':
            domain.append(('is_insurer_invoice', '=', True),)

        invoices = AccountInvoice.search(domain)
        return [[invoice.id] for invoice in invoices]

    @classmethod
    def execute(cls, objects, ids, treatment_date, extra_args):
        Pool().get('account.invoice').post(objects)
        cls.logger.info('%d commissions invoices posted' % len(objects))
