#!/usr/bin/env python
import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import datetime
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.modules.coop_utils import test_framework, prepare_test
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction

MODULE_NAME = os.path.basename(
                  os.path.abspath(
                      os.path.join(os.path.normpath(__file__), '..', '..')))


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''

    @classmethod
    def get_module_name(cls):
        return MODULE_NAME

    @classmethod
    def get_models(cls):
        return {
            'Definition': 'table.table_def',
            'Dimension': 'table.table_dimension',
            'Cell': 'table.table_cell',
        }

    @prepare_test()
    def test0010definition_get(self):
        '''
        Test Definition.get.
        '''
        definition, = self.Definition.create([{
                'name': 'Test',
                'code': 'test0'
                }])
        self.assertEqual(self.Definition.get('Test'), definition)
        self.assertRaises(IndexError, self.Definition.get, 'foo')

    @prepare_test()
    def test0020table_1dim_value_get(self):
        '''
        Test TableCell.get with 1 dimension of value.
        '''
        definition, = self.Definition.create([{
                'name': 'Test',
                'code': 'test1',
                'dimension_kind1': 'value',
                }])
        dim1_foo, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'value': 'foo',
                }])
        dim1_bar, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'value': 'bar',
                }])
        for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                {'dimension1': dim1_bar.id, 'value': 'spam'}):
            values.update({
                    'definition': definition.id,
                    })
            self.Cell.create([values])
        for query, result in (
                (('foo',), 'ham'),
                (('bar',), 'spam'),
                (('test',), None),
                ):
            self.assertEqual(self.Cell.get(definition, *query),
                result, (query, result))

    @prepare_test()
    def test0030table_1dim_date_get(self):
        '''
        Test TableCell.get with 1 dimension of date.
        '''
        definition, = self.Definition.create([{
                'name': 'Test',
                'code': 'test2',
                'dimension_kind1': 'date',
                }])
        dim1_foo, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'date': datetime.date(2012, 12, 21),
                }])
        dim1_bar, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'date': datetime.date(2012, 9, 21),
                }])
        for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                {'dimension1': dim1_bar.id, 'value': 'spam'}):
            values.update({
                    'definition': definition.id,
                    })
            self.Cell.create([values])
        for query, result in (
                ((datetime.date(2012, 12, 21),), 'ham'),
                ((datetime.date(2012, 9, 21),), 'spam'),
                ((datetime.date(2012, 6, 20),), None),
                ):
            self.assertEqual(self.Cell.get(definition, *query),
                result, (query, result))

    @prepare_test()
    def test0040table_1dim_range_get(self):
        '''
        Test TableCell.get with 1 dimension of range.
        '''
        definition, = self.Definition.create([{
                'name': 'Test',
                'code': 'test3',
                'dimension_kind1': 'range',
                }])
        dim1_foo, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'start': 1,
                'end': 10,
                }])
        dim1_bar, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'start': 20,
                'end': 42,
                }])
        for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                {'dimension1': dim1_bar.id, 'value': 'spam'}):
            values.update({
                    'definition': definition.id,
                    })
            self.Cell.create([values])
        for query, result in (
                ((0,), None),
                ((1,), 'ham'),
                ((5,), 'ham'),
                ((10,), None),
                ((30,), 'spam'),
                ((50,), None),
                ):
            self.assertEqual(self.Cell.get(definition, *query),
                result, (query, result))

    @prepare_test()
    def test0041table_1dim_range_get(self):
        '''
        Test TableCell.get with 1 dimension of range.
        '''
        definition, = self.Definition.create([{
                'name': 'Test',
                'code': 'test',
                'dimension_kind1': 'range',
                }])
        dim1_foo, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'start': None,
                'end': 10,
                }])
        dim1_bar, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'start': 20,
                'end': None,
                }])
        for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                {'dimension1': dim1_bar.id, 'value': 'spam'}):
            values.update({
                    'definition': definition.id,
                    })
            self.Cell.create([values])
        for query, result in (
                ((0,), 'ham'),
                ((5,), 'ham'),
                ((10,), None),
                ((30,), 'spam'),
                ((50,), 'spam'),
                ):
            self.assertEqual(self.Cell.get(definition, *query),
                result, (query, result))

    @prepare_test()
    def test0050table_1dim_range_date_get(self):
        '''
        Test TableCell.get with 1 dimension of range-date.
        '''
        definition, = self.Definition.create([{
                'name': 'Test',
                'code': 'test4',
                'dimension_kind1': 'range-date',
                }])
        dim1_foo, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'start_date': datetime.date(2012, 1, 1),
                'end_date': datetime.date(2012, 12, 31),
                }])
        dim1_bar, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'start_date': datetime.date(2013, 6, 1),
                'end_date': datetime.date(2013, 8, 1),
                }])
        for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                {'dimension1': dim1_bar.id, 'value': 'spam'}):
            values.update({
                    'definition': definition.id,
                    })
            self.Cell.create([values])
        for query, result in (
                ((datetime.date(2011, 1, 1),), None),
                ((datetime.date(2012, 1, 1),), 'ham'),
                ((datetime.date(2012, 3, 1),), 'ham'),
                ((datetime.date(2013, 1, 1),), None),
                ((datetime.date(2013, 7, 1),), 'spam'),
                ((datetime.date(2014, 1, 1),), None),
                ):
            self.assertEqual(self.Cell.get(definition, *query),
                result, (query, result))

    @prepare_test()
    def test0051table_1dim_range_date_get(self):
        '''
        Test TableCell.get with 1 dimension of range-date.
        '''
        definition, = self.Definition.create([{
                'name': 'Test',
                'code': 'test',
                'dimension_kind1': 'range-date',
                }])
        dim1_foo, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'start_date': None,
                'end_date': datetime.date(2012, 12, 31),
                }])
        dim1_bar, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'start_date': datetime.date(2013, 6, 1),
                'end_date': None,
                }])
        for values in ({'dimension1': dim1_foo.id, 'value': 'ham'},
                {'dimension1': dim1_bar.id, 'value': 'spam'}):
            values.update({
                    'definition': definition.id,
                    })
            self.Cell.create([values])
        for query, result in (
                ((datetime.date(2011, 1, 1),), 'ham'),
                ((datetime.date(2012, 3, 1),), 'ham'),
                ((datetime.date(2013, 1, 1),), None),
                ((datetime.date(2013, 7, 1),), 'spam'),
                ((datetime.date(2014, 1, 1),), 'spam'),
                ):
            self.assertEqual(self.Cell.get(definition, *query),
                result, (query, result))

    @prepare_test()
    def test0060table_2dim(self):
        '''
        Test TableCell.get with 2 dimensions of value.
        '''
        definition, = self.Definition.create([{
                'name': 'Test',
                'code': 'test_code',
                'dimension_kind1': 'value',
                'dimension_kind2': 'range',
                }])
        dim1_foo, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'value': 'foo',
                }])
        dim1_bar, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension1',
                'value': 'bar',
                }])
        dim2_foo, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension2',
                'start': 1,
                'end': 10,
                }])
        dim2_bar, = self.Dimension.create([{
                'definition': definition.id,
                'type': 'dimension2',
                'start': 20,
                'end': 42,
                }])
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
            self.Cell.create([values])

        for query, result in (
                (('foo', 1), 'ham'),
                (('bar', 5), 'spam'),
                (('foo', 10), None),
                (('bar', 30), 'chicken'),
                (('test', 30), None),
                ):
            self.assertEqual(self.Cell.get(definition, *query),
                result, (query, result))

    @prepare_test()
    def test0070load_dump_value(self):
        '''
        Test load/dump value.
        '''
        for value, type_ in (
                (None, 'char'),
                ('test', 'char'),
                ('', 'char'),
                (None, 'integer'),
                (1, 'integer'),
                (None, 'numeric'),
                (Decimal('1.5'), 'numeric'),
                (False, 'boolean'),
                (True, 'boolean'),
                (None, 'date'),
                (datetime.date(2012, 12, 12), 'date'),
                ):
            self.assertEqual(self.Cell._load_value(
                    self.Cell._dump_value({'value': value})['value'],
                    type_), value)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
