# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.wizard import Wizard, StateView, StateTransition, StateAction
from trytond.wizard import Button

from trytond.modules.coog_core import model, fields


__all__ = [
    'Surrender',
    'SurrenderParameters',
    'SurrenderPreview',
    ]


class Surrender(Wizard):
    'Surrender'
    __name__ = 'contract.surrender'

    start_state = 'parameters'
    parameters = StateView('contract.surrender.parameters',
        'contract_surrender.surrender_parameters_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('Preview', 'calculate', 'tryton-go-next', default=True),
            ])
    calculate = StateTransition()
    preview = StateView('contract.surrender.preview',
        'contract_surrender.surrender_preview_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'parameters', 'tryton-go-previous'),
            Button('Surrender', 'surrender', 'tryton-go-next', default=True),
            ])
    surrender = StateTransition()
    open_invoice = StateAction('account_invoice.act_invoice_in_form')

    @classmethod
    def __setup__(cls):
        super(Surrender, cls).__setup__()
        cls._error_messages.update({
                'invalid_date': 'Impossible to surrender before the '
                'contract\'s start_date (%(start_date)s)',
                })

    def default_parameters(self, name):
        if self.parameters._default_values:
            return self.parameters._default_values
        assert Transaction().context.get('active_model') == 'contract'
        contract = Pool().get('contract')(
            Transaction().context.get('active_id'))
        if not contract.can_surrender:
            contract.raise_user_error('cannot_surrender', {
                    'contract': contract.rec_name})
        return {
            'contract': contract.id,
            }

    def transition_calculate(self):
        self.check_parameters()
        self.calculate_surrenders()
        return 'preview'

    def check_parameters(self):
        if (self.parameters.contract.start_date >=
                self.parameters.surrender_date):
            self.raise_user_error('invalid_date', {
                    'start_date': self.parameters.contract.start_date})

    def calculate_surrenders(self):
        contract = self.parameters.contract
        contract.check_for_surrender([contract],
            self.parameters.surrender_date)
        surrenders = contract.calculate_surrenders(
            self.parameters.surrender_date)
        self.preview.contract = contract
        self.preview.currency = contract.currency
        self.preview.currency_digits = contract.currency_digits
        self.preview.currency_symbol = contract.currency_symbol
        self.preview.surrender_value = sum([x[1] for x in surrenders],
            Decimal(0))
        return 'preview'

    def default_preview(self, name):
        if self.preview._default_values:
            return self.preview._default_values
        return {}

    def transition_surrender(self):
        contract = self.parameters.contract
        contract.surrender([contract], self.parameters.surrender_date)
        return 'open_invoice'

    def do_open_invoice(self, action):
        Invoice = Pool().get('account.invoice')
        contract = self.parameters.contract
        invoice, = Invoice.search([
                ('contract', '=', contract.id),
                ('business_kind', '=', 'surrender'),
                ('state', 'in', ('posted', 'paid'))])
        return action, {
            'res_id': invoice.id,
            'res_ids': [invoice.id],
            'res_model': 'account.invoice',
            }


class SurrenderParameters(model.CoogView):
    'Surrender Parameters'
    __name__ = 'contract.surrender.parameters'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    surrender_date = fields.Date('Surrender Date', required=True,
        help='The date at which the contract will be surrendered')


class SurrenderPreview(model.CoogView):
    'Surrender Preview'
    __name__ = 'contract.surrender.preview'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    currency = fields.Many2One('currency.currency', 'Currency', readonly=True)
    currency_digits = fields.Integer('Currency Digits', readonly=True)
    currency_symbol = fields.Char('Currency Symbol', readonly=True)
    surrender_value = fields.Numeric('Surrender Value',
        digits=(16, Eval('currency_digits', 2)), readonly=True,
        depends=['currency_digits'], help='The amount that will be surrendered')
