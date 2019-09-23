import unittest
import datetime
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.pool import Pool


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'party_employment'

    def test0001_testEmploymentKindCreation(self):
        EmploymentKind = Pool().get('party.employment_kind')
        EmploymentKind(code='test', name='Test').save()

    @test_framework.prepare_test('party_employment.'
        'test0001_testEmploymentKindCreation')
    def test0060_party_API(self):
        pool = Pool()
        Party = pool.get('party.party')
        APIParty = pool.get('api.party')
        example_party_employment = APIParty._create_party_examples()[-1]
        result = APIParty.create_party(
            example_party_employment['input'], {})

        daizy, = Party.search([('name', '=', 'Doe'),
            ('first_name', '=', 'Daisy')])
        self.assertEqual(result['parties'], [
            {'ref': '5', 'id': daizy.id}])
        self.assertEqual(daizy.employments[0].entry_date,
            datetime.date(2012, 5, 5))
        self.assertEqual(daizy.employments[0].employment_kind.code, 'test')
        self.assertEqual(daizy.employments[0].versions[0].date,
            datetime.date(2012, 5, 5))
        self.assertEqual(daizy.employments[0].versions[0].gross_salary,
            Decimal('10000'))
        employe_update = {
            'parties': [{
                'ref': '5',
                'is_person': True,
                'name': 'Doe',
                'first_name': 'Daisy',
                'birth_date': '1974-06-10',
                'gender': 'female',
                'employments': [{
                    'entry_date': '2019-01-01',
                    'employment_kind': 'test',
                    'gross_salary': '20000',
                    }, {
                    'entry_date': '2023-02-02',
                    'employment_kind': 'test',
                    'gross_salary': '40000',
                    },

                ]
                },
                ],
            }
        result = APIParty.create_party(employe_update,
            {'_debug_server': True})
        test_update, = Party.search([('name', '=', 'Doe'),
            ('first_name', '=', 'Daisy')])
        self.assertEqual(test_update.employments[0].entry_date,
            datetime.date(2019, 1, 1))
        self.assertEqual(result['parties'], [
            {'ref': '5', 'id': test_update.id}])
        self.assertEqual(test_update.employments[0].versions[0].gross_salary,
            Decimal('20000'))

        self.assertEqual(test_update.employments[0].employment_kind.code,
            'test')

        self.assertEqual(test_update.employments[1].entry_date,
            datetime.date(2023, 2, 2))
        self.assertEqual(test_update.employments[1].versions[0].gross_salary,
            Decimal('40000'))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
