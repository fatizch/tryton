# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import defaultdict

from sql import Null, Cast
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import coog_sql

__all__ = [
    'InvoiceSlipConfiguration',
    ]


class InvoiceSlipConfiguration:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.slip.configuration'

    @classmethod
    def _get_new_slip(cls, parameters):
        invoice = super(InvoiceSlipConfiguration, cls)._get_new_slip(parameters)
        invoice.insurer_role = parameters.get('insurer', None)
        return invoice

    @classmethod
    def _get_slip_lines(cls, account, parameters):
        return super(InvoiceSlipConfiguration, cls)._get_slip_lines(
            account, parameters) + [
            cls._get_slip_line(account, '%s > 0' % account.rec_name,
                    parameters),
            cls._get_slip_line(account, '%s < 0' % account.rec_name,
                    parameters),
            ]

    @classmethod
    def _retrieve_empty_slips(cls, slip_parameters):
        '''
            Override to add the commissions positive / negative lines
        '''
        per_account = super(InvoiceSlipConfiguration,
            cls)._retrieve_empty_slips(slip_parameters)
        for account, data in per_account.iteritems():
            invoice = data['invoice']
            try:
                data['positive_invoice_line'] = cls._find_slip_line(
                    account, '%s > 0' % account.rec_name, invoice)
            except KeyError:
                pass

            try:
                data['negative_invoice_line'] = cls._find_slip_line(
                    account, '%s < 0' % account.rec_name, invoice)
            except KeyError:
                pass

        return per_account

    @classmethod
    def _get_invoices_data(cls, slip_parameters, invoices_data):
        '''
            Look for commissions and add them to the data. For invoices without
            any commissions, forward to super.
        '''
        pool = Pool()
        Commission = pool.get('commission')
        Invoice = pool.get('account.invoice')

        slip_date = slip_parameters[0]['date']
        per_account = defaultdict(lambda: {'lines': [], 'commissions': []})
        to_ignore = defaultdict(list)
        to_sum = defaultdict(lambda: defaultdict(list))

        # TODO: We only need to browse in order to know the invoices states,
        # maybe we could include it in the select_invoices data query
        per_id = {x.id: x for x in Invoice.browse(invoices_data.keys())}
        remains = set(invoices_data.keys())

        for invoice_id, commission_id, date, account in \
                cls._get_insurer_commissions(slip_parameters, per_id.keys()):
            if invoice_id in remains:
                remains.remove(invoice_id)
            if not date or not slip_date or date <= slip_date:
                # Ignore lines without date if invoice state is posted : we are
                # handling an unreconciled invoice
                if not date and per_id[invoice_id].state == 'posted':
                    continue
                to_sum[account][invoice_id].append(commission_id)
            else:
                to_ignore[account].append(invoice_id)

        for insurer_account, value in to_sum.iteritems():
            for invoice_id, commissions in value.iteritems():
                if invoice_id not in to_ignore[insurer_account]:
                    per_account[insurer_account]['commissions'] += \
                        Commission.browse(commissions)
                    for line, account in invoices_data[invoice_id]:
                        per_account[account]['lines'].append(line)
                else:
                    continue

        if remains:
            # Invoices which must be included, but without any commissions
            # attached to them => just call super
            inputs = {x: y for x, y in invoices_data.iteritems()
                if x in remains}
            no_commission_data = super(InvoiceSlipConfiguration,
                cls)._get_invoices_data(slip_parameters, inputs)
            for account_id, data in no_commission_data.iteritems():
                per_account[account_id]['lines'] += data['lines']

        return per_account

    @classmethod
    def _get_insurer_commissions(cls, slip_parameters, invoices_ids):
        '''
            Returns all commissions associated to the invoices given as
            parameters, if they are meant for the insurers found in the slip
            parameters
        '''
        pool = Pool()
        commission = pool.get('commission').__table__()
        cursor = Transaction().connection.cursor()
        line = pool.get('account.invoice.line').__table__()
        agent = pool.get('commission.agent').__table__()
        option = pool.get('offered.option.description').__table__()

        insurers = filter(
            None, [x.get('insurer', None) for x in slip_parameters])
        if not insurers or not invoices_ids:
            return []

        query_table = line.join(option
            .join(agent, condition=(option.insurer == agent.insurer) &
                option.insurer.in_([x.id for x in insurers]))
            .join(commission, condition=(agent.id == commission.agent)),
            condition=(commission.origin == coog_sql.TextCat(
                    'account.invoice.line,', Cast(line.id, 'VARCHAR'))))

        query = query_table.select(
            line.invoice, commission.id, commission.date,
            option.account_for_billing,
            group_by=[commission.id, option.insurer, line.invoice,
                option.account_for_billing],
            where=line.invoice.in_(invoices_ids) &
            (commission.invoice_line == Null))
        cursor.execute(*query)
        return cursor.fetchall()

    @classmethod
    def _update_backrefs(cls, slip_parameters, invoices_data, current_slips):
        '''
            This override will set the invoice_line field on the commissions
            that will be included in the slip
        '''
        super(InvoiceSlipConfiguration, cls)._update_backrefs(
            slip_parameters, invoices_data, current_slips)
        cls._update_commissions(slip_parameters, invoices_data, current_slips)

    @classmethod
    def _update_commissions(cls, slip_parameters, invoices_data,
            current_slips):
        cursor = Transaction().connection.cursor()
        commission_table = Pool().get('commission').__table__()
        for account, account_data in current_slips.iteritems():
            account_invoice_data = invoices_data[account.id]
            if not account_invoice_data.get('commissions', None):
                continue
            positives, negatives = [], []
            for commission in account_invoice_data['commissions']:
                if account_data['invoice'].type.startswith(commission.type_):
                    negatives.append(commission.id)
                else:
                    positives.append(commission.id)

            if positives:
                cursor.execute(*commission_table.update(
                        [commission_table.invoice_line],
                        [account_data['positive_invoice_line'].id],
                        where=commission_table.id.in_(positives)))
            if negatives:
                cursor.execute(*commission_table.update(
                        [commission_table.invoice_line],
                        [account_data['negative_invoice_line'].id],
                        where=commission_table.id.in_(negatives)))

    @classmethod
    def _finalize_invoice_lines(cls, slip_parameters, account_data):
        super(InvoiceSlipConfiguration, cls)._finalize_invoice_lines(
            slip_parameters, account_data)
        cls._finalize_commission_lines(slip_parameters, account_data)

    @classmethod
    def _finalize_commission_lines(cls, slip_parameters, account_data):
        if 'positive_invoice_line' in account_data:
            cls._update_commission_invoice_lines(account_data['invoice'],
                account_data['positive_invoice_line'],
                account_data['negative_invoice_line'])

    @classmethod
    def _update_commission_invoice_lines(cls, commission_invoice,
            positive_line, negative_line):
        pool = Pool()
        Product = pool.get('product.product')
        Line = pool.get('account.invoice.line')
        Commission = pool.get('commission')
        Agent = pool.get('commission.agent')
        commission = Commission.__table__()
        cursor = Transaction().connection.cursor()
        to_save = []

        query = commission.select(
            Sum(Coalesce(commission.amount, 0)).as_('amount'),
            commission.product, commission.agent,
            commission.invoice_line,
            group_by=[commission.agent, commission.product,
                commission.invoice_line],
            where=commission.invoice_line.in_(
                [positive_line.id, negative_line.id]))
        cursor.execute(*query)
        matches = []
        for amount, product, agent, invoice_line in cursor.fetchall():
            matches.append((product, agent))
            agent = Agent(agent)
            product = Product(product)
            new_invoice_line = cls._get_slip_line(product.account_revenue_used,
                agent.rec_name, {'party': commission_invoice.party})
            new_invoice_line.invoice = commission_invoice
            if invoice_line == negative_line.id:
                new_invoice_line.unit_price = amount * -1
            else:
                new_invoice_line.unit_price = amount
            new_invoice_line.unit_price = Decimal(new_invoice_line.unit_price
                ).quantize(Decimal(10) ** -Line.unit_price.digits[1])
            new_invoice_line.product = product
            new_invoice_line.on_change_product()
            # JCA : Force account field, since on_change_product forces it to
            # the product account. TODO : Investigate what is it in
            # on_change_product that we need ?
            new_invoice_line.account = product.account_revenue_used
            new_invoice_line.invoice = commission_invoice
            to_save.append(new_invoice_line)
        Line.save(to_save)
        for line, (product, agent) in zip(to_save, matches):
            cursor.execute(*commission.update([commission.invoice_line],
                    [line.id], where=commission.invoice_line.in_(
                        [positive_line.id, negative_line.id])
                    & (commission.product == product)
                    & (commission.agent == agent)))
        Line.delete([negative_line, positive_line])

    @classmethod
    def _event_code_from_slip_kind(cls, slip_kind):
        if slip_kind in ('all_insurer_invoices', 'insurer_invoice'):
            return 'commission_invoice_generated'
        return super(InvoiceSlipConfiguration,
            cls)._event_code_from_slip_kind(slip_kind)
