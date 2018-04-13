# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.modules.coog_core import model, fields

__all__ = [
    'ChangePaymentTerm',
    'SelectTerm',
    'PartyErase',
    ]


class ChangePaymentTerm(Wizard):
    'Change Payment Term'

    __name__ = 'account.invoice.change_payment_term'

    start_state = 'select_term'
    select_term = StateView('account.invoice.change_payment_term.select_term',
        'account_invoice_cog.select_term_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Change', 'change', 'tryton-go-next', default=True)])
    change = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ChangePaymentTerm, cls).__setup__()
        cls._error_messages.update({
                'bad_state': 'The invoice must be posted !',
                })

    def default_select_term(self, name):
        assert Transaction().context.get('active_model') == 'account.invoice'
        invoice = Pool().get('account.invoice')(Transaction().context.get(
                'active_id'))
        if invoice.state != 'posted':
            self.raise_user_error('bad_state')
        return {
            'invoice': invoice.id,
            'current_term': invoice.payment_term.id,
            'current_invoice_date': invoice.invoice_date,
            }

    def transition_change(self):
        Pool().get('account.invoice').change_term([self.select_term.invoice],
            self.select_term.new_term, self.select_term.new_invoice_date)
        return 'end'


class SelectTerm(model.CoogView):
    'Select Term'

    __name__ = 'account.invoice.change_payment_term.select_term'

    invoice = fields.Many2One('account.invoice', 'Invoice',
        required=True, readonly=True)
    current_term = fields.Many2One('account.invoice.payment_term',
        'Current Payment Term', readonly=True)
    new_term = fields.Many2One('account.invoice.payment_term',
        'New Payment Term', domain=[('id', '!=', Eval('current_term'))],
        required=True, depends=['current_term'])
    new_invoice_date = fields.Date('New Invoice Date', required=True)
    current_invoice_date = fields.Date('Current Invoice Date', readonly=True)


class PartyErase:
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    def to_erase(self, party_id):
        to_erase = super(PartyErase, self).to_erase(party_id)
        Invoice = Pool().get('account.invoice')
        to_erase.append(
            (Invoice, [('party', '=', party_id)], True,
                ['description', 'comment'],
                [None, None]))
        return to_erase
