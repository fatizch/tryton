#-*- coding:utf-8 -*-
import unittest
from datetime import date

import trytond.tests.test_tryton
from trytond.modules.coop_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'party_fr'

    @classmethod
    def get_models(cls):
        return {
            'Person': 'party.party',
        }

    def createPerson(
            self, birth_date, ssn, expected_return, gender='male', i=0):
        try:
            person, = self.Person.create([{
                'is_person': True,
                'name': 'Person %s' % i,
                'first_name': 'first name %s' % i,
                'ssn': ssn,
                'birth_date': birth_date,
                'gender': gender,
                'addresses': []
            }])
            res = person.id > 0
        except:
            res = False
        self.assertEqual(res, expected_return)

    def test0010ssn(self):
        '''
        Test SSN
        '''
        values = (
                ('145062B12312341', True),
                ('145062B12312342', False),
                ('145062A12312314', True),
                ('145062A12312315', False),
                ('145067512312354', True),
                ('145067512312355', False),
                ('145065C12312307', False),
                ('14511661231233', False),
                ('279086507612053', True)
        )
        for i, (value, test) in enumerate(values):
            birth_date = date(int('19' + value[1:3]), int(value[3:5]), 1)
            gender = 'male'
            if value[0:1] == '2':
                gender = 'female'
            self.createPerson(birth_date, value, test, gender, i)

    def test0020ssnbirthdate(self):
        '''
        Test SSN and birthdate compatibility
        '''
        ssn = '145062B12312341'
        birth_date = date(int('19' + ssn[1:3]), int(ssn[3:5]), 1)
        self.createPerson(birth_date, ssn, True)
        birth_date = date(int('1946'), int(ssn[3:5]), 1)
        self.createPerson(birth_date, ssn, False)
        birth_date = date(int('19' + ssn[1:3]), 07, 1)
        self.createPerson(birth_date, ssn, False)

    def test0030ssngender(self):
        '''
        Test SSN and gender compatibility
        '''
        ssn = '245062B12312388'
        birth_date = date(int('19' + ssn[1:3]), int(ssn[3:5]), 1)
        self.createPerson(birth_date, ssn, True, gender='female')
        self.createPerson(birth_date, ssn, False, gender='male')
        ssn = '145062B12312341'
        self.createPerson(birth_date, ssn, False, gender='female')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
