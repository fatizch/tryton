# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'Agent',
    'Commission',
    'FilterCommissions',
    ]


class Agent(metaclass=PoolMeta):
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


class Commission(metaclass=PoolMeta):
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


class FilterCommissions(metaclass=PoolMeta):
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
