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
from trytond.exceptions import UserError


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
            'Mandate': 'account.payment.sepa.mandate',
            'Party': 'party.party',
            'BankAccount': 'bank.account',
            'Group': 'account.payment.group',
            'Journal': 'account.payment.journal',
            }

    @classmethod
    def depending_modules(cls):
        return ['bank_cog', 'company_cog']

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

    @test_framework.prepare_test(
        'company_cog.test0001_testCompanyCreation',
        'bank_cog.test0020bankaccount')
    def test_mandate_validation(self):
        account, = self.BankAccount.search([], limit=1)
        party, = self.Party.search([], limit=1)
        company, = self.Company().search([], limit=1)
        mandate = self.Mandate(party=party, company=company,
            account_number=account.numbers[0], identification='001',
            type='recurrent', scheme='CORE',
            signature_date=datetime.date(2011, 1, 1))
        mandate.save()
        with self.assertRaises(UserError):
            # Amendment without start_date
            mandate2 = self.Mandate(party=party, company=company,
                account_number=account.numbers[0], identification='001',
                type='recurrent', scheme='CORE',
                signature_date=datetime.date(2011, 1, 1),
                amendment_of=mandate)
            mandate2.save()
        mandate2 = self.Mandate(party=party, company=company,
            account_number=account.numbers[0], identification='001',
            type='recurrent', scheme='CORE',
            signature_date=datetime.date(2011, 1, 1),
            amendment_of=mandate,
            start_date=datetime.date(2010, 1, 1))
        mandate2.save()
        with self.assertRaises(UserError):
            # Same identification, different origin
            mandate3 = self.Mandate(party=party, company=company,
                account_number=account.numbers[0], identification='001',
                type='recurrent', scheme='CORE',
                signature_date=datetime.date(2011, 1, 1))
            mandate3.save()
        with self.assertRaises(UserError):
            # Amendment with same start date
            mandate4 = self.Mandate(party=party, company=company,
                account_number=account.numbers[0], identification='001',
                type='recurrent', scheme='CORE',
                signature_date=datetime.date(2011, 1, 1),
                amendment_of=mandate2,
                start_date=datetime.date(2010, 1, 1))
            mandate4.save()

    def test_get_sepa_template(self):
        flavors = ['base', 'base.003', 'pain.001.001.03', 'pain.001.001.05',
            'pain.001.003.03', 'pain.008.001.02',
            'pain.008.001.04', 'pain.008.003.02']
        for flavor in flavors:
            self.Group(kind='receivable', journal=self.Journal(
                    sepa_receivable_flavor=flavor)
            ).get_sepa_template()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
