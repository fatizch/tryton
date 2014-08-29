import unittest
import datetime

from mock import Mock

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

        parent = Mock()
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


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModuleTestCase))
    return suite
