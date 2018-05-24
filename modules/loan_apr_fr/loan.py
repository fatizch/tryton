# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import math
from collections import defaultdict
from decimal import Decimal

from trytond.rpc import RPC
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, coog_date


__all__ = [
    'Loan',
    ]


def find_dec_root(func, x, step, tol):
    '''
        Basic naive function root calculation (dicot)
        It supposes that function is decreasing
        Implementation could be a subject of improvements
    '''
    fx = func(x)
    if math.fabs(fx) <= tol:
        return x

    if fx > 0:
        x_min, fx_min = x, fx
        while True:
            x += step
            fx = func(x)
            assert fx <= fx_min
            if fx > 0:
                x_min, fx_min = x, fx
            elif fx == 0:
                x_min, x_max, fx_min, fx_max = x, x, fx, fx
                break
            else:
                x_max, fx_max = x, fx
                break
    else:  # fx assumed to be < 0 since |fx| > tol
        x_max, fx_max = x, fx
        while True:
            x -= step
            fx = func(x)
            assert fx >= fx_max
            if fx < 0:
                x_max, fx_max = x, fx
            elif fx == 0:
                x_min, x_max, fx_min, fx_max = x, x, fx, fx
                break
            else:
                x_min, fx_min = x, fx
                break

    if (x_min != x_max):
        pivot = x_min + ((x_max - x_min) * (fx_min / (fx_min - fx_max)))
    else:
        pivot = x_min

    return find_dec_root(func, pivot, step / 5, tol)


class Loan:
    __metaclass__ = PoolMeta
    __name__ = 'loan'

    taea = fields.Function(
        fields.Numeric('TAEA', digits=(6, 4)),
        'get_taea')
    bank_fees = fields.Numeric('Bank Fees', depends=['currency_digits'],
        digits=(16, Eval('currency_digits', 2)))

    @classmethod
    def __setup__(cls):
        super(Loan, cls).__setup__()
        cls.__rpc__.update({
                'calculate_taea': RPC(instantiate=0),
                })

    @classmethod
    def default_bank_fees(cls):
        return 0

    def get_taea(self, name):
        pool = Pool()
        contract_id = Transaction().context.get('contract', None)
        if contract_id:
            contract = pool.get('contract')(contract_id)
        else:
            return 0

        Fee = pool.get('account.fee')

        rule = contract.product.average_loan_premium_rule
        premiums = contract.calculate_premium_per_loan()
        ratios = contract.get_used_loans_ratios()[self.id]
        ratios['do_not_use'] = 0

        rule_fees = dict([(x.fee, x.action) for x in rule.fee_rules])
        fee_ratios = {}
        for fee_id, data_dict in premiums['fee_totals'].iteritems():
            action = rule_fees.get(Fee(fee_id), rule.default_fee_action)
            fee_ratios[fee_id] = ratios[action]

        # TODO : Use increments to properly populate the list
        capitals = [(0, self.amount)]

        payment_dict = defaultdict(lambda: {
                'nb_years': None, 'payment_amount': 0, 'insurance_amount': 0})
        for premium_data in premiums['per_period']:
            if premium_data['loan'] != self.id and not fee_ratios.get(
                    premium_data['fee'], 0):
                continue
            cur_payment = payment_dict[premium_data['period_start']]
            if cur_payment['nb_years'] is None:
                cur_payment['nb_years'] = coog_date.number_of_years_between(
                    self.funds_release_date, premium_data['period_start'],
                    prorata_method=coog_date.prorata_exact)
            if premium_data['loan']:
                cur_payment['insurance_amount'] += premium_data['amount']
                cur_payment['insurance_amount'] += premium_data['tax']
            else:
                cur_payment['insurance_amount'] += (premium_data['amount'] +
                    premium_data['tax']) * fee_ratios[premium_data['fee']]

        for payment in self.payments:
            if not payment.amount:
                continue
            cur_payment = payment_dict[payment.start_date]
            if cur_payment['nb_years'] is None:
                cur_payment['nb_years'] = coog_date.number_of_years_between(
                    self.funds_release_date, payment.start_date,
                    prorata_method=coog_date.prorata_exact)
            cur_payment['payment_amount'] += payment.amount

        payments = [payment_dict[x] for x in sorted(payment_dict.keys())]
        payments[0]['payment_amount'] += self.bank_fees or Decimal('0.0')

        return self.calculate_taea(capitals, payments)

    def calculate_taea(self, capitals, payments):
        base_apr = self._calculate_annual_percentage_rate(capitals, [
                [x['nb_years'], x['payment_amount']] for x in payments
                if x['payment_amount']])
        insurance_apr = self._calculate_annual_percentage_rate(capitals, [
                [x['nb_years'], x['payment_amount'] + x['insurance_amount']]
                for x in payments
                if x['payment_amount'] or x['insurance_amount']])
        return insurance_apr - base_apr

    @classmethod
    def _calculate_annual_percentage_rate(cls, capitals, payments):
        '''
            Calculate TAEG
            http://en.wikipedia.org/wiki/Annual_percentage_rate#European_Union
        '''

        def fx(x):
            result = 0.0
            for nb_year, amount in payments:
                result += float(amount) / ((1 + x) ** float(nb_year))
            for nb_year, capital in capitals:
                result -= float(capital) / ((1 + x) ** float(nb_year))
            return result

        return Decimal(find_dec_root(fx, 0.1, 0.02, 1e-7))
