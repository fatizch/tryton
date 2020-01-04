import unittest

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.pool import Pool


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'party_public_employment'

    @test_framework.prepare_test('party_employment.'
        'test0001_testEmploymentKindCreation')
    def test0060_party_API(self):
        pool = Pool()
        Party = pool.get('party.party')
        APIParty = pool.get('api.party')
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')
        fr = Country(name='France', code='FR')
        fr.save()
        allier = Subdivision(name='Allier', code='FR-03', country=fr,
            type='metropolitan department')
        allier.save()
        example_party_employment = APIParty._create_party_examples()[-1]
        result = APIParty.create_party(
            example_party_employment['input'], {})
        daizy, = Party.search([('name', '=', 'Doe'),
            ('first_name', '=', 'Daisy')])

        self.assertEqual(result['parties'], [
            {'ref': '5', 'id': daizy.id}])
        self.assertEqual(
            daizy.employments[0].versions[0].administrative_situation, 'active')
        self.assertEqual(daizy.employments[0].versions[0].gross_salary,
            10000)
        self.assertEqual(daizy.employments[0].versions[0].increased_index, 100)
        self.assertEqual(daizy.employments[0].versions[0].work_country, fr)
        self.assertEqual(daizy.employments[0].versions[0].work_subdivision,
            allier)
        employe_update = {
            'parties': [{
                'ref': '5',
                'is_person': True,
                'name': 'Doe',
                'first_name': 'Daisy',
                'birth_date': '1974-06-10',
                'gender': 'female',
                'employments': [
                    {
                        'entry_date': '2019-01-01',
                        'employment_kind': 'test',
                        'gross_salary': '20000',
                        'administrative_situation': 'retired',
                        'increased_index': 200,
                        'work_subdivision': '03',
                        }]
                },
                ],
            }

        result = APIParty.create_party(employe_update,
            {'_debug_server': True})
        test_update, = Party.search([('name', '=', 'Doe'),
            ('first_name', '=', 'Daisy')])

        self.assertEqual(result['parties'], [
            {'ref': '5', 'id': test_update.id}])
        self.assertEqual(
            test_update.employments[0].versions[0].administrative_situation,
            'retired')
        self.assertEqual(test_update.employments[0].versions[0].increased_index,
            200)
        self.assertEqual(test_update.employments[0].versions[0].gross_salary,
            20000)
        self.assertEqual(daizy.employments[0].versions[0].work_subdivision,
            allier)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
