# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import DictSchemaMixin
from trytond.modules.company.model import (CompanyValueMixin,
    CompanyMultiValueMixin)

import model
import export
import fields

__metaclass__ = PoolMeta

__all__ = [
    'TestMethodDefinitions',
    'TestDictSchema',
    'ExportTestM2O',
    'ExportTestNumeric',
    'ExportTestChar',
    'ExportTestSelection',
    'ExportTestTarget',
    'ExportTestTarget2',
    'ExportTestTargetSlave',
    'ExportTestTargetSlave2',
    'ExportTest',
    'ExportTestRelation',
    'O2MDeletionMaster',
    'O2MDeletionChild',
    'TestHistoryTable',
    'TestHistoryChildTable',
    'TestLoaderUpdater',
    ]


class TestMethodDefinitions(model.CoogSQL):
    'Test Method Definition Model'
    __name__ = 'coog_core.test_model_method_definition'

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


class TestDictSchema(DictSchemaMixin, model.CoogSQL):
    'Test Dict Schema'
    __name__ = 'coog_core.test.dict.schema'


class ExportTestTarget(model.CoogSQL, export.ExportImportMixin):
    'no doc'
    __name__ = 'coog_core.export_test_target'
    _func_key = 'char'
    char = fields.Char('My field')


class ExportTestTargetSlave(model.CoogSQL, export.ExportImportMixin):
    'no doc'
    __name__ = 'coog_core.export_test_target_slave'
    _func_key = 'char'
    char = fields.Char('My field')
    integer = fields.Integer('Integer')


class ExportTest(model.CoogSQL, export.ExportImportMixin,
        CompanyMultiValueMixin):
    'Export Test'
    __name__ = 'coog_core.export_test'
    _func_key = 'char'
    boolean = fields.Boolean('Boolean')
    integer = fields.Integer('Integer')
    float = fields.Float('Float')
    numeric = fields.Numeric('Numeric')
    char = fields.Char('Char')
    text = fields.Text('Text')
    date = fields.Date('Date')
    datetime = fields.DateTime('DateTime')
    selection = fields.Selection([
            (None, ''),
            ('select1', 'Select 1'),
            ('select2', 'Select 2'),
            ], 'Selection')
    many2one = fields.Many2One('coog_core.export_test_target',
            'Many2One')
    many2many = fields.Many2Many('coog_core.export_test_relation',
            'many2many', 'target', 'Many2Many')
    one2many = fields.One2Many('coog_core.export_test_target', 'one2many',
            'One2Many')
    valid_one2many = fields.One2Many('coog_core.export_test_target_slave',
        'one2many', 'Valid One2Many')
    reference = fields.Reference('Reference', [
            (None, ''),
            ('coog_core.export_test_target', 'Target'),
            ])
    multivalue_m2o = fields.MultiValue(
        fields.Many2One('coog_core.export_test_target', 'Property Many2One',
            domain=[('char', '=', 'key')]))
    multivalue_numeric = fields.MultiValue(fields.Numeric('Multivalue Numeric'))
    multivalue_char = fields.MultiValue(fields.Char('Multivalue Char'))
    multivalue_selection = fields.MultiValue(fields.Selection([
            (None, ''),
            ('select1', 'Select 1'),
            ('select2', 'Select 2'),
            ], 'Property Selection'))
    some_dict = fields.Dict('coog_core.test.dict.schema', 'Dict')

    @classmethod
    def _export_light(cls):
        return set(['reference'])


class ExportTestM2O(model.CoogSQL, CompanyValueMixin):
    'Export Test M2O'
    __name__ = 'coog_core.export_test.multivalue_m2o'

    export_test = fields.Many2One('coog_core.export_test', 'Configuration',
        ondelete='CASCADE', select=True)
    multivalue_m2o = fields.Many2One('coog_core.export_test_target',
        'Property Many2One', domain=[('char', '=', 'key')])


class ExportTestNumeric(model.CoogSQL, CompanyValueMixin):
    'Export Test Numeric'
    __name__ = 'coog_core.export_test.multivalue_numeric'

    export_test = fields.Many2One('coog_core.export_test', 'Configuration',
        ondelete='CASCADE', select=True)
    multivalue_numeric = fields.Numeric('Multivalue Numeric')


class ExportTestChar(model.CoogSQL, CompanyValueMixin):
    'Export Test Char'
    __name__ = 'coog_core.export_test.multivalue_char'

    export_test = fields.Many2One('coog_core.export_test', 'Configuration',
        ondelete='CASCADE', select=True)
    multivalue_char = fields.Char('Multivalue Char')


class ExportTestSelection(model.CoogSQL, CompanyValueMixin):
    'Export Test Selection'
    __name__ = 'coog_core.export_test.multivalue_selection'

    export_test = fields.Many2One('coog_core.export_test', 'Configuration',
        ondelete='CASCADE', select=True)
    multivalue_selection = fields.Char('Multivalue Selection')


class ExportTestTarget2:
    'no doc'
    __name__ = 'coog_core.export_test_target'
    _func_key = 'char'
    char = fields.Char('My field')
    integer = fields.Integer('Integer')
    one2many = fields.Many2One('coog_core.export_test', 'Export Data')
    many2one = fields.Many2One('coog_core.export_test', 'Export Data')

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return set(['many2one'])


class ExportTestTargetSlave2:
    'no doc'
    __name__ = 'coog_core.export_test_target_slave'
    _func_key = 'char'
    char = fields.Char('My field')
    one2many = fields.Many2One('coog_core.export_test', 'Export Data')


class ExportTestRelation(model.CoogSQL, export.ExportImportMixin):
    "Export Data Many2Many"
    __name__ = 'coog_core.export_test_relation'
    many2many = fields.Many2One('coog_core.export_test', 'Export Data')
    target = fields.Many2One('coog_core.export_test_target', 'Target')


class O2MDeletionMaster(model.CoogSQL):
    'O2M Deletion Master'

    __name__ = 'coog_core.o2m_deletion_master_test'

    test_one2many = fields.One2Many('coog_core.o2m_deletion_child_test',
        'master', 'Test One2Many', delete_missing=True)


class O2MDeletionChild(model.CoogSQL):
    'O2M Deletion Child'

    __name__ = 'coog_core.o2m_deletion_child_test'

    master = fields.Many2One('coog_core.o2m_deletion_master_test', 'Master')


class TestHistoryTable(model.CoogSQL):
    'Test History'

    __name__ = 'coog_core.test_history'
    _history = True

    foo = fields.Char('Foo')
    childs = fields.One2Many('coog_core.test_history.child', 'parent',
        'Childs', delete_missing=True)


class TestHistoryChildTable(model.CoogSQL):
    'Test History Child Table'

    __name__ = 'coog_core.test_history.child'
    _history = True

    parent = fields.Many2One('coog_core.test_history', 'Parent',
        ondelete='CASCADE', required=True, select=True)
    bar = fields.Char('Bar')


class TestLoaderUpdater(model.CoogSQL):
    'Test Loader Updater'

    __name__ = 'coog_core.test_loader_updater'

    real_field = fields.Char('Real Field')
    normal_function = fields.Function(
        fields.Char('Normal Function'),
        'get_field')
    loader_field = fields.Function(
        fields.Char('Loader Field'),
        loader='load_field')
    loader_mixt_field = fields.Function(
        fields.Char('Loader Field'),
        getter='get_field', loader='load_field')
    updater_field = fields.Function(
        fields.Char('Updater Field'),
        loader='load_field', updater='update_field')

    def get_field(self, name):
        return 'bar'

    def load_field(self):
        return self.real_field

    def update_field(self, value):
        self.real_field = value
