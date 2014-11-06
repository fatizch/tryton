# -*- coding: utf-8 -*-
import unittest
import datetime
from decimal import Decimal

import mock

import trytond.tests.test_tryton
from trytond.model import ModelSQL, fields
from trytond.exceptions import UserError

from trytond.modules.cog_utils import test_framework
from trytond.modules.cog_utils import utils, coop_date, model


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    @classmethod
    def get_module_name(cls):
        return 'cog_utils'

    @classmethod
    def get_models(cls):
        return {
            'View': 'ir.ui.view',
            'MethodDefinition': 'ir.model.method',
            'Model': 'ir.model',
            'ExportTest': 'cog_utils.export_test',
            'ExportTestTarget': 'cog_utils.export_test_target',
            'ExportTestTargetSlave': 'cog_utils.export_test_target_slave',
            'ExportTestRelation': 'cog_utils.export_test_relation',
            }

    def test0020get_module_path(self):
        self.assert_(utils.get_module_path('cog_utils'))
        self.assert_(utils.get_module_path('dfsfsfsdf') is None)

    def test0030calculate_duration_between(self):
        start_date = datetime.date(2013, 1, 1)
        end_date = datetime.date(2013, 1, 31)
        self.assert_(coop_date.duration_between(start_date, end_date, 'day')
            == 31)
        self.assert_(coop_date.duration_between(start_date, end_date, 'month')
            == 1)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (1, True))
        self.assert_(coop_date.duration_between(start_date, end_date,
                'quarter') == 0)
        self.assert_(coop_date.duration_between(start_date, end_date, 'year')
            == 0)

        end_date = datetime.date(2013, 3, 31)
        self.assert_(coop_date.duration_between(start_date, end_date, 'day')
            == 90)
        self.assert_(coop_date.duration_between(start_date, end_date, 'month')
            == 3)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (3, True))
        self.assert_(coop_date.duration_between(start_date, end_date,
                'quarter') == 1)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'quarter') == (1, True))
        self.assert_(coop_date.duration_between(start_date, end_date, 'year')
            == 0)

        end_date = datetime.date(2013, 12, 31)
        self.assert_(coop_date.duration_between(start_date, end_date, 'day')
            == 365)
        self.assert_(coop_date.duration_between(start_date, end_date, 'month')
            == 12)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (12, True))
        self.assert_(coop_date.duration_between(start_date, end_date,
            'quarter') == 4)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'quarter') == (4, True))
        self.assert_(coop_date.duration_between(start_date, end_date, 'year')
            == 1)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'year') == (1, True))

        end_date = datetime.date(2014, 1, 1)
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (12, False))
        self.assert_(coop_date.duration_between_and_is_it_exact(start_date,
            end_date, 'year') == (1, False))

    def test0035_functional_error(self):
        class PatchedView(self.View, model.FunctionalErrorMixIn):
            @classmethod
            def test_functional_error(cls):
                cls.append_functional_error('error_1')

            @classmethod
            def test_blocking_error(cls):
                cls.raise_user_error('error_2')

            @classmethod
            def test_registered_error(cls):
                cls.append_functional_error('invalid_xml', ('dummy_view',))

        def test_method(method_names):
            try:
                with model.error_manager():
                    for method_name in method_names:
                        getattr(PatchedView, method_name)()
            except UserError, exc:
                return exc.message
            return None

        self.assertEqual(test_method(['test_functional_error']), 'error_1')
        self.assertEqual(test_method(['test_functional_error',
                    'test_functional_error']), 'error_1\nerror_1')
        self.assertEqual(test_method(['test_blocking_error']), 'error_2')
        self.assertEqual(test_method(['test_blocking_error',
                    'test_functional_error']), 'error_2')
        self.assertEqual(test_method(['test_functional_error',
                    'test_blocking_error']), 'error_1\nerror_2')
        self.assertEqual(test_method(['test_registered_error']),
            'Invalid XML for view "dummy_view".')

    def test0040revision_mixin(self):
        'Test RevisionMixin'

        class TestModel(ModelSQL, model._RevisionMixin):
            'Test RevisionMixin Model'
            __name__ = 'cog_utils.test_model_revision_mixin'
            _parent_name = 'parent'
            parent = fields.Integer('Parent', required=True)
            value = fields.Integer('Value')

            @staticmethod
            def revision_columns():
                return ['value']

        class TestModelWithReverseField(ModelSQL, model._RevisionMixin):
            'Test RevisionMixin Model'
            __name__ = 'cog_utils.test_model_revision_mixin'
            _parent_name = 'parent'
            parent = fields.Integer('Parent', required=True)
            value = fields.Integer('Value')

            @staticmethod
            def revision_columns():
                return ['value']

            @classmethod
            def get_reverse_field_name(cls):
                return 'revisions'

        TestModel.__setup__()
        TestModel.__post_setup__()
        TestModel.__register__('cog_utils')

        TestModelWithReverseField.__setup__()
        TestModelWithReverseField.__post_setup__()
        TestModelWithReverseField.__register__('cog_utils')

        parent_id = 1

        records = TestModel.create([{
                    'parent': parent_id,
                    'date': None,
                    'value': 1,
                    }, {
                    'parent': parent_id,
                    'date': datetime.date(2014, 1, 1),
                    'value': 2,
                    }, {
                    'parent': parent_id,
                    'date': datetime.date(2014, 6, 1),
                    'value': 3,
                    }, {
                    'parent': parent_id,
                    'date': datetime.date(2014, 12, 1),
                    'value': 4,
                    }])

        parent = mock.Mock()
        parent.id = parent_id

        self.assertEqual(TestModel.get_values([parent], ['value']),
            {'value': {parent_id: 1}, 'id': {parent_id: records[0].id}})

        self.assertEqual(TestModel.get_values([parent], ['value'],
                datetime.date(2014, 2, 1)),
            {'value': {parent_id: 2}, 'id': {parent_id: records[1].id}})

        self.assertEqual(TestModel.get_values([parent], ['value'],
                datetime.date(2014, 6, 1)),
            {'value': {parent_id: 3}, 'id': {parent_id: records[2].id}})

        self.assertEqual(TestModel.get_values([parent], ['value'],
                datetime.date(2015, 1, 1)),
            {'value': {parent_id: 4}, 'id': {parent_id: records[3].id}})

        TestModel.delete([records[0]])
        self.assertEqual(TestModel.get_values([parent], ['value']),
            {'value': {parent_id: None}, 'id': {parent_id: None}})

        parent_id = 2
        parent.id = parent_id

        records_reverse_field = TestModel.create([{
                    'parent': parent_id,
                    'date': None,
                    'value': 1,
                    }, {
                    'parent': parent_id,
                    'date': datetime.date(2014, 1, 1),
                    'value': 2,
                    }])

        self.assertEqual(
            TestModelWithReverseField.get_values([parent], ['value']),
            {'value': {parent_id: 1},
                'revisions': {parent_id: records_reverse_field[0].id}})

    def test0041get_value_at_date(self):

        class TestClass(object):
            def __init__(self, date=None, value=None):
                self.date = date
                self.value = value

        from datetime import date

        value1 = TestClass(None, 10)
        self.assertEqual(utils.get_value_at_date(
                [value1], date(2000, 10, 1)), value1)

        value2 = TestClass(date(2014, 1, 1), 20)
        self.assertEqual(utils.get_value_at_date(
                [value2], date(2013, 12, 31)), None)
        self.assertEqual(utils.get_value_at_date(
                [value2], date(2014, 1, 1)), value2)

        self.assertEqual(utils.get_value_at_date(
                [value1, value2], date(2013, 12, 31)), value1)
        self.assertEqual(utils.get_value_at_date(
                [value1, value2], date(2014, 1, 1)), value2)

        # Check that the order does not matter
        self.assertEqual(utils.get_value_at_date(
                [value2, value1], date(2014, 1, 1)), value2)

    def test0042_test_list_proxy(self):
        test_list = [
            (1, 10),
            (4, 20),
            (10, 14),
            ]
        proxied_list = utils.ProxyListWithGetter(test_list,
            lambda x: x[0])
        self.assertEqual([x for x in proxied_list], [1, 4, 10])
        self.assertEqual(len(proxied_list), 3)

    def test0043_test_method_definition_filter(self):
        class TestModel(ModelSQL):
            'Test Method Definition Model'
            __name__ = 'cog_utils.test_model_method_definition'

            attribute = None

            @classmethod
            def class_method(cls):
                pass

            def _hidden_method(self):
                pass

            def arg_method(self, *args):
                pass

            def no_caller(self, foo=None):
                pass

            def no_default(self, foo, caller=None):
                pass

            def good_one(self, foo=None, caller=None):
                return caller

            def other_good_one(self, caller=None, foo=None, **kwargs):
                pass

        TestModel.__setup__()
        TestModel.__post_setup__()
        TestModel.__register__('cog_utils')

        method = self.MethodDefinition()
        self.assertEqual(method.get_possible_methods(), [])

        method.model = self.Model.search([
                ('model', '=', 'cog_utils.test_model_method_definition')])[0]

        with mock.patch.object(trytond.tests.test_tryton.POOL,
                'get') as pool_get:
            pool_get.return_value = TestModel
            self.assertEqual(method.get_possible_methods(), [
                    ('good_one', 'good_one'),
                    ('other_good_one', 'other_good_one'),
                    ])
            pool_get.assert_called_with(
                'cog_utils.test_model_method_definition')

        method.method_name = 'good_one'

        callee = TestModel()
        self.assertEqual(method.execute(10, callee), 10)

    def test0050_export_import_key_not_unique(self):
        to_export = self.ExportTestTarget(char="sometext")
        to_export.save()
        duplicata = self.ExportTestTarget(char="sometext")
        duplicata.save()
        output = []
        to_export.export_ws_json(output=output)

        self.assertRaises(UserError, self.ExportTestTarget.import_ws_json,
            output[0])

    def test0051_export_import_non_relation_fields(self):
        self.maxDiff = None
        values = {
            'boolean': True,
            'integer': 0,
            'float': 0.0002,
            'numeric': Decimal("0.03"),
            'char': "somekey",
            'text': "line \n line2 \nline3",
            'date': datetime.date(2012, 12, 3),
            'datetime': datetime.datetime(2014, 11, 3, 2, 3, 1),
            'selection': 'select1',
        }

        to_export = self.ExportTest(**values)
        to_export.save()
        output = []
        to_export.export_ws_json(output=output)

        values.update({'_func_key': 'somekey',
                '__name__': 'cog_utils.export_test',
                'reference': None,
                'one2many': [],
                'valid_one2many': [],
                'many2many': [],
                'many2one': None,
                })

        self.assertDictEqual(values, output[0])
        output[0]['text'] = 'someothertext'
        values['text'] = 'someothertext'
        self.ExportTest.multiple_import_ws_json(output)
        output = []
        to_export.export_ws_json(output=output)

        self.assertDictEqual(values, output[0])

    def test0052_export_import_many2one(self):
        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', many2one=target)
        to_export.save()
        output = []
        to_export.export_ws_json(output=output)

        self.assertEqual(output[0]['_func_key'], 'key')
        self.assertEqual(output[1]['_func_key'], 'otherkey')

        output[0]['integer'] = 12

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual(12, to_export.many2one.integer)

    def test_0053_export_import_many2many(self):

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', many2many=[target])
        to_export.save()
        former = to_export.many2many
        output = []
        to_export.export_ws_json(output=output)

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual(to_export.many2many, former)

    def test_0054_export_import_many2many_update(self):

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', many2many=[target])
        to_export.save()
        former_char = to_export.many2many[0].char
        output = []
        to_export.export_ws_json(output=output)

        to_export.many2many = []
        to_export.save()

        self.ExportTestTarget.delete([target])

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual(to_export.many2many[0].char, former_char)

    def test_00542_export_import_many2many_remove(self):

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', many2many=[target])
        to_export.save()

        output = []
        to_export.export_ws_json(output=output)
        output[1]['many2many'] = []

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual((), to_export.many2many)

    def test0055_export_import_recursion(self):
        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', many2one=target)
        to_export.save()
        target.many2one = to_export
        target.save()
        output = []
        to_export.export_ws_json(output=output)
        output[0]['integer'] = 12

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual(12, to_export.many2one.integer)
        self.assertEqual(to_export, to_export.many2one.many2one)

    def test0056_export_import_reference_field(self):
        target = self.ExportTestTarget(char='key', integer=12)
        target.save()
        to_export = self.ExportTest(char='otherkey', reference=target)
        to_export.save()
        output = []
        to_export.export_ws_json(output=output)
        output[0]['reference']['integer'] = 3

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual(3, to_export.reference.integer)

    def test_0057_export_import_one2many(self):

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', one2many=[target])
        to_export.save()
        former = to_export.one2many
        output = []
        to_export.export_ws_json(output=output)

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual(to_export.one2many, former)

    def test_00571_export_import_one2many_update(self):

        target = self.ExportTestTargetSlave(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', valid_one2many=[target])
        to_export.save()
        output = []
        to_export.export_ws_json(output=output)

        to_export.one2many = []
        to_export.save()
        self.ExportTestTargetSlave.delete([target])

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual(to_export.valid_one2many[0].char, 'key')

    def test_00572_export_import_one2many_no_update(self):
        # One2many to master object are not managed

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', one2many=[target])
        to_export.save()
        output = []
        to_export.export_ws_json(output=output)

        to_export.one2many = []
        to_export.save()
        self.ExportTestTarget.delete([target])

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual((), to_export.one2many)

    def test_00573_export_import_one2many_delete(self):
        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', one2many=[target])
        to_export.save()
        output = []
        to_export.export_ws_json(output=output)

        output[1]['one2many'] = []

        self.ExportTest.multiple_import_ws_json(output)
        self.assertEqual((), to_export.one2many)
        self.assertEqual([], self.ExportTestTarget.search(
                [('id', '!=', 0)]))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModuleTestCase))
    return suite
