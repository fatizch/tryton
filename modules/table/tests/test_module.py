# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.modules.coog_core import test_framework


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'table'

    @classmethod
    def get_models(cls):
        return {
            'Definition': 'table',
            'Dimension': 'table.dimension.value',
            'Cell': 'table.cell',
        }

    def test0010definition_get(self):
        '''
        Test Definition.get.
        '''
        definition, = self.Definition.create([{
            'name': 'Test',
            'code': 'test0',
            'type_': 'char',
        }])
        self.assertEqual(self.Definition.get('Test'), definition)
        self.assertRaises(IndexError, self.Definition.get, 'foo')

    def test0020table_1dim_value_get(self):
        '''
        Test TableCell.get with 1 dimension of value.
        '''
        definition, = self.Definition.create([{
                    'name': 'Test',
                    'code': 'test1',
                    'dimension_kind1': 'value',
                    'type_': 'char',
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
        for values in (
                {'dimension1': dim1_foo.id, 'value': 'ham'},
                {'dimension1': dim1_bar.id, 'value': 'spam'}):
            values.update({
                    'definition': definition.id,
                    })
            self.Cell.create([values])
        for query, result in (
                (('foo',), 'ham'),
                (('bar',), 'spam'),
                (('test',), None)):
            self.assertEqual(
                self.Cell.get(definition, *query),
                result, (query, result))

    def test0030table_1dim_date_get(self):
        '''
        Test TableCell.get with 1 dimension of date.
        '''
        definition, = self.Definition.create([{
                    'name': 'Test',
                    'code': 'test2',
                    'type_': 'char',
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
        for values in (
                {'dimension1': dim1_foo.id, 'value': 'ham'},
                {'dimension1': dim1_bar.id, 'value': 'spam'}):
            values.update({
                    'definition': definition.id,
                    })
            self.Cell.create([values])
        for query, result in (
                ((datetime.date(2012, 12, 21),), 'ham'),
                ((datetime.date(2012, 9, 21),), 'spam'),
                ((datetime.date(2012, 6, 20),), None)):
            self.assertEqual(
                self.Cell.get(definition, *query),
                result, (query, result))

    def test0040table_1dim_range_get(self):
        '''
        Test TableCell.get with 1 dimension of range.
        '''
        definition, = self.Definition.create([{
                    'name': 'Test',
                    'code': 'test3',
                    'type_': 'char',
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
        for values in (
                {'dimension1': dim1_foo.id, 'value': 'ham'},
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
                ((50,), None)):
            self.assertEqual(
                self.Cell.get(definition, *query),
                result, (query, result))

    def test0041table_1dim_range_get(self):
        '''
        Test TableCell.get with 1 dimension of range.
        '''
        definition, = self.Definition.create([{
                    'name': 'Test',
                    'code': 'test',
                    'type_': 'char',
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
        for values in (
                {'dimension1': dim1_foo.id, 'value': 'ham'},
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
                ((50,), 'spam')):
            self.assertEqual(
                self.Cell.get(definition, *query),
                result, (query, result))

    def test0050table_1dim_range_date_get(self):
        '''
        Test TableCell.get with 1 dimension of range-date.
        '''
        definition, = self.Definition.create([{
                    'name': 'Test',
                    'code': 'test4',
                    'type_': 'char',
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
        for values in (
                {'dimension1': dim1_foo.id, 'value': 'ham'},
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
                ((datetime.date(2014, 1, 1),), None)):
            self.assertEqual(
                self.Cell.get(definition, *query),
                result, (query, result))

    def test0051table_1dim_range_date_get(self):
        '''
        Test TableCell.get with 1 dimension of range-date.
        '''
        definition, = self.Definition.create([{
                    'name': 'Test',
                    'code': 'test',
                    'type_': 'char',
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
        for values in (
                {'dimension1': dim1_foo.id, 'value': 'ham'},
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
                ((datetime.date(2014, 1, 1),), 'spam')):
            self.assertEqual(
                self.Cell.get(definition, *query),
                result, (query, result))

    def test0060table_2dim(self):
        '''
        Test TableCell.get with 2 dimensions of value.
        '''
        definition, = self.Definition.create([{
                    'name': 'Test',
                    'code': 'test_code',
                    'type_': 'char',
                    'dimension_kind1': 'value',
                    'dimension_kind2': 'range',
                    'dimension_name1': 'Value',
                    'dimension_name2': 'Range',
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
                (('test', 30), None)):
            self.assertEqual(
                self.Cell.get(definition, *query),
                result, (query, result))

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
                (datetime.date(2012, 12, 12), 'date')):
            self.assertEqual(
                self.Cell._load_value(
                    self.Cell._dump_value({'value': value})['value'],
                    type_), value)

    @test_framework.prepare_test('table.test0060table_2dim')
    def test0090test_export(self):
        # Note: test pass only with a database configured as postgresql
        self.maxDiff = None
        test_table = self.Definition.search([('code', '=', 'test_code')])[0]
        file_name, result, _ = test_table.export_json_to_file()
        self.assertEqual(file_name, '[%s][table]test_code.json' %
            datetime.date.today().strftime('%Y-%m-%d'))
        result[0]['cells'] = set(result[0]['cells'])
        self.assertEqual(result, [
                {'__name__': 'table',
                    '_func_key': u'test_code',
                    'cells': set([(u'bar', u'[1.0 - 10.0[', u'spam'),
                        (u'foo', u'[1.0 - 10.0[', u'ham'),
                        (u'bar', u'[20.0 - 42.0[', u'chicken'),
                        (u'foo', u'[20.0 - 42.0[', u'egg'),
                        ]),
                    'code': u'test_code',
                    'dimension1': [{'__name__': 'table.dimension.value',
                            '_func_key': u'bar',
                            'date': None,
                            'end': None,
                            'end_date': None,
                            'name': u'bar',
                            'sequence': None,
                            'start': None,
                            'start_date': None,
                            'type': u'dimension1',
                            'value': u'bar'},
                        {'__name__': 'table.dimension.value',
                            '_func_key': u'foo',
                            'date': None,
                            'end': None,
                            'end_date': None,
                            'name': u'foo',
                            'sequence': None,
                            'start': None,
                            'start_date': None,
                            'type': u'dimension1',
                            'value': u'foo'}],
                    'dimension2': [{'__name__': 'table.dimension.value',
                            '_func_key': u'[1.0 - 10.0[',
                            'date': None,
                            'end': 10.0,
                            'end_date': None,
                            'name': u'[1.0 - 10.0[',
                            'sequence': None,
                            'start': 1.0,
                            'start_date': None,
                            'type': u'dimension2',
                            'value': None},
                        {'__name__': 'table.dimension.value',
                            '_func_key': u'[20.0 - 42.0[',
                            'date': None,
                            'end': 42.0,
                            'end_date': None,
                            'name': u'[20.0 - 42.0[',
                            'sequence': None,
                            'start': 20.0,
                            'start_date': None,
                            'type': u'dimension2',
                            'value': None}],
                    'dimension3': [],
                    'dimension4': [],
                    'dimension_kind1': u'value',
                    'dimension_kind2': u'range',
                    'dimension_kind3': None,
                    'dimension_kind4': None,
                    'dimension_name1': u'Value',
                    'dimension_name2': u'Range',
                    'dimension_name3': None,
                    'dimension_name4': None,
                    'dimension_order1': u'alpha',
                    'dimension_order2': u'alpha',
                    'dimension_order3': u'alpha',
                    'dimension_order4': u'alpha',
                    'name': u'Test',
                    'number_of_digits': 2,
                    'tags': [],
               'type_': u'char'}])

    @test_framework.prepare_test('table.test0060table_2dim')
    def test0091test_copy(self):
        test_table = self.Definition.search([('code', '=', 'test_code')])[0]
        new_table = test_table.copy([test_table])[0]
        self.assertEqual(new_table.code, 'test_code_clone')
        self.assertEqual(self.Cell.get(new_table, 'bar', 30), 'chicken')

        # Check original table is still there
        test_table = self.Definition.search([('code', '=', 'test_code')])[0]


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
