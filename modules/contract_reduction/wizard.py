# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.wizard import Wizard, StateView, StateTransition
from trytond.wizard import Button

from trytond.modules.coog_core import model, fields


__all__ = [
    'Reduce',
    'ReduceParameters',
    'ReducePreview',
    'CancelReduction',
    ]


class Reduce(Wizard):
    'Reduce'
    __name__ = 'contract.reduce'

    start_state = 'parameters'
    parameters = StateView('contract.reduce.parameters',
        'contract_reduction.reduction_parameters_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('Preview', 'calculate', 'tryton-go-next', default=True),
            ])
    calculate = StateTransition()
    preview = StateView('contract.reduce.preview',
        'contract_reduction.reduction_preview_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('Previous', 'parameters', 'tryton-go-previous'),
            Button('Reduce', 'reduce', 'tryton-go-next', default=True),
            ])
    reduce = StateTransition()

    @classmethod
    def __setup__(cls):
        super(Reduce, cls).__setup__()
        cls._error_messages.update({
                'no_reduction_rule': 'No reduction rule was found on product '
                '%(product)s',
                'invalid_date': 'Impossible to reduce the contract before the '
                'contract\'s start_date (%(start_date)s)',
                })

    def default_parameters(self, name):
        if self.parameters._default_values:
            return self.parameters._default_values
        assert Transaction().context.get('active_model') == 'contract'
        contract = Pool().get('contract')(
            Transaction().context.get('active_id'))
        if not contract.can_reduce:
            contract.raise_user_error('cannot_reduce', {
                    'contract': contract.rec_name})
        return {
            'contract': contract.id,
            }

    def transition_calculate(self):
        self.check_parameters()
        self.calculate_reduction()
        return 'preview'

    def check_parameters(self):
        if (self.parameters.contract.start_date >=
                self.parameters.reduction_date):
            self.raise_user_error('invalid_date', {
                    'start_date': self.parameters.contract.start_date})

    def calculate_reduction(self):
        contract = self.parameters.contract
        contract.check_for_reduction([contract],
            self.parameters.reduction_date)
        reductions = contract.calculate_reductions(
            self.parameters.reduction_date)
        self.preview.contract = contract
        self.preview.currency = contract.currency
        self.preview.currency_digits = contract.currency_digits
        self.preview.currency_symbol = contract.currency_symbol
        self.preview.reduction_value = sum([x[1] for x in reductions],
            Decimal(0))
        self.preview.reduction_date = self.parameters.reduction_date
        return 'preview'

    def default_preview(self, name):
        if self.preview._default_values:
            return self.preview._default_values
        return {}

    def transition_reduce(self):
        contract = self.parameters.contract
        contract.reduce([contract], self.parameters.reduction_date)
        return 'end'


class ReduceParameters(model.CoogView):
    'Reduction Parameters'
    __name__ = 'contract.reduce.parameters'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    reduction_date = fields.Date('Reduction Date', required=True,
        help='The date at which the contract will be reduced')


class ReducePreview(model.CoogView):
    'Reduction Preview'
    __name__ = 'contract.reduce.preview'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    currency = fields.Many2One('currency.currency', 'Currency', readonly=True)
    currency_digits = fields.Integer('Currency Digits', readonly=True)
    currency_symbol = fields.Char('Currency Symbol', readonly=True)
    reduction_value = fields.Numeric('Reduction Value',
        digits=(16, Eval('currency_digits', 2)), readonly=True,
        depends=['currency_digits'], help='The contract value after reduction')
    reduction_date = fields.Date('Reduction Date', readonly=True)


class CancelReduction(Wizard):
    'Cancel Reduction'
    __name__ = 'contract.cancel.reduction'

    start_state = 'cancel_reduction'
    cancel_reduction = StateTransition()

    def transition_cancel_reduction(self):
        assert Transaction().context.get('active_model') == 'contract'
        contract = Pool().get('contract')(
            Transaction().context.get('active_id'))
        contract.cancel_reduction([contract])
        return 'end'
