# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.modules.currency.tests import create_currency


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'account_invoice_cog'

    @classmethod
    def get_models(cls):
        return {
            'PaymentTerm': 'account.invoice.payment_term',
            }

    def test_payment_term(self):
        'Test payment_term'
        cu1 = create_currency('cu1')
        term, = self.PaymentTerm.create([{
                    'name': 'End of quarter + 1 month',
                    'lines': [
                        ('create', [{
                                    'sequence': 1,
                                    'type': 'remainder',
                                    'relativedeltas': [('create', [{
                                                    'months': 1,
                                                    'quarter': True,
                                                    'day': 30,
                                                    },
                                                ]),
                                        ],
                                    }])]
                    }])
        amount = Decimal('1000')
        # End of quarter + 1 month
        for m in range(1, 10):
            terms = term.compute(amount, cu1, date=datetime.date(2011, m, 15))
            self.assertEqual(terms,
                [(datetime.date(2011, (m - 1) // 3 * 3 + 4, 30), amount), ])

        for m in range(10, 13):
            terms = term.compute(amount, cu1, date=datetime.date(2011, m, 15))
            self.assertEqual(terms, [(datetime.date(2012, 1, 30), amount), ])

        # End of quarter
        term.lines[0].relativedeltas[0].months = 0
        for m in range(1, 13):
            terms = term.compute(amount, cu1, date=datetime.date(2011, m, 15))
            self.assertEqual(terms,
                [(datetime.date(2011, (m - 1) // 3 * 3 + 3, 30), amount), ])

        # Beginning of quarter
        term.lines[0].relativedeltas[0].months = -2
        for m in range(1, 13):
            terms = term.compute(amount, cu1, date=datetime.date(2011, m, 15))
            self.assertEqual(terms,
                [(datetime.date(2011, (m - 1) // 3 * 3 + 1, 30), amount), ])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
