# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import unittest
import trytond.tests.test_tryton
import datetime
from io import BytesIO

from mock import Mock

from trytond.modules.coog_core import test_framework
from trytond.modules.account_payment_sepa_cog.payment import CAMT054Coog


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'account_payment_sepa_cog'

    @classmethod
    def get_models(cls):
        return {
            'PaymentJournal': 'account.payment.journal',
            'MoveLine': 'account.move.line',
            'Message': 'account.payment.sepa.message',
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

    def handle_camt054(self, flavor):
        'Handle camt.054'
        message_file = os.path.join(os.path.dirname(__file__),
            '%s.xml' % flavor)
        message = open(message_file).read()
        namespace = self.Message().get_namespace(message)
        self.assertEqual(namespace,
            'urn:iso:std:iso:20022:tech:xsd:%s' % flavor)

        payment = Mock()
        Payment = Mock()
        Payment.search.return_value = [payment]

        handler = CAMT054Coog(BytesIO(message), Payment)

        self.assertEqual(handler.msg_id, 'AAAASESS-FP-00001')
        Payment.search.assert_called_with([
                ('sepa_end_to_end_id', '=', 'MUELL/FINP/RA12345'),
                ('kind', '=', 'receivable'),
                ])

        self.assertEqual(payment.sepa_return_reason_code, 'AM04')
        self.assertEqual(payment.sepa_bank_reject_date,
            datetime.date(2010, 10, 18))
        Payment.save.assert_called_with([payment])
        Payment.fail.assert_called_with([payment])

    def test_camt054_001_02(self):
        'Test camt.054.001.02 handling'
        self.handle_camt054('camt.054.001.02')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
