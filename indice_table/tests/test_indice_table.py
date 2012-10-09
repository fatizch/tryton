#!/usr/bin/env python
import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import datetime
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction


class IndiceTableTestCase(unittest.TestCase):
    '''
    Test IndiceTable module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('indice_table')
        self.definition = POOL.get('indice_table.definition')
        self.dimension = POOL.get('indice_table.definition.dimension')
        self.indice_table = POOL.get('indice_table')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('indice_table')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010definition_get(self):
        '''
        Test Definition.get.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            definition = self.definition.create({
                    'name': 'Test',
                    })
            self.assertEqual(self.definition.get('Test'), definition)
            self.assertRaises(IndexError, self.definition.get, 'foo')

    def test0020indice_table_1dim_value_get(self):
        '''
        Test IndiceTable.get with 1 dimension of value.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            definition = self.definition.create({
                    'name': 'Test',
                    'dimension_kind1': 'value',
                    })
            dim1_foo = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'value': 'foo',
                    })
            dim1_bar = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'value': 'bar',
                    })
            for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                    {'dimension1': dim1_bar.id, 'value': 'spam'}):
                values.update({
                        'definition': definition.id,
                        })
                self.indice_table.create(values)
            for query, result in (
                    (('foo',), 'ham'),
                    (('bar',), 'spam'),
                    (('test',), None),
                    ):
                self.assertEqual(self.indice_table.get(definition, *query),
                    result, (query, result))

    def test0030indice_table_1dim_date_get(self):
        '''
        Test IndiceTable.get with 1 dimension of date.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            definition = self.definition.create({
                    'name': 'Test',
                    'dimension_kind1': 'date',
                    })
            dim1_foo = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'date': datetime.date(2012, 12, 21),
                    })
            dim1_bar = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'date': datetime.date(2012, 9, 21),
                    })
            for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                    {'dimension1': dim1_bar.id, 'value': 'spam'}):
                values.update({
                        'definition': definition.id,
                        })
                self.indice_table.create(values)
            for query, result in (
                    ((datetime.date(2012, 12, 21),), 'ham'),
                    ((datetime.date(2012, 9, 21),), 'spam'),
                    ((datetime.date(2012, 6, 20),), None),
                    ):
                self.assertEqual(self.indice_table.get(definition, *query),
                    result, (query, result))

    def test0040indice_table_1dim_range_get(self):
        '''
        Test IndiceTable.get with 1 dimension of range.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            definition = self.definition.create({
                    'name': 'Test',
                    'dimension_kind1': 'range',
                    })
            dim1_foo = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'start': 1,
                    'end': 10,
                    })
            dim1_bar = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'start': 20,
                    'end': 42,
                    })
            for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                    {'dimension1': dim1_bar.id, 'value': 'spam'}):
                values.update({
                        'definition': definition.id,
                        })
                self.indice_table.create(values)
            for query, result in (
                    ((0,), None),
                    ((1,), 'ham'),
                    ((5,), 'ham'),
                    ((10,), None),
                    ((30,), 'spam'),
                    ((50,), None),
                    ):
                self.assertEqual(self.indice_table.get(definition, *query),
                    result, (query, result))

    def test0050indice_table_1dim_range_date_get(self):
        '''
        Test IndiceTable.get with 1 dimension of range.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            definition = self.definition.create({
                    'name': 'Test',
                    'dimension_kind1': 'range-date',
                    })
            dim1_foo = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'start_date': datetime.date(2012, 1, 1),
                    'end_date': datetime.date(2012, 12, 31),
                    })
            dim1_bar = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'start_date': datetime.date(2013, 6, 1),
                    'end_date': datetime.date(2013, 8, 1),
                    })
            for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                    {'dimension1': dim1_bar.id, 'value': 'spam'}):
                values.update({
                        'definition': definition.id,
                        })
                self.indice_table.create(values)
            for query, result in (
                    ((datetime.date(2011, 1, 1),), None),
                    ((datetime.date(2012, 1, 1),), 'ham'),
                    ((datetime.date(2012, 3, 1),), 'ham'),
                    ((datetime.date(2013, 1, 1),), None),
                    ((datetime.date(2013, 7, 1),), 'spam'),
                    ((datetime.date(2014, 1, 1),), None),
                    ):
                self.assertEqual(self.indice_table.get(definition, *query),
                    result, (query, result))

    def test0060indice_table_2dim(self):
        '''
        Test IndiceTable.get with 2 dimensions of value.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            definition = self.definition.create({
                    'name': 'Test',
                    'dimension_kind1': 'value',
                    'dimension_kind2': 'range',
                    })
            dim1_foo = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'value': 'foo',
                    })
            dim1_bar = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension1',
                    'value': 'bar',
                    })
            dim2_foo = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension2',
                    'start': 1,
                    'end': 10,
                    })
            dim2_bar = self.dimension.create({
                    'definition': definition.id,
                    'type': 'dimension2',
                    'start': 20,
                    'end': 42,
                    })
            for values in (
                    {'dimension1': dim1_foo.id, 'dimension2': dim2_foo.id,
                        'value': 'ham'},
                    {'dimension1': dim1_bar.id, 'dimension2': dim2_foo.id,
                        'value': 'spam'},
                    {'dimension1': dim1_foo.id, 'dimension2': dim2_bar.id,
                        'value': 'egg'},
                    {'dimension1': dim1_bar.id, 'dimension2': dim2_bar.id,
                        'value': 'chicken'}):
                values.update({
                        'definition': definition.id,
                        })
                self.indice_table.create(values)

            for query, result in (
                    (('foo', 1), 'ham'),
                    (('bar', 5), 'spam'),
                    (('foo', 10), None),
                    (('bar', 30), 'chicken'),
                    (('test', 30), None),
                    ):
                self.assertEqual(self.indice_table.get(definition, *query),
                    result, (query, result))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            IndiceTableTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
