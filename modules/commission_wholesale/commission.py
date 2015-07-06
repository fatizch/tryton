from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Agent',
    'Commission',
    'CreateInvoicePrincipal',
    ]


class Agent:
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
            return self.party.account_receivable
        return super(Agent, self).account


class Commission:
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
                ('insurer', self.commissioned_option.coverage.insurer),
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
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if ('insurer' not in key or 'delegation_of_payment' not in key or
                key['delegation_of_payment']):
            return super(Commission, cls)._get_invoice(key)
        insurer = key['insurer']
        agent = key['agent']
        if key['type'].startswith('out'):
            payment_term = insurer.party.customer_payment_term
        else:
            payment_term = insurer.party.supplier_payment_term
        return Invoice(
            company=agent.company,
            type=key['type'],
            journal=cls.get_journal(),
            party=insurer.party,
            invoice_address=insurer.party.address_get(type='invoice'),
            currency=agent.currency,
            account=agent.account,
            payment_term=payment_term,
            description=agent.rec_name)


class CreateInvoicePrincipal:
    __name__ = 'commission.create_invoice_principal'

    @classmethod
    def __setup__(cls):
        super(CreateInvoicePrincipal, cls).__setup__()
        cls._error_messages.update({
                'wholesale_broker_reimbursement':
                'Wholesale broker reimbursement %s'
                })

    def get_wholesale_brokers_line_domain(self, account, party):
        domain = [
            ('account', '=', account.id),
            ('principal_invoice_line', '=', None),
            ('journal.type', '=', 'commission'),
            ('party', '!=', party.id),
            ('origin.id', '!=', None, 'account.invoice')
            ]
        if self.ask.until_date:
            domain.append(('date', '<=', self.ask.until_date))
        return domain

    def create_insurer_notice(self, party):
        '''
        This method adds the commission amount paid to wholesale brokers to the
        insurer invoice
        '''
        pool = Pool()
        Line = pool.get('account.move.line')
        Invoice = pool.get('account.invoice')

        commission_invoice = super(CreateInvoicePrincipal, self).\
            create_insurer_notice(party)
        account = party.insurer_role[0].waiting_account
        if not commission_invoice or not account:
            return commission_invoice

        lines = Line.search(
            self.get_wholesale_brokers_line_domain(account, party),
            order=[('party', 'ASC')])
        if not lines:
            return commission_invoice
        for party, party_lines in groupby(lines, key=lambda x: x.party):
            amount = sum(l.amount for l in lines)
            invoice_line = self.get_wholesale_brokers_line(amount, account,
                party)
            invoice_line.invoice = commission_invoice
            invoice_line.save()
            Line.write(list(party_lines), {
                    'principal_invoice_line': invoice_line.id,
                    })
        Invoice.update_taxes([commission_invoice])
        return commission_invoice

    def get_wholesale_brokers_line(self, amount, account, party):
        pool = Pool()
        Line = pool.get('account.invoice.line')

        line = Line()
        line.type = 'line'
        line.quantity = 1
        line.unit_price = amount
        line.account = account
        line.description = self.raise_user_error(
            'wholesale_broker_reimbursement', party.rec_name,
            raise_exception=False)
        return line
