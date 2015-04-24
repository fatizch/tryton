import unittest
import trytond.tests.test_tryton
import datetime

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'account_payment_sepa_cog'

    @classmethod
    def get_models(cls):
        return {
            'PaymentJournal': 'account.payment.journal',
            'MoveLine': 'account.move.line',
            }

    def test0010_test_next_possible_payment_date(self):
        today = datetime.date.today()
        year = today.year + 1
        payment_journal = self.PaymentJournal()
        payment_journal.process_method = 'sepa'
        payment_journal.last_sepa_receivable_payment_creation_date = \
            datetime.date(year, 01, 01)

        line = self.MoveLine()
        line.maturity_date = datetime.date(year, 01, 01)
        payment_date = payment_journal.get_next_possible_payment_date(line, 5)
        self.assertEqual(payment_date, datetime.date(year, 01, 05))

        payment_journal.last_sepa_receivable_payment_creation_date = \
            datetime.date(year, 01, 05)
        payment_date = payment_journal.get_next_possible_payment_date(line, 5)
        self.assertEqual(payment_date, datetime.date(year, 02, 05))

        payment_journal.last_sepa_receivable_payment_creation_date = \
            datetime.date(year, 04, 06)
        payment_date = payment_journal.get_next_possible_payment_date(line, 5)
        self.assertEqual(payment_date, datetime.date(year, 05, 05))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
