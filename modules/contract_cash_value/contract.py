# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If

from trytond.modules.coog_core import fields, model
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'Contract',
    'ContractDeposit',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    is_cash_value = fields.Function(
        fields.Boolean('Is Cash Value'),
        'getter_is_cash_value')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'open_deposits': {'readonly': ~Eval('is_cash_value', False)},
                },
            )

    def getter_is_cash_value(self, name):
        return self.product and self.product.is_cash_value

    @classmethod
    @model.CoogView.button_action('contract_cash_value.act_open_deposits')
    def open_deposits(cls, contracts):
        pass


class ContractDeposit(model.CoogSQL, model.CoogView, ModelCurrency):
    'Contract Deposit'

    __name__ = 'contract.deposit'

    contract = fields.Many2One('contract', 'Contract', required=True,
        ondelete='CASCADE', select=True, readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('received', 'Received')],
        'State', readonly=True, required=True, help='The current state of the '
        'deposit')
    date = fields.Date('Date', states={
            'required': Eval('state', '') == 'received',
            'readonly': Eval('state', '') != 'draft'}, depends=['state'],
        help='The date at which the deposit amount was effectively received')
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        states={'readonly': Eval('state', '') != 'draft'}, depends=['state'],
        required=True, ondelete='RESTRICT')
    invoice = fields.Many2One('account.invoice', 'Invoice', required=True,
        ondelete='RESTRICT', domain=[
            If(Eval('state', '') == 'draft', [], [('state', '=', 'paid')])],
        states={'readonly': Eval('state', '') != 'draft'}, depends=['state'])
    amount = fields.Numeric('Amount', required=True,
        digits=(16, Eval('currency_digits', 2)),
        states={'readonly': Eval('state', '') != 'draft'},
        depends=['currency_digits', 'state'])

    @classmethod
    def __setup__(cls):
        super(ContractDeposit, cls).__setup__()
        cls._order = [('date', 'ASC'), ('coverage', 'ASC')]

    @classmethod
    def default_state(cls):
        return 'draft'

    @fields.depends('contract')
    def on_change_contract(self):
        self.currency = self.contract.currency if self.contract else None
        if self.currency:
            self.currency_digits = self.currency.digits
            self.currency_symbol = self.currency.symbol

    def get_currency(self):
        return self.contract.currency

    def init_dict_for_rule_engine(self, data_dict=None):
        if data_dict is None:
            data_dict = {}
        self.contract.init_dict_for_rule_engine(data_dict)
        self.coverage.init_dict_for_rule_engine(data_dict)
        data_dict['deposit'] = self
        return data_dict
