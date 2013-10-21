#-*- coding:utf-8 -*-
import sys
import os
from datetime import date
from decimal import Decimal

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction

DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

MODULE_NAME = os.path.basename(os.path.abspath(
        os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(unittest.TestCase):
    '''
    Test Coop module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module(MODULE_NAME)
        self.Loan = POOL.get('loan.loan')
        self.Currency = POOL.get('currency.currency')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view(MODULE_NAME)

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010loan_basic_data(self):
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            currency, = self.Currency.create([{
                        'name': 'Euro',
                        'code': 'EUR',
                        'symbol': u'€',
            }])
            transaction.cursor.commit()

    def assert_payment(self, loan, at_date, number, begin_balance, amount,
            principal, interest, end_balance):
        payment = loan.get_payment(at_date)
        self.assert_(payment)
        self.assert_(payment.number == number)
        self.assert_(loan.currency.is_zero(
                payment.begin_balance - begin_balance))
        self.assert_(loan.currency.is_zero(payment.amount - amount))
        self.assert_(loan.currency.is_zero(payment.principal - principal))
        self.assert_(loan.currency.is_zero(payment.interest - interest))
        self.assert_(loan.currency.is_zero(
                payment.end_balance - end_balance))

    def test0020loan_creation(self):
        '''
        Test basic loan
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            currency, = self.Currency.search([], limit=1)
            loan = self.Loan()
            loan.kind = 'fixed_rate'
            loan.rate = Decimal(0.04)
            loan.funds_release_date = date(2012, 7, 1)
            loan.first_payment_date = date(2012, 7, 15)
            loan.payment_frequency = 'month'
            loan.amount = 100000
            loan.number_of_payments = 180
            loan.currency = currency
            loan.payment_amount = loan.on_change_with_payment_amount()
            self.assert_(
                currency.is_zero(loan.payment_amount - Decimal(739.69)))

            loan.calculate_increments('partially', 12)
            self.assert_(len(loan.increments) == 2)
            increment_1 = loan.get_increment(loan.first_payment_date)
            self.assert_(increment_1)
            self.assert_(increment_1.defferal == 'partially')
            self.assert_(increment_1.number_of_payments == 12)
            self.assert_(
                currency.is_zero(increment_1.payment_amount - Decimal(333.33)))
            increment_2 = loan.get_increment(date(2013, 7, 15))
            self.assert_(increment_2)
            self.assert_(
                currency.is_zero(increment_2.payment_amount - Decimal(778.35)))

            loan.early_payments = []
            loan.payments = loan.calculate_payments()
            self.assert_(len(loan.payments) == loan.number_of_payments)

            self.assert_payment(loan, date(2013, 7, 14), 12, loan.amount,
                Decimal(333.33), Decimal(0.0), Decimal(333.33), loan.amount)

            self.assert_payment(loan, date(2013, 7, 15), 13, loan.amount,
                Decimal(778.35), Decimal(445.02), Decimal(333.33),
                Decimal(99554.98))

            self.assert_payment(loan, date(2021, 1, 15), 103,
                Decimal(53381.95), Decimal(778.35), Decimal(600.41),
                Decimal(177.94), Decimal(52781.54))

            self.assert_payment(loan, date(2027, 6, 15), 180,
                Decimal(774.70), Decimal(777.28), Decimal(774.70),
                Decimal(2.58), Decimal(0.0))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
