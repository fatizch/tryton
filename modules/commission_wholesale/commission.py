# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'Agent',
    'Commission',
    'FilterCommissions',
    'CreateInvoicePrincipal',
    ]


class Agent:
    __metaclass__ = PoolMeta
    __name__ = 'commission.agent'

    wholesale_broker = fields.Boolean('Wholesale Broker',
        states={'invisible': ~(Eval('type_') == 'agent')},
        depends=['type_'])
    delegation_of_payment = fields.Boolean('Delegation of Commission Payment',
        states={'invisible': ~Eval('wholesale_broker')},
        depends=['wholesale_broker'])

    @property
    def account(self):
        if (self.type_ == 'agent' and self.wholesale_broker and
                not self.delegation_of_payment):
            return self.party.account_receivable_used
        return super(Agent, self).account


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'

    @fields.depends('agent')
    def on_change_with_type_(self, name=None):
        if (self.agent and self.agent.wholesale_broker and
                not self.agent.delegation_of_payment):
            return 'in'
        return super(Commission, self).on_change_with_type_(name)

    def _group_to_invoice_key(self):
        key = super(Commission, self)._group_to_invoice_key()
        if self.agent.wholesale_broker and self.commissioned_option:
            return key + (
                ('insurer', self.commissioned_option.coverage.get_insurer(
                    self.start)),
                ('delegation_of_payment', self.agent.delegation_of_payment)
                )
        return key

    @classmethod
    def _get_invoice(cls, key):
        '''
        When there is no delegation of payment an invoice has to be created
        to request commission amount to the insurer for the wholesale brokers.
        The invoice has to be sent to the insurer
        '''
        invoice = super(Commission, cls)._get_invoice(key)
        if ('insurer' not in key or 'delegation_of_payment' not in key or
                key['delegation_of_payment']):
            return invoice
        insurer = key['insurer']
        party = insurer.party
        if key['type'].startswith('out'):
            payment_term = party.customer_payment_term
            account = party.account_receivable
        else:
            payment_term = party.supplier_payment_term
            account = party.account_payable_used
        invoice.party = party
        invoice.insurer_role = insurer
        invoice.invoice_address = party.address_get(type='invoice')
        invoice.account = account
        invoice.payment_term = payment_term
        invoice.business_kind = 'wholesale_invoice'
        return invoice


class CreateInvoicePrincipal:
    __metaclass__ = PoolMeta
    __name__ = 'commission.create_invoice_principal'

    @classmethod
    def __setup__(cls):
        super(CreateInvoicePrincipal, cls).__setup__()
        cls._error_messages.update({
                'wholesale_broker_reimbursement':
                'Wholesale broker reimbursement %s'
                })

    @classmethod
    def get_wholesale_brokers_line_domain(cls, account, party, until_date):
        domain = [
            ('account', '=', account.id),
            ('principal_invoice_line', '=', None),
            ('journal.type', '=', 'commission'),
            ('party', '!=', party.id),
            ('origin.id', '!=', None, 'account.invoice')
            ]
        if until_date:
            domain.append(('date', '<=', until_date))
        return domain

    @classmethod
    def finalize_invoices_and_lines(cls, insurers, company, journal,
            date, notice_kind):
        '''
        This method adds the commission amount paid to wholesale brokers to the
        insurer invoice
        '''

        pool = Pool()
        Line = pool.get('account.move.line')
        Invoice = pool.get('account.invoice')
        Insurer = pool.get('insurer')

        commission_invoices = super(CreateInvoicePrincipal,
            cls).finalize_invoices_and_lines(
            insurers, company, journal, date, notice_kind)
        for commission_invoice in commission_invoices:
            accounts = [x for y in Insurer.get_insurers_waiting_accounts(
                    [commission_invoice.insurer_role],
                    notice_kind).itervalues()
                for x in y]
            if not accounts:
                continue
            for account in accounts:
                lines = Line.search(
                    cls.get_wholesale_brokers_line_domain(account,
                        commission_invoice.party, date),
                    order=[('party', 'ASC')])
                if not lines:
                    continue
                for party, party_lines in groupby(
                        lines, key=lambda x: x.party):
                    amount = sum(-l.amount for l in lines)
                    invoice_line = cls.get_wholesale_brokers_line(
                        amount, account, party)
                    invoice_line.invoice = commission_invoice
                    invoice_line.save()
                    Line.write(list(party_lines), {
                            'principal_invoice_line': invoice_line.id,
                            })
        Invoice.update_taxes(commission_invoices)
        return commission_invoices

    @classmethod
    def get_wholesale_brokers_line(cls, amount, account, party):
        pool = Pool()
        Line = pool.get('account.invoice.line')

        line = Line()
        line.type = 'line'
        line.quantity = 1
        line.unit_price = amount
        line.account = account
        line.description = cls.raise_user_error(
            'wholesale_broker_reimbursement', party.rec_name,
            raise_exception=False)
        return line


class FilterCommissions:
    __metaclass__ = PoolMeta
    __name__ = 'commission.filter_commission'

    def get_domain_from_invoice_business_kind(self, ids, kinds):
        if len(kinds) != 1:
            return super(FilterCommissions,
                self).get_domain_from_invoice_business_kind(ids, kinds)
        kind = kinds[0]
        if kind == 'wholesale_invoice':
            return [('invoice_line.invoice', 'in', ids)]
        return super(FilterCommissions,
            self).get_domain_from_invoice_business_kind(ids, kinds)
