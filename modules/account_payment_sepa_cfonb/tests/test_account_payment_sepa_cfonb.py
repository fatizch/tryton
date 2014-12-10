# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
from itertools import chain

import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_depends
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction

from trytond.modules.account_payment_sepa.tests.test_account_payment_sepa \
    import validate_file


class AccountPaymentSepaCFONBTestCase(unittest.TestCase):
    'Test Account Payment SEPA CFONB module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('account_payment_sepa_cfonb')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test_pain008_001_02_cfonb(self):
        'Test pain.008.001.02-cfonb xsd validation'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            validate_file('pain.008.001.02-cfonb', 'receivable',
                xsd='pain.008.001.02')


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    from trytond.modules.account.tests import test_account
    for test in chain(test_company.suite(), test_account.suite()):
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AccountPaymentSepaCFONBTestCase))
    return suite
