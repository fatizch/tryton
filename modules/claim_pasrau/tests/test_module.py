# encoding: utf8
import unittest
import datetime

from decimal import Decimal

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.modules.dsn_standard import dsn
from trytond.modules.claim_pasrau import dsn as pasrau_dsn
import os


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'claim_pasrau'

    ssn1 = '180104161674907'
    ssn2 = '180106741921625'
    ssn3 = '180104807063318'
    effective_date = datetime.date.today()

    @classmethod
    def fetch_models_for(cls):
        return ['dsn_standard']

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Address': 'party.address',
            'Country': 'country.country',
            'PartyCustomPasrauRate': 'party.pasrau.rate',
            'DefaultPasrauRate': 'claim.pasrau.default.rate',
        }

    def test_neorau_validate(self):
        D = pasrau_dsn.NEORAUTemplate(None, void=True, replace=True)

        bad_iban = dsn.Entry(u'S21.G00.20.004', u'tééé')
        good_iban = dsn.Entry(u'S21.G00.20.004',
            u'64G1DFR14DRF514GDF54GD')

        D.message = [good_iban]
        self.assertTrue(D.validate)
        D.message.append(bad_iban)
        self.assertRaises(dsn.DSNValidationError, D.validate)

    def test0001_test_pasrau_files(self):
        Party = self.Party
        PartyCustomPasrauRate = self.PartyCustomPasrauRate

        person1 = Party(name=u'doe', first_name=u'joe', ssn=self.ssn1)
        person1.save()
        person2 = Party(name=u'doe', first_name=u'jane', ssn=self.ssn2)
        person2.save()
        person3 = Party(name=u'dane', first_name=u'jane', ssn=self.ssn3)
        person3.save()

        dir_path = os.path.dirname(os.path.realpath(__file__))
        file1 = os.path.join(dir_path, 'pasrau-crm.xml')
        file2 = os.path.join(dir_path, 'pasrau-crm-multi.xml')

        self.assertTrue(PartyCustomPasrauRate.process_xml_file(file1))
        self.assertTrue(PartyCustomPasrauRate.process_xml_file(file2))

        created_rates = PartyCustomPasrauRate.search([])
        self.assertEqual(len(created_rates), 3)
        effective_date = self.effective_date
        for rate in created_rates:
            if rate.party.ssn == self.ssn1:
                self.assertEqual(rate.effective_date, effective_date)
                self.assertEqual(rate.pasrau_tax_rate, Decimal('0.14'))
                self.assertEqual(rate.origin, 'default')
                self.assertEqual(rate.business_id, 'NOVEMBRE-2019')
            elif rate.party.ssn == self.ssn2:
                self.assertEqual(rate.effective_date, effective_date)
                self.assertEqual(rate.pasrau_tax_rate, Decimal('0.02'))
                self.assertEqual(rate.origin, 'default')
                self.assertEqual(rate.business_id, 'NOVEMBRE-2019')
            elif rate.party.ssn == self.ssn3:
                self.assertEqual(rate.effective_date, effective_date)
                self.assertEqual(rate.pasrau_tax_rate, Decimal('0.14'))
                self.assertEqual(rate.origin, 'default')
                self.assertEqual(rate.business_id, 'DECEMBRE-2019')

    @test_framework.prepare_test(
        'claim_pasrau.test0001_test_pasrau_files'
        )
    def test0002_get_appliable_pasrau_rate(self):
        joe, = self.Party.search([('ssn', '=', self.ssn1)])
        country = self.Country(name='Oz', code='OZ')
        country.save()
        joe_address = self.Address(party=joe, zip='75001', country=country,
            city='Emerald')
        joe_address.save()
        self.assertEqual(
            joe.get_appliable_pasrau_rate(None, self.effective_date, None,
                self.effective_date),
            Decimal('0.14'))

        new_rate_value = Decimal('0.12')
        new_rate = joe.update_pasrau_rate(
            self.effective_date, new_rate_value)
        new_rate.save()
        self.assertEqual(
            joe.get_appliable_pasrau_rate(None, self.effective_date, None,
                self.effective_date),
            new_rate_value)

    def test0003_get_appliable_default_pasrau_rate(self):
        DefaultRate = self.DefaultPasrauRate
        PersoRate = self.PartyCustomPasrauRate
        d = datetime.date

        assert len(PersoRate.search([])) == 0

        def test_default_rate(data, expected):
            res = DefaultRate.get_appliable_default_pasrau_rate(*data)
            self.assertEqual(res, expected, 'Test With Values: %s\n'
                'Expected: %s, Got: %s' % (str(data), expected, res))

        # we rely on 2019 data created by xml
        # reference is https://www.net-entreprises.fr/wp-content/uploads/
        # 2017/09/PASRAU_Note-bareme-par-defaut.pdf
        for values, expected in [
            (
                # full month, this is in reference dodcument
                ('75001', Decimal('500'), d(2019, 1, 1), d(2019, 1, 31),
                    d(2019, 1, 1)),
                Decimal('0')
            ),
            (
                # full month, this is in reference dodcument
                ('75001', Decimal('1420'), d(2019, 1, 1), d(2019, 1, 31),
                    d(2019, 1, 1)),
                Decimal('0.015')
            ),
            (
                # full month, this is in reference dodcument
                ('75001', Decimal('46502'), d(2019, 1, 1), d(2019, 1, 31),
                    d(2019, 1, 1)),
                Decimal('0.43')
            ),
            (   # full trimester, also in reference document
                ('75001', Decimal('4104'), d(2019, 1, 1), d(2019, 3, 31),
                    d(2019, 1, 1)),
                Decimal('0.005')
            ),
            (   # one day, also in reference document
                ('75001', Decimal('55'), d(2019, 1, 1), d(2019, 1, 1),
                    d(2019, 1, 1)),
                Decimal('0.015')
            ),
            (   # three days, also in reference document
                ('75001', Decimal('53.14') * 3, d(2019, 1, 1),
                    d(2019, 1, 3), d(2019, 1, 1)),
                Decimal('0.005')
            ),
            (
                # 113 days
                # this case is not explained in reference document.
                # the current rules gets us a coeff of 3.76 and a rate of 0.025
                # but, if we used for example, a coeff of (nb_days / 26.0),
                # we'll get a coeff of 4.3  and a rate of 0.005
                ('75001', Decimal('5948.32'), d(2019, 10, 9), d(2020, 1, 28),
                    d(2019, 10, 9)),
                Decimal('0.025')
            ),
                ]:
            test_default_rate(values, expected=expected)

    def test0004_get_region(self):
        DefaultRate = self.DefaultPasrauRate
        self.assertEqual(DefaultRate.get_region('75001'), 'metropolitan')
        self.assertEqual(DefaultRate.get_region('95001'), 'metropolitan')
        self.assertEqual(DefaultRate.get_region('97120'), 'grm')
        self.assertEqual(DefaultRate.get_region('97300'), 'gm')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
