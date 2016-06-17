# -*- coding: utf-8 -*-
import unittest
import datetime
import mock
from decimal import Decimal

from sql import Column

import trytond.tests.test_tryton
from trytond.model import ModelSQL, fields
from trytond.transaction import Transaction
from trytond.exceptions import UserError

from trytond.modules.cog_utils import test_framework, history_tools
from trytond.modules.cog_utils import utils, coop_string, coop_date, model


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'cog_utils'

    @classmethod
    def get_models(cls):
        return {
            'View': 'ir.ui.view',
            'TestMethodDefinition': 'cog_utils.test_model_method_definition',
            'MethodDefinition': 'ir.model.method',
            'Model': 'ir.model',
            'ExportTest': 'cog_utils.export_test',
            'ExportTestTarget': 'cog_utils.export_test_target',
            'ExportTestTargetSlave': 'cog_utils.export_test_target_slave',
            'ExportTestRelation': 'cog_utils.export_test_relation',
            'O2MMaster': 'cog_utils.o2m_deletion_master_test',
            'O2MChild': 'cog_utils.o2m_deletion_child_test',
            'ExportModelConfiguration': 'ir.export.configuration.model',
            'ExportConfiguration': 'ir.export.configuration',
            'ExportFieldConfiguration': 'ir.export.configuration.field',
            'VersionedObject': 'cog_utils.test_version',
            'Version': 'cog_utils.test_version.version',
            'Version1': 'cog_utils.test_version.version1',
            'EventTypeAction': 'event.type.action',
            'TestHistoryTable': 'cog_utils.test_history',
            'TestHistoryChildTable': 'cog_utils.test_history.child',
            'TestLoaderUpdater': 'cog_utils.test_loader_updater',
            }

    def test0020get_module_path(self):
        self.assert_(utils.get_module_path('cog_utils'))
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

        start_date = datetime.date(2016, 2, 29)
        self.assertEqual(coop_date.add_duration(start_date, 'month', 1),
            datetime.date(2016, 3, 29))
        self.assertEqual(coop_date.add_duration(start_date, 'month', 1, True),
            datetime.date(2016, 3, 31))

        start_date = datetime.date(2015, 2, 28)
        self.assertEqual(coop_date.add_duration(start_date, 'year', 1),
            datetime.date(2016, 2, 28))
        self.assertEqual(coop_date.add_duration(start_date, 'year', 1, True),
            datetime.date(2016, 2, 29))

        start_date = datetime.date(2015, 2, 12)
        end_date = datetime.date(2016, 3, 10)
        self.assertEqual(coop_date.number_of_years_between(start_date,
                end_date), 1)
        self.assertEqual(coop_date.number_of_years_between(end_date,
                start_date), -1)
        self.assertEqual(coop_date.number_of_years_between(start_date,
                end_date, prorata_method=coop_date.prorata_365),
            1 + Decimal(28) / Decimal(365))

        # Test leap year
        start_date = datetime.date(2016, 2, 29)
        end_date = datetime.date(2017, 3, 27)
        self.assertEqual(coop_date.number_of_years_between(start_date,
                end_date, prorata_method=coop_date.prorata_365),
            1 + Decimal(28) / Decimal(365))
        # Test negative
        self.assertEqual(coop_date.number_of_years_between(end_date,
                start_date, prorata_method=coop_date.prorata_365),
            -1 - Decimal(28) / Decimal(365))

        self.assertEqual(coop_date.get_last_day_of_last_month(
            datetime.date(2016, 3, 15)), datetime.date(2016, 2, 29))

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
        method = self.MethodDefinition()
        self.assertEqual(method.get_possible_methods(), [])

        method.model = self.Model.search([
                ('model', '=', 'cog_utils.test_model_method_definition')])[0]
        method.model.model = 'cog_utils.test_model_method_definition'

        self.assertEqual(method.get_possible_methods(),
            [('good_one', 'good_one'), ('other_good_one', 'other_good_one')])
        method.method_name = 'good_one'

        callee = self.TestMethodDefinition()
        with mock.patch.object(trytond.tests.test_tryton.POOL,
                'get') as pool_get:
            pool_get.return_value = self.TestMethodDefinition
            self.assertEqual(method.execute(10, callee), 10)
            pool_get.assert_called_with(
                'cog_utils.test_model_method_definition')

        method.id = 10
        with mock.patch.object(self.MethodDefinition, 'search') as search:
            search.return_value = [method]
            self.assertEqual(self.MethodDefinition.get_method(
                    'cog_utils.test_model_method_definition', 'good_on'),
                method)
            search.assert_called_with([
                    ('model.model', '=',
                        'cog_utils.test_model_method_definition'),
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
                '__name__': 'cog_utils.export_test',
                'reference': None,
                'one2many': [],
                'property_m2o': None,
                'property_numeric': None,
                'property_char': None,
                'property_selection': None,
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

    def test_0058_export_import_property_m2o(self):
        target = self.ExportTestTarget(char='key')
        target.save()
        to_export = self.ExportTest(char='otherkey', property_m2o=target)
        to_export.save()
        output = []
        to_export.export_json(output=output)

        self.assertEqual(output[0]['_func_key'], 'key')
        self.assertEqual(output[1]['_func_key'], 'otherkey')

        output[0]['integer'] = 12

        self.ExportTest.import_json(output)
        self.assertEqual(12, to_export.property_m2o.integer)

    def test_0059_export_import_property_numeric(self):
        to_export = self.ExportTest(char='otherkey', property_numeric='1.5')
        to_export.save()
        output = []
        to_export.export_json(output=output)

        self.assertEqual(output[0]['property_numeric'], Decimal('1.5'))
        output[0]['property_numeric'] = Decimal('3.2')

        self.ExportTest.import_json(output)
        self.assertEqual(Decimal('3.2'), to_export.property_numeric)

    def test_0060_export_import_property_char(self):
        to_export = self.ExportTest(char='otherkey', property_char='Hello')
        to_export.save()
        output = []
        to_export.export_json(output=output)

        self.assertEqual(output[0]['property_char'], 'Hello')

        output[0]['property_char'] = 'hi'
        self.ExportTest.import_json(output)
        self.assertEqual('hi', to_export.property_char)

    def test_0062_export_import_property_selection(self):
        to_export = self.ExportTest(char='otherkey',
            property_selection='select1')
        to_export.save()
        output = []
        to_export.export_json(output=output)

        self.assertEqual(output[0]['property_selection'], 'select1')
        output[0]['property_selection'] = 'select2'

        self.ExportTest.import_json(output)
        self.assertEqual('select2', to_export.property_selection)

    def test_0063_export_import_configuration(self):
        model = self.Model.search([('model', '=', 'cog_utils.export_test')])[0]
        model_configuration = self.ExportModelConfiguration(name='Export Test',
            code='export_test', model=model,
            model_name='cog_utils.export_test')
        model_configuration.save()
        model_slave = self.Model.search(
            [('model', '=', 'cog_utils.export_test_target_slave')])[0]
        model_configuration_slave = self.ExportModelConfiguration(
            name='Export Test Slave', code='export_test_slave',
            model=model_slave,
            model_name='cog_utils.export_test_target_slave')
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

    def test0090_version_management(self):
        master = self.VersionedObject(test_field='Master')
        master.save()

        # Check default versions
        self.assertEqual(len(master.versions), 1)
        self.assertEqual(master.versions[0].version_field, 'Default Value')
        self.assertEqual(len(master.versions_1), 1)
        self.assertEqual(master.versions_1[0].version_field, 'Default Value 1')

        # Check current version getter does not crash with no version
        master.versions = []
        master.versions_1 = []
        master.save()
        self.assertEqual(master.current_version, None)
        self.assertEqual(master.current_version_1, None)

        master.versions = [self.Version(version_field='Child 1')]
        master.save()

        # Check only first versioned field is updated
        self.assertEqual(master.current_version, master.versions[0])
        self.assertEqual(master.current_version_1, None)

        before_today = coop_date.add_day(utils.today(), -1)
        master.versions_1 = [self.Version1(version_field='Child 2'),
            self.Version1(version_field='Child 3', start_1=before_today)]
        master.save()

        self.assertEqual(master.current_version, master.versions[0])
        self.assertEqual(master.current_version_1, master.versions_1[1])

        after_today = coop_date.add_day(utils.today(), 1)
        master.versions = [self.Version(version_field='Child 4',
                start=after_today)] + list(master.versions)
        master.save()

        # Check ordering
        self.assertEqual([x.version_field for x in master.versions], [
                'Child 1', 'Child 4'])

        # Check versioning
        self.assertEqual(master.current_version, master.versions[0])

        some_date = coop_date.add_day(utils.today(), -20)
        master.versions = [self.Version(version_field='Child 5',
                start=some_date)] + list(master.versions)
        master.versions_1 = [self.Version1(version_field='Child 6',
                start_1=some_date)] + list(master.versions_1)

        # Check get_version_at_date before saving / ordering
        self.assertEqual(master.get_version_at_date(some_date).version_field,
            'Child 5')
        self.assertEqual(
            master.get_version_1_at_date(some_date).version_field, 'Child 6')

        master.save()
        # Check get_version_at_date after saving / ordering
        self.assertEqual(master.get_version_at_date(some_date).version_field,
            'Child 5')
        self.assertEqual(
            master.get_version_1_at_date(some_date).version_field, 'Child 6')

        # Check _get_version_fields_at_date
        self.assertEqual(master.current_version_1_version_field, 'Child 3')
        self.assertEqual(utils.version_getter([master], ['version_field'],
                'cog_utils.test_version.version1', 'master_1', some_date,
                date_field='start_1'),
            {'version_field': {master.id: 'Child 6'}})

        # Check field update
        self.assertEqual(master.current_version.version_field, 'Child 5')
        master.version_field = 'Updated Child'
        master.on_change_version_field()
        self.assertEqual(master.get_version_at_date(
                utils.today()).version_field, 'Updated Child')

        self.assertEqual(master.current_version_1.version_field, 'Child 3')
        master.current_version_1_version_field = 'Updated Child 1'
        master.on_change_current_version_1_version_field()
        self.assertEqual(master.get_version_1_at_date(
                utils.today()).version_field, 'Updated Child 1')

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

    def test_string_replace(self):
        s = u'café-THÉ:20$'

        self.assertEqual(coop_string.slugify(s, lower=False), u'cafe-THE_20_')
        self.assertEqual(coop_string.slugify(s), u'cafe-the_20_')
        self.assertEqual(coop_string.asciify(s), u'cafe-THE:20$')
        self.assertEqual(coop_string.slugify(s, '-'), u'cafe-the-20-')

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

    def test_filter_at_date(self):
        def create_version_since(since_days):
            return self.Version(val=str(since_days),
                start_date=coop_date.add_day(utils.today(), since_days),
                end_date=utils.today())

        l = [create_version_since(-2),
            create_version_since(-10),
            create_version_since(-1),
        ]
        self.assertEqual(utils.filter_list_at_date(l,
            at_date=coop_date.add_day(utils.today(), -2)), l[:-1])
        self.assertEqual(utils.filter_list_at_date(l,
            at_date=coop_date.add_day(utils.today(), -11)), [])
        self.assertEqual(utils.filter_list_at_date(l,
            at_date=utils.today()), l)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ModuleTestCase))
    return suite
