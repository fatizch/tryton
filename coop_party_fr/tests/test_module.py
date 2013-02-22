#-*- coding:utf-8 -*-
import sys
import os
from datetime import date

DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction

MODULE_NAME = os.path.basename(
                  os.path.abspath(
                      os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(unittest.TestCase):
    '''
    Test Coop module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module(MODULE_NAME)
        self.Person = POOL.get('party.party')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view(MODULE_NAME)

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def createPerson(
            self, birth_date, ssn, expected_return, gender='male', i=0):
        with Transaction().start(DB_NAME, USER,
           context=CONTEXT):
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
