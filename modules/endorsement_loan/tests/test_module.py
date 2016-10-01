# encoding: utf-8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import unittest
import doctest
import datetime

import trytond.tests.test_tryton
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.transaction import Transaction

from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'endorsement_loan'

    @classmethod
    def get_models(cls):
        return {
            'EndorsementLoan': 'endorsement.loan',
            'EndorsementLoanField': 'endorsement.loan.field',
            'LoanIncrement': 'loan.increment',
            'LoanPayment': 'loan.payment',
            }

    @classmethod
    def depending_modules(cls):
        return ['loan', 'endorsement']

    def get_loan(self):
        return self.Loan.search([
                ('kind', '=', 'fixed_rate'),
                ('rate', '=', Decimal('0.0752')),
                ('funds_release_date', '=', datetime.date(2014, 3, 5)),
                ('amount', '=', Decimal('134566')),
                ])[0]

    @test_framework.prepare_test('endorsement.test0001_check_possible_views')
    def test0010_create_loan_endorsement_part(self):
        endorsement_part = self.EndorsementPart()
        endorsement_part.name = 'Change Loan Amount'
        endorsement_part.code = endorsement_part.on_change_with_code()
        endorsement_part.view = 'simple_contract_modification'
        endorsement_part.kind = 'loan'
        endorsement_part.loan_fields = [
            {
                'field': self.Field.search([
                        ('model.model', '=', 'loan'),
                        ('name', '=', 'amount')])[0],
            },
            {
                'field': self.Field.search([
                        ('model.model', '=', 'loan'),
                        ('name', '=', 'kind')])[0],
            },
            {
                'field': self.Field.search([
                        ('model.model', '=', 'loan'),
                        ('name', '=', 'payment_frequency')])[0],
            },
            {
                'field': self.Field.search([
                        ('model.model', '=', 'loan'),
                        ('name', '=', 'rate')])[0],
            },
            ]

        self.assertEqual(endorsement_part.code,
            'change_loan_amount')
        endorsement_part.save()

    @test_framework.prepare_test(
        'endorsement_loan.test0010_create_loan_endorsement_part',
        )
    def test0020_create_endorsement_definition(self):
        endorsement_part, = self.EndorsementPart.search([
                ('code', '=', 'change_loan_amount'),
                ])
        definition = self.EndorsementDefinition()
        definition.name = 'Change Loan Amount'
        definition.code = definition.on_change_with_code()
        definition.ordered_endorsement_parts = [{
                'endorsement_part': endorsement_part.id,
                'order': 1,
                }]
        self.assertEqual(definition.code, 'change_loan_amount')
        definition.save()
        self.assertEqual(list(definition.endorsement_parts),
            [endorsement_part])

    @test_framework.prepare_test(
        'endorsement_loan.test0020_create_endorsement_definition',
        'loan.test0037loan_creation',
        )
    def test0030_create_endorsement(self):
        definition, = self.EndorsementDefinition.search([
                ('code', '=', 'change_loan_amount'),
                ])
        loan = self.get_loan()
        effective_date = loan.funds_release_date + datetime.timedelta(
            days=200)
        previous_amount = loan.amount
        loan.amount = Decimal('150000')
        endorsement = self.Endorsement(
            definition=definition,
            effective_date=effective_date,
            loan_endorsements=[{
                    'loan': loan.id,
                    'values': {
                        'amount': Decimal('150000'),
                        },
                    }])
        loan.amount = previous_amount
        endorsement.save()
        loan_endorsement, = endorsement.loan_endorsements
        self.assertEqual(endorsement.state, 'draft')
        self.assertEqual(loan_endorsement.state, 'draft')
        self.assertEqual(loan_endorsement.definition, definition)
        self.assertEqual(list(endorsement.loans), [loan])
        self.assertEqual(loan.amount, previous_amount)
        self.assertEqual(loan_endorsement.apply_values(), {
                'amount': Decimal('150000'),
                })

    @test_framework.prepare_test(
        'endorsement_loan.test0030_create_endorsement',
        )
    def test0031_endorsement_summary(self):
        loan = self.get_loan()
        endorsement, = self.Endorsement.search([
                ('loans', '=', loan.id),
                ])
        self.assertEqual(endorsement.endorsement_summary,
            u'<div><b>Change Loan Amount</b></div>'
            u'<div><u>Loan Modifications :</u></div>'
            u'<div>    <i>Amount</i>: %s → 150000</div>' % loan.amount)

    @test_framework.prepare_test(
        'endorsement_loan.test0030_create_endorsement',
        )
    def test0040_endorsement_application(self):
        loan = self.get_loan()
        endorsement, = self.Endorsement.search([
                ('loans', '=', loan.id),
                ])
        endorsement.apply([endorsement])
        loan = endorsement.loans[0]
        new_payment = loan.payments[20].outstanding_balance
        self.assertEqual(loan.amount, Decimal('150000'))
        self.assertEqual(new_payment, Decimal('143924.46'))
        self.assertEqual(loan.payments[20].amount, Decimal('5538.33'))

    @test_framework.prepare_test(
        'endorsement_loan.test0030_create_endorsement',
        )
    def test0099_revert_endorsement(self):
        # Note: test pass only with a database configured as postgresql
        # WARNING: No dependency, commit required for the history / write dates
        # to kick in properly
        Transaction().commit()

        loan = self.get_loan()
        endorsement, = self.Endorsement.search([
                ('loans', '=', loan.id),
                ])
        previous_loan_amount = loan.amount
        endorsement.apply([endorsement])
        Transaction().commit()

        loan = endorsement.loans[0]
        loan_endorsement, = endorsement.loan_endorsements
        self.assert_(endorsement.application_date)
        self.assertEqual(endorsement.state, 'applied')
        self.assertEqual(loan_endorsement.state, 'applied')
        self.assertEqual(loan.amount, Decimal('150000'))
        self.assertEqual(loan_endorsement.base_instance.amount,
            previous_loan_amount)
        self.assert_(endorsement.rollback_date)
        endorsement.cancel([endorsement])
        Transaction().commit()

        loan = endorsement.loans[0]
        self.assertEqual(loan_endorsement.state, 'canceled')
        self.assertEqual(loan.amount, previous_loan_amount)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_endorsement_loan.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
