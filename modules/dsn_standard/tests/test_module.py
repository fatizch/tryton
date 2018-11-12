# encoding: utf8
import unittest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.modules.dsn_standard import dsn

from trytond.config import config
from trytond.modules.coog_core import utils
from trytond.modules import get_module_info


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'dsn_standard'

    @classmethod
    def get_models(cls):
        return {
            'Party': 'party.party',
            'Address': 'party.address',
            'Country': 'country.country',
            }

    def test_validate(self):
        D = dsn.NEODeSTemplate(None)
        bad_iban = dsn.Entry(u'S21.G00.20.004', u'tééé')
        good_iban = dsn.Entry(u'S21.G00.20.004',
            u'64G1DFR14DRF514GDF54GD')

        D.message = [good_iban]
        self.assertTrue(D.validate)
        D.message.append(bad_iban)
        self.assertRaises(dsn.DSNValidationError, D.validate)

    def test_generate(self):
        sender = self.Party()
        sender.is_person = False
        sender.name = 'Corp'
        sender.code = 'a_dsn_sender'
        sender.siren = '379158322'
        sender.save()

        country = self.Country(name="Oz", code='OZ')
        country.save()
        address = self.Address(party=sender, zip="1", country=country,
            city="Emerald", street='2 Common Street')
        address.save()
        sender.addresses = [address.id]
        sender.save()

        config.add_section('dsn')
        config.set('dsn', 'sender_code', 'a_dsn_sender')
        config.set('dsn', 'sender_nic', '123')
        config.set('dsn', 'sender_contact_civility', '01')
        config.set('dsn', 'sender_contact_full_name', 'Joe Doe')
        config.set('dsn', 'sender_contact_email', 'joe@corp.com')
        config.set('dsn', 'sender_contact_phone', '0101010101')

        D = dsn.NEODeSTemplate(None)
        s = D.generate()
        version = get_module_info('dsn_standard').get('version')
        expected_file = '\n'.join([
            u"S10.G00.00.001,'Coog'",
            u"S10.G00.00.002,'Coopengo'",
            u"S10.G00.00.003,'%s'" % version,
            u"S10.G00.00.005,'02'",
            u"S10.G00.00.006,'20176'",
            u"S10.G00.00.008,'01'",
            u"S10.G00.01.001,'379158322'",
            u"S10.G00.01.002,'123'",
            u"S10.G00.01.003,'Corp'",
            u"S10.G00.01.004,'2 Common Street'",
            u"S10.G00.01.005,'1'",
            u"S10.G00.01.006,'Emerald'",
            u"S10.G00.01.007,'OZ'",
            u"S10.G00.02.001,'01'",
            u"S10.G00.02.002,'Joe Doe'",
            u"S10.G00.02.004,'joe@corp.com'",
            u"S10.G00.02.005,'0101010101'",
            u"S20.G00.05.001,'21'",
            u"S20.G00.05.002,'01'",
            u"S20.G00.05.003,'23'",
            u"S20.G00.05.004,'24'",
            u"S20.G00.05.005,'%s'" % utils.today().strftime('01%m%Y'),
            u"S20.G00.05.007,'%s'" % utils.today().strftime('%d%m%Y'),
            u"S20.G00.05.010,'01'",
            u"S90.G00.90.001,'26'",
            u"S90.G00.90.002,'1'"
        ])

        for line, expected in zip(s.split('\n'), expected_file.split('\n')):
            self.assertEqual(line, expected)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
