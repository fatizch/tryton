# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
import mock
from decimal import Decimal

from datetime import date
from sql import Column

from trytond import backend
import trytond.tests.test_tryton
from trytond.model import ModelSQL, fields
from trytond.transaction import Transaction
from trytond.exceptions import UserError

from trytond.modules.coog_core import test_framework, history_tools
from trytond.modules.coog_core import utils, coog_string, coog_date, model


class ModuleTestCase(test_framework.CoogTestCase):
    '''
    Test Coog module.
    '''
    module = 'coog_core'

    @classmethod
    def get_models(cls):
        return {
            'View': 'ir.ui.view',
            'TestMethodDefinition': 'coog_core.test_model_method_definition',
            'MethodDefinition': 'ir.model.method',
            'Model': 'ir.model',
            'ExportTest': 'coog_core.export_test',
            'ExportTestTarget': 'coog_core.export_test_target',
            'ExportTestTargetSlave': 'coog_core.export_test_target_slave',
            'ExportTestRelation': 'coog_core.export_test_relation',
            'O2MMaster': 'coog_core.o2m_deletion_master_test',
            'O2MChild': 'coog_core.o2m_deletion_child_test',
            'ExportModelConfiguration': 'ir.export.configuration.model',
            'ExportConfiguration': 'ir.export.configuration',
            'ExportFieldConfiguration': 'ir.export.configuration.field',
            'EventTypeAction': 'event.type.action',
            'TestHistoryTable': 'coog_core.test_history',
            'TestHistoryChildTable': 'coog_core.test_history.child',
            'TestLoaderUpdater': 'coog_core.test_loader_updater',
            }

    def test0010class_injection(self):
        assert issubclass(self.TestLoaderUpdater,
            model.GlobalSearchLimitedMixin)
        assert issubclass(self.View, model.GlobalSearchLimitedMixin)
        assert issubclass(self.Model, model.GlobalSearchLimitedMixin)
        assert issubclass(self.EventTypeAction, model.GlobalSearchLimitedMixin)

    def test0020get_module_path(self):
        self.assert_(utils.get_module_path('coog_core'))
        self.assert_(utils.get_module_path('dfsfsfsdf') is None)

    def test0025_clear_history(self):
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        def assert_history(klass, fname, values):
            h_table = klass.__table_history__()
            cursor.execute(*h_table.select(
                    Column(h_table, '__id'), Column(h_table, fname),
                    order_by=Column(h_table, '__id')))
            self.assertEqual(cursor.fetchall(), values)

        # Basic test : Check only latest version exists
        master = self.TestHistoryTable(foo='v1')
        master.save()
        transaction.commit()
        master.foo = 'v2'
        master.save()
        master.foo = 'v3'
        master.save()
        transaction.commit()

        assert_history(self.TestHistoryTable, 'foo', [
                    (1, 'v1'), (2, 'v2'), (3, 'v3')])

        # Test ignore_before : delete all history except the latest version,
        # as well as any version before ignore_before
        #   => all ignored, no changes
        history_tools.clear_previous_history([master],
            ignore_before=master.write_date)
        assert_history(self.TestHistoryTable, 'foo', [
                    (1, 'v1'), (2, 'v2'), (3, 'v3')])

        # Test include_ignore : delete all history except the latest version
        # and all versions striclty before ignore_before
        #  => remove v2
        history_tools.clear_previous_history([master],
            ignore_before=master.write_date, include_ignore=False)
        assert_history(self.TestHistoryTable, 'foo', [
                    (1, 'v1'), (3, 'v3')])

        # Test standard clear : Remove all but latest version
        history_tools.clear_previous_history([master])
        master = self.TestHistoryTable(master.id)
        self.assertEqual(master.foo, 'v3')
        assert_history(self.TestHistoryTable, 'foo', [(3, 'v3')])

        # Test Children
        master.childs = [
            self.TestHistoryChildTable(bar='v1a'),
            self.TestHistoryChildTable(bar='v1b'),
            ]
        master.save()
        transaction.commit()
        master.childs = [master.childs[1]]
        master.foo = 'v4'
        master.save()
        transaction.commit()
        master.childs[0].bar = 'v2b'
        # Only save the child, not the master
        master.childs[0].save()
        transaction.commit()

        # Current history versions :
        #  - master : (3, 'v3'), (4, 'v4')
        #  - childs :
        #       * child 1 : (1, 'v1a'), (3, -'v1a')
        #       * child 2 : (2, 'v1b'), (4, v1b->'v2b')

        # Clear all : Remove all but latest version
        history_tools.clear_previous_history([master])
        master = self.TestHistoryTable(master.id)
        self.assertEqual(master.foo, 'v4')
        self.assertEqual([x.bar for x in master.childs], ['v2b'])

        assert_history(self.TestHistoryChildTable, 'bar', [(4, 'v2b')])

        # Test parent deletion
        master_id = master.id
        master.delete([master])
        transaction.commit()

        # Manually handle children field => Delete all children since parent
        # is dead
        history_tools.handle_field([], [master_id], {
                'model': self.TestHistoryChildTable,
                'reverse_field': 'parent'}, datetime.date.min, True)

        assert_history(self.TestHistoryChildTable, 'bar', [])
        assert_history(self.TestHistoryTable, 'foo', [
                (5, 'v4'), (6, None)])

        # Test history cleaning of dead entities
        history_tools.clear_previous_history(
            [self.TestHistoryTable(master_id)])
        assert_history(self.TestHistoryTable, 'foo', [])

    def test0030calculate_duration_between(self):
        start_date = datetime.date(2013, 1, 1)
        end_date = datetime.date(2013, 1, 31)
        self.assert_(coog_date.duration_between(start_date, end_date, 'day')
            == 31)
        self.assert_(coog_date.duration_between(start_date, end_date, 'month')
            == 1)
        self.assert_(coog_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (1, True))
        self.assert_(coog_date.duration_between(start_date, end_date,
                'quarter') == 0)
        self.assert_(coog_date.duration_between(start_date, end_date, 'year')
            == 0)

        end_date = datetime.date(2013, 3, 31)
        self.assert_(coog_date.duration_between(start_date, end_date, 'day')
            == 90)
        self.assert_(coog_date.duration_between(start_date, end_date, 'month')
            == 3)
        self.assert_(coog_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (3, True))
        self.assert_(coog_date.duration_between(start_date, end_date,
                'quarter') == 1)
        self.assert_(coog_date.duration_between_and_is_it_exact(start_date,
            end_date, 'quarter') == (1, True))
        self.assert_(coog_date.duration_between(start_date, end_date, 'year')
            == 0)

        end_date = datetime.date(2013, 12, 31)
        self.assert_(coog_date.duration_between(start_date, end_date, 'day')
            == 365)
        self.assert_(coog_date.duration_between(start_date, end_date, 'month')
            == 12)
        self.assert_(coog_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (12, True))
        self.assert_(coog_date.duration_between(start_date, end_date,
            'quarter') == 4)
        self.assert_(coog_date.duration_between_and_is_it_exact(start_date,
            end_date, 'quarter') == (4, True))
        self.assert_(coog_date.duration_between(start_date, end_date, 'year')
            == 1)
        self.assert_(coog_date.duration_between_and_is_it_exact(start_date,
            end_date, 'year') == (1, True))

        end_date = datetime.date(2014, 1, 1)
        self.assert_(coog_date.duration_between_and_is_it_exact(start_date,
            end_date, 'month') == (12, False))
        self.assert_(coog_date.duration_between_and_is_it_exact(start_date,
            end_date, 'year') == (1, False))

        start_date = datetime.date(2016, 2, 29)
        self.assertEqual(coog_date.add_duration(start_date, 'month', 1),
            datetime.date(2016, 3, 29))
        self.assertEqual(coog_date.add_duration(start_date, 'month', 1, True),
            datetime.date(2016, 3, 31))

        start_date = datetime.date(2015, 2, 28)
        self.assertEqual(coog_date.add_duration(start_date, 'year', 1),
            datetime.date(2016, 2, 28))
        self.assertEqual(coog_date.add_duration(start_date, 'year', 1, True),
            datetime.date(2016, 2, 29))

        start_date = datetime.date(2015, 2, 12)
        end_date = datetime.date(2016, 3, 10)
        self.assertEqual(coog_date.number_of_years_between(start_date,
                end_date), 1)
        self.assertEqual(coog_date.number_of_years_between(end_date,
                start_date), -1)
        self.assertEqual(coog_date.number_of_years_between(start_date,
                end_date, prorata_method=coog_date.prorata_365),
            1 + Decimal(28) / Decimal(365))

        # Test leap year
        start_date = datetime.date(2016, 2, 29)
        end_date = datetime.date(2017, 3, 27)
        self.assertEqual(coog_date.number_of_years_between(start_date,
                end_date, prorata_method=coog_date.prorata_365),
            1 + Decimal(28) / Decimal(365))
        # Test negative
        self.assertEqual(coog_date.number_of_years_between(end_date,
                start_date, prorata_method=coog_date.prorata_365),
            -1 - Decimal(28) / Decimal(365))

        self.assertEqual(coog_date.get_last_day_of_last_month(
            datetime.date(2016, 3, 15)), datetime.date(2016, 2, 29))

        # test exact prorata
        start_date = datetime.date(2015, 2, 12)
        end_date = datetime.date(2016, 3, 10)
        self.assertEqual(coog_date.number_of_years_between(start_date,
                end_date), 1)
        self.assertEqual(coog_date.number_of_years_between(end_date,
                start_date), -1)
        self.assertEqual(coog_date.number_of_years_between(start_date,
                end_date, prorata_method=coog_date.prorata_exact),
            1 + Decimal(28) / Decimal(366))

        # Test leap year
        start_date = datetime.date(2016, 2, 29)
        end_date = datetime.date(2017, 3, 27)
        self.assertEqual(coog_date.number_of_years_between(start_date,
                end_date, prorata_method=coog_date.prorata_exact),
            1 + Decimal(28) / Decimal(365))
        # Test negative
        self.assertEqual(coog_date.number_of_years_between(end_date,
                start_date, prorata_method=coog_date.prorata_exact),
            -1 - Decimal(28) / Decimal(365))

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
            __name__ = 'coog_core.test_model_revision_mixin'
            _parent_name = 'parent'
            parent = fields.Integer('Parent', required=True)
            value = fields.Integer('Value')

            @staticmethod
            def revision_columns():
                return ['value']

        class TestModelWithReverseField(ModelSQL, model._RevisionMixin):
            'Test RevisionMixin Model'
            __name__ = 'coog_core.test_model_revision_mixin'
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
        TestModel.__register__('coog_core')

        TestModelWithReverseField.__setup__()
        TestModelWithReverseField.__post_setup__()
        TestModelWithReverseField.__register__('coog_core')

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
        from trytond.pool import Pool

        method = self.MethodDefinition()
        self.assertEqual(method.get_possible_methods(), [])

        method.model = self.Model.search([
                ('model', '=', 'coog_core.test_model_method_definition')])[0]
        method.model.model = 'coog_core.test_model_method_definition'

        self.assertEqual(method.get_possible_methods(),
            [('good_one', 'good_one'), ('other_good_one', 'other_good_one')])
        method.method_name = 'good_one'

        callee = self.TestMethodDefinition()
        with mock.patch.object(Pool, 'get') as pool_get:
            pool_get.return_value = self.TestMethodDefinition
            self.assertEqual(method.execute(10, callee), 10)
            pool_get.assert_called_with(
                'coog_core.test_model_method_definition')

        method.id = 10
        with mock.patch.object(self.MethodDefinition, 'search') as search:
            search.return_value = [method]
            self.assertEqual(self.MethodDefinition.get_method(
                    'coog_core.test_model_method_definition', 'good_on'),
                method)
            search.assert_called_with([
                    ('model.model', '=',
                        'coog_core.test_model_method_definition'),
                    ('method_name', '=', 'good_on')])

    def test0050_export_import_key_not_unique(self):
        to_export = self.ExportTestTarget(char="sometext")
        to_export.save()
        duplicata = self.ExportTestTarget(char="sometext")
        duplicata.save()
        output = []
        to_export.export_json(output=output)

        self.assertRaises(UserError, self.ExportTestTarget.import_json,
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
            'some_dict': {},
        }

        to_export = self.ExportTest(**values)
        to_export.save()
        output = []
        to_export.export_json(output=output)

        values.update({'_func_key': 'somekey',
                '__name__': 'coog_core.export_test',
                'reference': None,
                'one2many': [],
                'multivalue_m2o': None,
                'multivalue_numeric': None,
                'multivalue_char': None,
                'multivalue_selection': None,
                'valid_one2many': [],
                'many2many': [],
                'many2one': None,
                })

        self.assertDictEqual(values, output[0])
        output[0]['text'] = 'someothertext'
        values['text'] = 'someothertext'
        self.ExportTest.import_json(output)
        output = []
        to_export.export_json(output=output)

        self.assertDictEqual(values, output[0])

    def test0052_export_import_many2one(self):
        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', many2one=target)
        to_export.save()
        output = []
        to_export.export_json(output=output)

        self.assertEqual(output[0]['_func_key'], 'key')
        self.assertEqual(output[1]['_func_key'], 'otherkey')

        output[0]['integer'] = 12

        self.ExportTest.import_json(output)
        self.assertEqual(12, to_export.many2one.integer)

    def test_0053_export_import_many2many(self):

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', many2many=[target])
        to_export.save()
        former = to_export.many2many
        output = []
        to_export.export_json(output=output)

        self.ExportTest.import_json(output)
        self.assertEqual(to_export.many2many, former)

    def test_0054_export_import_many2many_update(self):

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', many2many=[target])
        to_export.save()
        former_char = to_export.many2many[0].char
        output = []
        to_export.export_json(output=output)

        to_export.many2many = []
        to_export.save()

        self.ExportTestTarget.delete([target])

        self.ExportTest.import_json(output)
        self.assertEqual(to_export.many2many[0].char, former_char)

    def test_00542_export_import_many2many_remove(self):

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', many2many=[target])
        to_export.save()

        output = []
        to_export.export_json(output=output)
        output[1]['many2many'] = []

        self.ExportTest.import_json(output)
        self.assertEqual((), to_export.many2many)

    def test0056_export_import_reference_field(self):
        target = self.ExportTestTarget(char='key', integer=12)
        target.save()
        to_export = self.ExportTest(char='otherkey', reference=target)
        to_export.save()
        output = []
        to_export.export_json(output=output)
        output[0]['reference']['integer'] = 3

        self.ExportTest.import_json(output)
        self.assertEqual(3, to_export.reference.integer)

    def test_0057_export_import_one2many(self):

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', one2many=[target])
        to_export.save()
        former = to_export.one2many
        output = []
        to_export.export_json(output=output)

        self.ExportTest.import_json(output)
        self.assertEqual(to_export.one2many, former)

    def test_00571_export_import_one2many_update(self):

        target = self.ExportTestTargetSlave(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', valid_one2many=[target])
        to_export.save()
        output = []
        to_export.export_json(output=output)

        to_export.one2many = []
        to_export.save()
        self.ExportTestTargetSlave.delete([target])

        self.ExportTest.import_json(output)
        self.assertEqual(to_export.valid_one2many[0].char, 'key')

    def test_00572_export_import_one2many_no_update(self):
        # One2many to master object are not managed

        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', one2many=[target])
        to_export.save()
        output = []
        to_export.export_json(output=output)

        to_export.one2many = []
        to_export.save()
        self.ExportTestTarget.delete([target])

        self.ExportTest.import_json(output)
        self.assertEqual((), to_export.one2many)

    def test_00573_export_import_one2many_delete(self):
        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', one2many=[target])
        to_export.save()
        output = []
        to_export.export_json(output=output)

        output[1]['one2many'] = []

        self.ExportTest.import_json(output)
        self.assertEqual((), to_export.one2many)
        self.assertEqual([], self.ExportTestTarget.search(
                [('id', '!=', 0)]))

    def test_0058_export_import_multivalue_m2o(self):
        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', multivalue_m2o=target)
        to_export.save()
        output = []
        to_export.export_json(output=output)
        self.assertEqual(output[0]['_func_key'], 'key')
        self.assertEqual(output[1]['_func_key'], 'otherkey')

        output[0]['integer'] = 12

        self.ExportTest.import_json(output)
        self.assertEqual(12, to_export.multivalue_m2o.integer)

    def test_0059_export_import_multivalue_numeric(self):
        to_export = self.ExportTest(char='otherkey',
            multivalue_numeric=Decimal('1.5'))
        to_export.save()
        output = []
        to_export.export_json(output=output)

        self.assertEqual(output[0]['multivalue_numeric'], Decimal('1.5'))
        output[0]['multivalue_numeric'] = Decimal('3.2')

        self.ExportTest.import_json(output)
        self.assertEqual(Decimal('3.2'), to_export.multivalue_numeric)

    def test_0060_export_import_multivalue_char(self):
        to_export = self.ExportTest(char='otherkey', multivalue_char='Hello')
        to_export.save()
        output = []
        to_export.export_json(output=output)

        self.assertEqual(output[0]['multivalue_char'], 'Hello')

        output[0]['multivalue_char'] = 'hi'
        self.ExportTest.import_json(output)
        self.assertEqual('hi', to_export.multivalue_char)

    def test_0062_export_import_multivalue_selection(self):
        to_export = self.ExportTest(char='otherkey',
            multivalue_selection='select1')
        to_export.save()
        output = []
        to_export.export_json(output=output)

        self.assertEqual(output[0]['multivalue_selection'], 'select1')
        output[0]['multivalue_selection'] = 'select2'

        self.ExportTest.import_json(output)
        self.assertEqual('select2', to_export.multivalue_selection)

    def test_0063_export_import_configuration(self):
        model = self.Model.search([('model', '=', 'coog_core.export_test')])[0]
        model_configuration = self.ExportModelConfiguration(name='Export Test',
            code='export_test', model=model,
            model_name='coog_core.export_test')
        model_configuration.save()
        model_slave = self.Model.search(
            [('model', '=', 'coog_core.export_test_target_slave')])[0]
        model_configuration_slave = self.ExportModelConfiguration(
            name='Export Test Slave', code='export_test_slave',
            model=model_slave,
            model_name='coog_core.export_test_target_slave')
        model_configuration_slave.save()
        field_configuration = self.ExportFieldConfiguration(field_name='char',
            model=model_configuration, export_light_strategy=False)
        field_configuration.save()
        field_configuration = self.ExportFieldConfiguration(field_name='char',
            model=model_configuration_slave, export_light_strategy=False)
        field_configuration.save()
        conf = self.ExportConfiguration(name='MyConf', code='my_conf',
            models_configuration=[model_configuration,
                model_configuration_slave])

        target = self.ExportTestTargetSlave(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', valid_one2many=[target])
        to_export.save()
        output = []
        to_export.export_json(output=output, configuration=conf)
        self.assertEqual(output[0]['char'], 'otherkey')
        self.assertEqual(len(output[0]), 3)

        field_configuration = self.ExportFieldConfiguration(
            field_name='valid_one2many', model=model_configuration,
            export_light_strategy=False)
        field_configuration.save()
        output = []
        conf._configuration = None
        to_export.export_json(output=output, configuration=conf)
        self.assertEqual(output[0]['valid_one2many'][0]['char'], 'key')

        field_configuration.export_light_strategy = True
        field_configuration.save()
        output = []
        conf._configuration = None
        to_export.export_json(output=output, configuration=conf)
        self.assertEqual(len(output[0]['valid_one2many']), 1)

    def test0070_o2m_deletion(self):
        master = self.O2MMaster(test_one2many=[self.O2MChild(),
                self.O2MChild(), self.O2MChild()])
        master.save()
        self.assertEqual(len(self.O2MChild.search([
                        ('master', '=', master)])), 3)
        self.assertEqual(len(self.O2MChild.search([
                        ('master', '=', None)])), 0)
        last_elem = master.test_one2many[2]
        master.test_one2many = master.test_one2many[:2]
        self.assertEqual(master._save_values, {
                'test_one2many': [('delete', [last_elem.id])]})
        master.save()
        self.assertEqual(len(self.O2MChild.search([
                        ('master', '=', master)])), 2)
        self.assertEqual(len(self.O2MChild.search([
                        ('master', '=', None)])), 0)

    def test0080_apply_dict(self):
        target = self.ExportTestTarget(char='target')
        target.save()
        child1 = self.ExportTestTarget(char='child1')
        child1.save()
        child2 = self.ExportTestTarget(char='child2')
        child2.save()
        parent = self.ExportTest(char='parent', many2one=target,
            one2many=[child1, child2])
        parent.save()
        utils.apply_dict(parent, {'many2one': child1.id})
        self.assertEqual(parent.many2one.char, 'child1')

        parent = self.ExportTest(parent.id)
        self.assertEqual(parent.many2one.char, 'target')
        utils.apply_dict(parent, {'char': 'foo'})
        self.assertEqual(parent.char, 'foo')
        utils.apply_dict(parent, {'one2many':
                [('delete', [child1.id, child2.id])]})
        self.assertEqual(len(parent.one2many), 0)
        utils.apply_dict(parent, {'one2many':
                [('add', [child1.id, child2.id])]})
        self.assertEqual(len(parent.one2many), 2)
        utils.apply_dict(parent, {'one2many':
                [('create', [{'char': 'bar', 'many2one': target.id}])]})
        self.assertEqual(len(parent.one2many), 3)
        utils.apply_dict(parent, {'one2many':
                [('write', [child2.id], {'char': 'child2_tainted'})]})
        self.assertEqual(parent.one2many[1].char, 'child2_tainted')

        parent = self.ExportTest(parent.id)
        self.assertEqual(len(parent.one2many), 2)

    def test0100_loader_updater(self):
        test_instance = self.TestLoaderUpdater(real_field='foo')
        self.assertRaises(AttributeError,
            lambda: test_instance.normal_function)
        self.assertEqual('foo', test_instance.loader_field)
        self.assertEqual('foo', test_instance.loader_mixt_field)
        self.assertEqual('foo', test_instance.updater_field)
        test_instance.save()

        self.assertEqual('bar', test_instance.normal_function)
        self.assertEqual([{'id': 1, 'loader_mixt_field': 'bar'}],
            self.TestLoaderUpdater.read(
                [test_instance.id], ['loader_mixt_field']))
        self.assertEqual('foo', test_instance.loader_field)
        self.assertEqual('foo', test_instance.loader_mixt_field)
        self.assertEqual('foo', test_instance.updater_field)

        test_instance.updater_field = 'honey'
        self.assertEqual('bar', test_instance.normal_function)
        self.assertEqual([{'id': 1, 'loader_mixt_field': 'bar'}],
            self.TestLoaderUpdater.read(
                [test_instance.id], ['loader_mixt_field']))
        self.assertEqual('honey', test_instance.loader_field)
        self.assertEqual('honey', test_instance.loader_mixt_field)
        self.assertEqual('honey', test_instance.updater_field)
        self.assertEqual('honey', test_instance.real_field)

        test_instance.save()

        # get_field is a fake getter, so no surprise here
        self.assertEqual('bar', test_instance.normal_function)
        self.assertEqual([{'id': 1, 'loader_mixt_field': 'bar'}],
            self.TestLoaderUpdater.read(
                [test_instance.id], ['loader_mixt_field']))
        self.assertEqual('honey', test_instance.loader_field)
        self.assertEqual('honey', test_instance.loader_mixt_field)
        self.assertEqual('honey', test_instance.updater_field)
        self.assertEqual('honey', test_instance.real_field)

    def test_0110_history_table(self):
        cursor = Transaction().connection.cursor()

        master = self.TestHistoryTable(foo='1')
        master.save()
        Transaction().commit()

        master.foo = '2'
        master.save()
        Transaction().commit()

        self.assertRaises(AssertionError,
            self.TestHistoryTable._get_history_table)

        with Transaction().set_context(_datetime=datetime.datetime(2000, 1, 1,
                    0, 0, 0)):
            test_table = self.TestHistoryTable._get_history_table()
            cursor.execute(*test_table.select(test_table.id, test_table.foo,
                    where=test_table.id == master.id))
            self.assertEqual(cursor.fetchall(), [])

        with Transaction().set_context(_datetime=master.create_date):
            test_table = self.TestHistoryTable._get_history_table()
            cursor.execute(*test_table.select(test_table.id, test_table.foo,
                    where=test_table.id == master.id))
            self.assertEqual(cursor.fetchall(), [(master.id, u'1')])

        with Transaction().set_context(_datetime=master.write_date):
            test_table = self.TestHistoryTable._get_history_table()
            cursor.execute(*test_table.select(test_table.id, test_table.foo,
                    where=test_table.id == master.id))
            self.assertEqual(cursor.fetchall(), [(master.id, u'2')])

        child_1 = self.TestHistoryChildTable(bar='1', parent=master)
        child_1.save()
        Transaction().commit()
        child_date = child_1.create_date

        master.childs = []
        master.save()
        Transaction().commit()

        with Transaction().set_context(_datetime=master.create_date):
            test_table = self.TestHistoryTable._get_history_table()
            child_table = self.TestHistoryChildTable._get_history_table()
            cursor.execute(*test_table.join(child_table, type_='LEFT OUTER',
                    condition=(child_table.parent == test_table.id)
                ).select(test_table.id, test_table.foo, child_table.bar,
                    where=test_table.id == master.id))
            self.assertEqual(cursor.fetchall(), [(master.id, u'1', None)])

        with Transaction().set_context(_datetime=child_date):
            test_table = self.TestHistoryTable._get_history_table()
            child_table = self.TestHistoryChildTable._get_history_table()
            cursor.execute(*test_table.join(child_table, type_='LEFT OUTER',
                    condition=(child_table.parent == test_table.id)
                ).select(test_table.id, test_table.foo, child_table.bar,
                    where=test_table.id == master.id))
            self.assertEqual(cursor.fetchall(), [(master.id, u'2', u'1')])

        with Transaction().set_context(_datetime=master.write_date):
            test_table = self.TestHistoryTable._get_history_table()
            child_table = self.TestHistoryChildTable._get_history_table()
            cursor.execute(*test_table.join(child_table, type_='LEFT OUTER',
                    condition=(child_table.parent == test_table.id)
                ).select(test_table.id, test_table.foo, child_table.bar,
                    where=test_table.id == master.id))
            self.assertEqual(cursor.fetchall(), [(master.id, u'2', None)])

    def test_0115_calculate_periods_at_date(self):
        dates = [datetime.date(2012, 1, 1), datetime.date(2013, 1, 1),
            datetime.date(2013, 6, 6), datetime.date(2013, 9, 9),
            datetime.date(2014, 1, 1), datetime.date(2015, 1, 1)]
        period_start = dates[1]
        period_end = dates[-2]
        periods = coog_date.calculate_periods_from_dates(dates, period_start,
            period_end)
        periods_must_be = [
            (period_start, coog_date.add_day(dates[2], -1)),
            (dates[2], coog_date.add_day(dates[3], -1)),
            (dates[3], period_end),
            ]
        self.assertEqual(periods, periods_must_be)

    def test_0120_pre_commit_sub_transaction_behavior(self):
        from trytond.modules.coog_core import model

        inc = mock.Mock()

        class TestModel(ModelSQL, model._RevisionMixin):
            'Test Sub Transaction Model'
            __name__ = 'coog_core.test_model_sub_transaction'
            value = fields.Integer('Value')

        TestModel.__setup__()
        TestModel.__post_setup__()
        TestModel.__register__('coog_core')
        inc.increment = 0
        real_main_transaction = Transaction()

        real_main_transaction.commit()

        def some_substitute(*args):
            return 42

        DatabaseOperationalError = backend.get('DatabaseOperationalError')

        @model.pre_commit_transaction()
        def pre_commit_function(increment, crash_at=-1, inc_first=False,
                sub_transactions=None,
                exception_class=DatabaseOperationalError):
            if sub_transactions is None:
                sub_transactions = []
            ret, sub_transaction = sub_transaction_test_model(increment,
                crash_at, inc_first, exception_class)
            sub_transactions.append(sub_transaction)
            if isinstance(ret, Exception):
                raise ret

        @model.sub_transaction_retry(2, 10)
        def sub_transaction_test_model(increment, crash_at, inc_first,
                exception_class=DatabaseOperationalError):
            if inc_first:
                increment.increment += 1
            if increment.increment == crash_at:
                raise exception_class('Error')
            TestModel.create([{
                    'value': increment.increment
                    }])
            if not inc_first:
                increment.increment += 1

        self.assertEqual(len(TestModel.search([])), 0)

        with Transaction().new_transaction():
            ret = pre_commit_function(inc,
                substitute_hook=some_substitute)
            self.assertEqual(ret, 42)

        with Transaction().new_transaction():
            self.assertEqual(len(TestModel.search([])), 1)

        def commit_should_fail():
            with Transaction().new_transaction():
                self.assertEqual(len(TestModel.search([])), 1)
                # Create object and save it into the fake_main_transaction
                TestModel.create([{
                        'value': -99,
                        }])
                res = pre_commit_function(inc, crash_at=inc.increment)
                self.assertEqual(res, None)

        DatabaseOperationalError = backend.get('DatabaseOperationalError')
        self.assertRaises(DatabaseOperationalError, commit_should_fail)
        self.assertEqual(inc.increment, 1)
        # Sub transaction has fail and crashes it's main_transaction
        # which is the fake_main_transaction here.
        # So everything should have been rollbacked:
        # 1. The object created into the fake_main_transaction
        # 2. The objected created into the sub transaction of the delayed
        # method
        with Transaction().new_transaction():
            self.assertEqual(len(TestModel.search([])), 1)

        def commit_should_succeed_with_retry():
            # Here we check if the sub transaction retry
            # succeed after a failure
            with Transaction().new_transaction():
                self.assertEqual(len(TestModel.search([])), 1)
                # Create object and save it into the fake_main_transaction
                TestModel.create([{
                        'value': -99,
                        }])
                pre_commit_function(inc, crash_at=inc.increment + 1,
                    inc_first=True)

        commit_should_succeed_with_retry()
        self.assertEqual(inc.increment, 3)
        # Sub transaction has fail but incrementing first will allow the second
        # try to succeed, so the transactions will be committed with:
        # 1. The object created into the fake_main_transaction
        # 2. The objected created into the sub transaction of the delayed
        # method
        with Transaction().new_transaction():
            self.assertEqual(len(TestModel.search([])), 3)

        with Transaction().new_transaction():
            # check whether multiple call is working
            for x in range(10 - inc.increment, 0, -1):
                pre_commit_function(inc, inc_first=True)

        with Transaction().new_transaction():
            self.assertEqual(inc.increment, 10)

        def commit_should_fail_without_retry():
            # Here we check if the sub transaction fails without retrying
            # when an exception different from DatabaseOperationalError
            # is raised
            with Transaction().new_transaction():
                TestModel.create([{
                        'value': -99,
                        }])
                pre_commit_function(inc, crash_at=inc.increment + 1,
                    inc_first=True, exception_class=ZeroDivisionError)
        # ZeroDivisionError will be re-raised
        self.assertRaises(ZeroDivisionError,
            commit_should_fail_without_retry)
        # Because it has not retried, the increment in only incremented once
        self.assertEqual(inc.increment, 11)

    def test_0125_test_last_version_modified_before(self):
        l = []
        for x in range(0, 10):
            an_obj = mock.Mock()
            an_obj.val = x
            l.append(an_obj)
        single_list = [mock.Mock()]
        single_list[0].val = 42

        def key_func(x):
            return x.val

        r = utils.get_last_version_modified_before(single_list, single_list[0],
            less_than_key=key_func, compare_key=key_func, inclusive=True)

        self.assertEqual(r, single_list[0])

        r = utils.get_last_version_modified_before(single_list, single_list[0],
            less_than_key=key_func, compare_key=key_func, inclusive=False)

        self.assertEqual(r, None)

        # The list does not contains the element but the compare_key /
        # sort key is working well, so the higher value element of l should
        # be returned
        r = utils.get_last_version_modified_before(l, single_list[0],
            less_than_key=key_func, compare_key=key_func, inclusive=True)

        self.assertEqual(r, l[-1])

        # The list does not contains the element but the compare_key /
        # sort key is working well. No elements are matching and the call is
        # inclusive. But because the element is not in the list, it will not be
        # returned.
        single_list[0].val = -1
        r = utils.get_last_version_modified_before(l, single_list[0],
            less_than_key=key_func, compare_key=key_func, inclusive=True)

        self.assertEqual(r, None)

        single_list[0].value = 0
        r = utils.get_last_version_modified_before(l, l[3],
            less_than_key=key_func, compare_key=key_func, inclusive=True)

        # It is equivalent to l[3] But this is a representation of what happend
        # into the function: The selected records will be the first three objs
        # which are smaller than l[3] (l[0], l[1], l[2]) and it is including
        # the value l[3] => (l[0], l[1], l[2], l[3])
        # Because we want the bigger of the list, it will be the last element.
        self.assertEqual(r, l[0:4][-1])

        single_list[0].val = 0
        r = utils.get_last_version_modified_before(l, l[3],
            less_than_key=key_func, compare_key=key_func, inclusive=False)

        # See comment above
        self.assertEqual(r, l[0:3][-1])

        other_list = [mock.Mock(val=0), mock.Mock(val=3), mock.Mock(val=9)]
        values_with_duplicates = l + other_list

        r = utils.get_last_version_modified_before(
            values_with_duplicates, l[-1],
            less_than_key=key_func, compare_key=key_func, inclusive=True)

        self.assertEqual(r, sorted(values_with_duplicates, key=key_func,
            reverse=True)[1])

        only_duplicates = [mock.Mock(val=5) for x in range(0, 5)]

        r = utils.get_last_version_modified_before(
            only_duplicates, only_duplicates[-1],
            less_than_key=key_func, compare_key=key_func, inclusive=False)

        self.assertEqual(r, None)

        r = utils.get_last_version_modified_before(
            only_duplicates, only_duplicates[-1],
            less_than_key=key_func, compare_key=key_func, inclusive=True)

        self.assertEqual(r, only_duplicates[-1])

    def test_string_replace(self):
        s = u'café-THÉ:20$'

        self.assertEqual(coog_string.slugify(s, lower=False), u'cafe-THE_20_')
        self.assertEqual(coog_string.slugify(s), u'cafe-the_20_')
        self.assertEqual(coog_string.asciify(s), u'cafe-THE:20$')
        self.assertEqual(coog_string.slugify(s, '-'), u'cafe-the-20-')

    def test_event_type_action_pyson(self):
        good_obj = self.ExportTest(char='bingo',
            integer=12, boolean=True, some_dict={'one_value': 2})
        bad_obj = self.ExportTest(char='booh', integer=2,
            boolean=False, some_dict={'one_value': 3})
        empty_obj = self.ExportTest()

        conditions = ["Eval('char') == 'bingo'",
            "Eval('integer', 0) == 12",
            "Eval('integer', 0) > 10",
            "Eval('boolean', False) == True",
            "And(Eval('boolean', False) == True, Eval('integer', 0) == 12)",
            "Eval('some_dict', {}).get('one_value', 0) == 2"]

        for condition in conditions:
            action = self.EventTypeAction(
                pyson_condition=condition)
            res = action.filter_objects([good_obj, bad_obj, empty_obj])
            self.assertEqual(res, [good_obj], condition)

    def test_get_prorated_amount_on_period(self):
        sync_date = date(2011, 10, 21)
        frequency = 'monthly'
        value = Decimal(100)
        proportion = True
        for period, res_value in (
                ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 16), date(2014, 1, 31)), Decimal(100) *
                    Decimal(16) / Decimal(31)),
                ((date(2014, 1, 1), date(2014, 2, 28)), Decimal(200)),
                ((date(2014, 1, 1), date(2014, 3, 31)), Decimal(300)),
                ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(1200)),
                ((date(2014, 1, 15), date(2014, 2, 23)), Decimal(100) +
                    Decimal(100) * Decimal(9) / Decimal(28)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    proportion=proportion, frequency=frequency, value=value,
                    sync_date=sync_date), res_value)

        proportion = False
        for period, expected in (
                ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 16), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2014, 2, 28)), Decimal(200)),
                ((date(2014, 1, 1), date(2014, 3, 31)), Decimal(300)),
                ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(1200)),
                ((date(2014, 1, 15), date(2014, 2, 23)), Decimal(200)),
                ):
            res = utils.get_prorated_amount_on_period(*period,
                proportion=proportion, frequency=frequency, value=value,
                sync_date=sync_date)
            self.assertEqual(res, expected, 'Expected %s , got %s '
                    'for period %s ' % (expected, res, period))

        frequency = 'yearly'
        proportion = True
        for period, res_value in (
                ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2014, 1, 31)),
                    Decimal(100) * Decimal(31) / Decimal(365)),
                ((date(2014, 1, 1), date(2015, 12, 31)), Decimal(200)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    proportion=proportion, frequency=frequency, value=value,
                    sync_date=sync_date), res_value)

        proportion = False
        for period, expected in (
                ((date(2014, 1, 1), date(2014, 12, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2015, 1, 1)), Decimal(200)),
                ((date(2014, 1, 1), date(2015, 6, 1)), Decimal(200)),
                ):
            res = utils.get_prorated_amount_on_period(*period,
                proportion=proportion, frequency=frequency, value=value,
                sync_date=sync_date)
            self.assertEqual(res, expected, 'Expected %s , got %s '
                    'for period %s ' % (expected, res, period))

        proportion = True
        for period, res_value in (
                ((date(2015, 2, 1), date(2016, 1, 31)), Decimal(100)),
                ((date(2015, 3, 1), date(2016, 2, 29)), Decimal(100)),
                ((date(2016, 1, 1), date(2016, 1, 31)),
                    Decimal(100) * Decimal(31) / Decimal(365)),
                ((date(2017, 1, 1), date(2017, 1, 31)),
                    Decimal(100) * Decimal(31) / Decimal(366)),
                ((date(2016, 1, 1), date(2017, 1, 31)),
                    Decimal(100) +
                    Decimal(100) * Decimal(31) / Decimal(366)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    proportion=proportion, frequency=frequency, value=value,
                    sync_date=sync_date), res_value)

        frequency = 'once_per_contract'
        interval_start = date(2014, 1, 1)

        for period, res_value in (
                ((date(2014, 1, 1), date(2014, 1, 31)), Decimal(100)),
                ((date(2014, 1, 1), date(2015, 12, 31)), Decimal(100)),
                ((date(2014, 2, 1), date(2014, 2, 28)), Decimal(0)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    proportion=proportion, frequency=frequency, value=value,
                    sync_date=sync_date, interval_start=interval_start),
                res_value)

        frequency = 'at_contract_signature'
        value = Decimal(900)

        for period, res_value in (
                ((None, None), Decimal(900)),
                ((date(2014, 1, 1), date(2015, 12, 31)), Decimal(0)),
                ((date(2014, 2, 1), date(2014, 2, 28)), Decimal(0)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    proportion=proportion, frequency=frequency, value=value,
                    sync_date=sync_date), res_value)

        frequency = 'once_per_year'
        value = Decimal(100)

        for period, res_value in (
                ((date(2015, 10, 1), date(2015, 10, 22)), Decimal(100)),
                ((date(2015, 10, 1), date(2015, 10, 21)), Decimal(100)),
                ((date(2015, 10, 1), date(2015, 10, 20)), Decimal(0)),
                ((date(2015, 10, 1), date(2017, 10, 21)), Decimal(300)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    proportion=proportion), res_value)

        sync_date = date(2012, 2, 29)

        for period, res_value in (
                ((date(2015, 2, 1), date(2015, 3, 1)), Decimal(100)),
                ((date(2015, 2, 1), date(2015, 2, 28)), Decimal(100)),
                ((date(2015, 2, 1), date(2015, 2, 27)), Decimal(0)),
                ((date(2016, 2, 1), date(2016, 3, 1)), Decimal(100)),
                ((date(2016, 2, 1), date(2016, 2, 29)), Decimal(100)),
                ((date(2016, 2, 1), date(2016, 2, 28)), Decimal(0)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    proportion=proportion), res_value)

        frequency = 'monthly'
        value = Decimal(200)
        sync_date = date(2016, 11, 29)
        interval_start = date(2016, 11, 29)

        for period, res_value in (
                ((date(2016, 11, 29), date(2017, 11, 28)), Decimal(2400)),
                ((date(2016, 11, 29), date(2017, 2, 28)), Decimal(600)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    interval_start=interval_start, proportion=proportion),
                res_value)

        sync_date = date(2016, 11, 30)
        interval_start = date(2016, 11, 30)

        for period, res_value in (
                ((date(2016, 11, 30), date(2017, 11, 29)), Decimal(2400)),
                ((date(2016, 11, 30), date(2017, 2, 28)), Decimal(600)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    interval_start=interval_start, proportion=proportion),
                res_value)

        interval_start = date(2017, 1, 29)
        value = Decimal(30)
        sync_date = date(2016, 11, 30)

        for period, res_value in (
                ((date(2017, 1, 29), date(2017, 1, 31)), Decimal(3)),
                ((date(2017, 1, 29), date(2017, 1, 29)), Decimal(1)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    interval_start=interval_start, proportion=proportion),
                res_value)

        # This case is special. Since the reference date is March the 30th,
        # we assume that a period going from the 30th April to the 29th May is
        # a full month, even though the standard "follow end of month" would
        # make it a month minus one day.
        # The second test sets the reference date to February the 28th. In
        # that case, we apply the end month following rule, so the same period
        # from the 30th April to 29th May is not a full month.

        sync_date = date(2017, 3, 30)
        interval_start = date(2017, 4, 30)

        for period, res_value in (
                ((date(2017, 4, 30), date(2017, 5, 29)), Decimal(30)),
                ((date(2017, 5, 30), date(2017, 6, 29)), Decimal(30)),
                ((date(2018, 2, 28), date(2018, 3, 29)), Decimal(30)),
                ((date(2020, 2, 29), date(2020, 3, 29)), Decimal(30)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    interval_start=interval_start, proportion=proportion),
                res_value)

        value = Decimal(31)
        sync_date = date(2017, 2, 28)

        for period, res_value in (
                ((date(2017, 4, 30), date(2017, 5, 29)), Decimal(30)),
                ((date(2017, 5, 30), date(2017, 6, 29)), Decimal(31)),
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    interval_start=interval_start, proportion=proportion),
                res_value)

        proportion = True
        recursion = True
        frequency = 'quarterly'
        value = Decimal(300)
        sync_date = date(2017, 1, 1)
        interval_start = date(2017, 10, 1)
        for period, res_value in (
                ((date(2017, 11, 1), date(2017, 12, 31)), Decimal(200)),
                ((date(2017, 10, 1), date(2017, 12, 31)), Decimal(300)),
                ((date(2017, 11, 1), date(2017, 11, 30)), Decimal(100)),
                ((date(2017, 12, 1), date(2017, 12, 13)), Decimal(300) /
                    Decimal(3) * Decimal(13) / Decimal(31))
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    interval_start=interval_start, proportion=proportion,
                    recursion=recursion), res_value)

        recursion = False
        for period, res_value in (
                ((date(2017, 11, 1), date(2017, 12, 31)), Decimal(300) *
                    Decimal(61) / Decimal(92)),
                ((date(2017, 10, 1), date(2017, 12, 31)), Decimal(300)),
                ((date(2017, 11, 1), date(2017, 11, 30)), Decimal(300) *
                    Decimal(30) / Decimal(92)),
                ((date(2017, 12, 1), date(2017, 12, 13)), Decimal(300) *
                    Decimal(13) / Decimal(90))
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    interval_start=interval_start, proportion=proportion,
                    recursion=recursion), res_value)

        frequency = 'yearly'
        value = Decimal(1200)
        recursion = True
        interval_start = date(2017, 1, 1)
        for period, res_value in (
                ((date(2017, 1, 1), date(2017, 12, 31)), Decimal(1200)),
                ((date(2017, 1, 1), date(2017, 6, 30)), Decimal(600)),
                ((date(2017, 2, 1), date(2017, 2, 28)), Decimal(100)),
                ((date(2017, 12, 1), date(2017, 12, 13)), Decimal(1200)
                    / Decimal(12) * Decimal(13) / Decimal(31))
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    interval_start=interval_start, proportion=proportion,
                    recursion=recursion), res_value)

        recursion = False
        for period, res_value in (
                ((date(2017, 1, 1), date(2017, 12, 31)), Decimal(1200)),
                ((date(2017, 1, 1), date(2017, 6, 30)), Decimal(1200)
                    * Decimal(181) / Decimal(365)),
                ((date(2017, 2, 1), date(2017, 2, 28)), Decimal(1200)
                    * Decimal(28) / Decimal(365)),
                ((date(2017, 12, 1), date(2017, 12, 13)), Decimal(1200)
                    * Decimal(13) / Decimal(365))
                ):
            self.assertEqual(utils.get_prorated_amount_on_period(*period,
                    frequency=frequency, value=value, sync_date=sync_date,
                    interval_start=interval_start, proportion=proportion,
                    recursion=recursion), res_value)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
