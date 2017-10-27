# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, Button
from trytond.pyson import Eval
from trytond.modules.coog_core import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'LoanShare',
    'AveragePremiumRateLoanDisplayer',
    'DisplayLoanAveragePremiumValues',
    'DisplayLoanAveragePremium',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_loan_average_premium': {
                    'invisible': ~Eval('is_loan'),
                    },
                })

    def calculate_premium_aggregates(self, start=None, end=None):
        futures = self.get_future_invoices(self, start, end)
        per_contract_entity = defaultdict(
            lambda: defaultdict(lambda: Decimal(0)))
        per_offered_entity = defaultdict(
            lambda: defaultdict(lambda: Decimal(0)))

        for invoice in futures:
            for line in invoice['details']:
                if (line['start'] > (end or datetime.date.max) or
                        line['end'] < (start or datetime.date.min)):
                    continue
                premium = line['premium']
                per_contract_entity[
                    (premium.parent.__name__, premium.parent.id)][
                    premium.loan.id if premium.loan else None] += \
                    line['total_amount']
                per_offered_entity[
                    (premium.rated_entity.__name__, premium.rated_entity.id)][
                    premium.loan.id if premium.loan else None] += \
                    line['total_amount']
        return per_contract_entity, per_offered_entity

    def extract_premium(self, kind, start=None, end=None, value=None,
            model_name='', loan=None):
        # Returns a dictionnary which represents aggregates on future invoices
        # based on the model_name, a given parent, or per offered entity
        assert kind in ('offered', 'contract')
        per_contract_entity, per_offered_entity = \
            self.calculate_premium_aggregates(start, end)
        values = {}
        if kind == 'offered':
            values = per_offered_entity
        elif kind == 'contract':
            values = per_contract_entity
        if value:
            good_dict = values[(value.__name__, value.id)]
            if loan:
                return good_dict[loan.id]
            return sum(good_dict.values())
        if model_name:
            result = sum([self.extract_premium(kind, start, end, values=k,
                        loan=loan)
                    for k in values.iterkeys() if k[0] == model_name])
            return result
        return values

    @classmethod
    @model.CoogView.button_action(
        'loan_apr.act_loan_average_premium_display')
    def button_loan_average_premium(cls, contracts):
        pass


class LoanShare:
    __name__ = 'loan.share'

    average_premium_rate = fields.Function(
        fields.Numeric('Average Premium Rate', digits=(6, 4)),
        'get_average_premium_rate')
    base_premium_amount = fields.Function(
        fields.Numeric('Base Premium Amount', digits=(16, 2)),
        'get_average_premium_rate')

    @classmethod
    def get_average_premium_rate(cls, shares, names):
        field_values = {'average_premium_rate': {}, 'base_premium_amount': {}}
        for share in shares:
            contract = share.option.covered_element.contract
            rule = contract.product.average_loan_premium_rule
            vals = rule.calculate_average_premium_for_option(contract, share)
            field_values['base_premium_amount'][share.id] = vals[0] or 0
            field_values['average_premium_rate'][share.id] = vals[1] or 0
        return field_values


class DisplayLoanAveragePremium(Wizard):
    'Display Loan Average Premium'

    __name__ = 'loan.average_premium_rate.display'

    start_state = 'display_loans'
    display_loans = StateView('loan.average_premium_rate.display.values',
        'loan_apr.display_average_premium_values_view_form', [
            Button('Cancel', 'end', 'tryton-cancel')])

    def default_display_loans(self, name):
        if not Transaction().context.get('active_model') == 'contract':
            return {}
        contract_id = Transaction().context.get('active_id', None)
        if contract_id is None:
            return {}
        contract = Pool().get('contract')(contract_id)
        with Transaction().set_context(contract=contract_id):
            return {'loan_displayers': [{
                        'name': x.rec_name,
                        'average_premium_rate': x.average_premium_rate,
                        'base_premium_amount': x.base_premium_amount,
                        'currency_digits': x.currency_digits,
                        'currency_symbol': x.currency_symbol,
                        'current_loan_shares': [{
                                'name': y.option.rec_name,
                                'average_premium_rate': y.average_premium_rate,
                                'base_premium_amount': y.base_premium_amount,
                                'currency_digits': x.currency_digits,
                                'currency_symbol': x.currency_symbol,
                                'current_loan_shares': [],
                                } for y in x.current_loan_shares],
                        } for x in contract.used_loans],
                }


class DisplayLoanAveragePremiumValues(model.CoogView):
    'Display Loan Average Premium Values'

    __name__ = 'loan.average_premium_rate.display.values'

    loan_displayers = fields.One2Many(
        'loan.average_premium_rate.loan_displayer', None, 'Loans',
        readonly=True)


class AveragePremiumRateLoanDisplayer(model.CoogView):
    'Average Premium Rate Loan Displayer'

    __name__ = 'loan.average_premium_rate.loan_displayer'

    average_premium_rate = fields.Numeric('Average Premium Rate',
        digits=(6, 4))
    base_premium_amount = fields.Numeric('Base Premium Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits')
    current_loan_shares = fields.One2Many(
        'loan.average_premium_rate.loan_displayer', None,
        'Current Loan Shares')
    currency_symbol = fields.Char('Currency Symbol')
    name = fields.Char('Name')
