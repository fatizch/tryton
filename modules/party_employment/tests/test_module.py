import unittest
import datetime
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework
from trytond.modules.party_employment.offered import \
    EmploymentDataValidationError
from trytond.pool import Pool


class ModuleTestCase(test_framework.CoogTestCase):
    'Module Test Case'

    module = 'party_employment'

    @classmethod
    def fetch_models_for(cls):
        return ['offered_insurance']

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

    @test_framework.prepare_test('party_employment.'
        'test0060_party_API',
        'offered_insurance.test0010Coverage_creation',
        'contract.test0005_PrepareProductForSubscription')
    def test0070_contract_activation(self):
        pool = Pool()
        Product = pool.get('offered.product')
        Contract = pool.get('contract')
        Coverage = pool.get('offered.option.description')
        Option = pool.get('contract.option')
        CoveredElement = pool.get('contract.covered_element')
        Party = pool.get('party.party')
        product, = Product.search([
                ('code', '=', 'AAA'),
                ])
        coverage_a, = Coverage.search([('code', '=', 'ALP')])
        desc = coverage_a.item_desc
        desc.employment_required = True
        desc.save()
        start_date = product.start_date + datetime.timedelta(weeks=4)

        def test_contract(subscriber):
            contract = Contract(
                start_date=start_date,
                product=product.id,
                company=product.company.id,
                appliable_conditions_date=start_date,
                subscriber=subscriber,
                )
            contract.save()
            covered_element = CoveredElement()
            covered_element.item_desc = coverage_a.item_desc
            covered_element.contract = contract
            covered_element.party = contract.subscriber
            covered_element.save()
            option_cov_ant = Option()
            option_cov_ant.coverage = coverage_a.id
            option_cov_ant.covered_element = covered_element
            option_cov_ant.save()
            contract.activate_contract()

        daisy, = Party.search([('name', '=', 'Doe'),
            ('first_name', '=', 'Daisy')])
        test_contract(daisy)

        no_employment_data_party = Party(name='no',
            first_name='employment data', is_person=True,
            birth_date=datetime.date(1980, 1, 1),
            gender='male')
        no_employment_data_party.save()
        self.assertRaises(EmploymentDataValidationError, test_contract,
            no_employment_data_party)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
