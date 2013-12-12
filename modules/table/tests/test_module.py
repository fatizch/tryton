import unittest
import datetime
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.transaction import Transaction
from trytond.modules.coop_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'table'

    @classmethod
    def get_models(cls):
        return {
            'Definition': 'table',
            'Dimension': 'table.dimension.value',
            'Cell': 'table.cell',
            'ManageDimension1': 'table.manage_dimension.show_dimension_1',
        }

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
    def test0080test_manage_dimension1_wizard(self):
        table = self.Definition.search([('code', '=', 'test_code')])[0]
        with Transaction().set_context({'active_id': table.id}):
            wizard_id, _, _ = self.ManageDimension1.create()
            wizard = self.ManageDimension1(wizard_id)
            wizard._execute('dimension_management')
            res = wizard.default_dimension_management(None)
            self.assertEqual(res, {
                    'date_format': "%d%m%y",
                    'kind': "value",
                    'name': "Value",
                    'cur_dimension': 1,
                    'converted_text': "bar\nfoo",
                    'values': [2, 1],
                    'table': 1,
                    'order': "alpha",
                })
            self.assertEqual(self.ManageDimension1.next_dim_action.action_id,
                'table.act_manage_dimension_2')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
