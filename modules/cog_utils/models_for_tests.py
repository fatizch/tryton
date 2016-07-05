# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql.conditionals import Coalesce

from trytond.pool import PoolMeta, Pool
from trytond.model import DictSchemaMixin

import model
import export
import fields
import utils

__metaclass__ = PoolMeta

__all__ = [
    'TestMethodDefinitions',
    'TestDictSchema',
    'ExportTestTarget',
    'ExportTestTarget2',
    'ExportTestTargetSlave',
    'ExportTestTargetSlave2',
    'ExportTest',
    'ExportTestRelation',
    'O2MDeletionMaster',
    'O2MDeletionChild',
    'TestVersionedObject',
    'TestVersion',
    'TestVersion1',
    'TestHistoryTable',
    'TestHistoryChildTable',
    'TestLoaderUpdater',
    ]


class TestMethodDefinitions(model.CoopSQL):
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


class TestDictSchema(DictSchemaMixin, model.CoopSQL):
    'Test Dict Schema'
    __name__ = 'cog_utils.test.dict.schema'


class ExportTestTarget(model.CoopSQL, export.ExportImportMixin):
    'no doc'
    __name__ = 'cog_utils.export_test_target'
    _func_key = 'char'
    char = fields.Char('My field')


class ExportTestTargetSlave(model.CoopSQL, export.ExportImportMixin):
    'no doc'
    __name__ = 'cog_utils.export_test_target_slave'
    _func_key = 'char'
    char = fields.Char('My field')
    integer = fields.Integer('Integer')


class ExportTest(model.CoopSQL, export.ExportImportMixin):
    'Export Test'
    __name__ = 'cog_utils.export_test'
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
    many2one = fields.Many2One('cog_utils.export_test_target',
            'Many2One')
    many2many = fields.Many2Many('cog_utils.export_test_relation',
            'many2many', 'target', 'Many2Many')
    one2many = fields.One2Many('cog_utils.export_test_target', 'one2many',
            'One2Many')
    valid_one2many = fields.One2Many('cog_utils.export_test_target_slave',
        'one2many', 'Valid One2Many')
    reference = fields.Reference('Reference', [
            (None, ''),
            ('cog_utils.export_test_target', 'Target'),
            ])
    property_m2o = fields.Property(
        fields.Many2One('cog_utils.export_test_target', 'Property Many2One',
            domain=[('char', '=', 'key')]))
    property_numeric = fields.Property(fields.Numeric('Property Numeric'))
    property_char = fields.Property(fields.Char('Property Char'))
    property_selection = fields.Property(fields.Selection([
            (None, ''),
            ('select1', 'Select 1'),
            ('select2', 'Select 2'),
            ], 'Property Selection'))
    some_dict = fields.Dict('cog_utils.test.dict.schema', 'Dict')

    @classmethod
    def _export_light(cls):
        return set(['reference'])


class ExportTestTarget2:
    'no doc'
    __name__ = 'cog_utils.export_test_target'
    _func_key = 'char'
    char = fields.Char('My field')
    integer = fields.Integer('Integer')
    one2many = fields.Many2One('cog_utils.export_test', 'Export Data')
    many2one = fields.Many2One('cog_utils.export_test', 'Export Data')

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_light(cls):
        return set(['many2one'])


class ExportTestTargetSlave2:
    'no doc'
    __name__ = 'cog_utils.export_test_target_slave'
    _func_key = 'char'
    char = fields.Char('My field')
    one2many = fields.Many2One('cog_utils.export_test', 'Export Data')


class ExportTestRelation(model.CoopSQL, export.ExportImportMixin):
    "Export Data Many2Many"
    __name__ = 'cog_utils.export_test_relation'
    many2many = fields.Many2One('cog_utils.export_test', 'Export Data')
    target = fields.Many2One('cog_utils.export_test_target', 'Target')


class O2MDeletionMaster(model.CoopSQL):
    'O2M Deletion Master'

    __name__ = 'cog_utils.o2m_deletion_master_test'

    test_one2many = fields.One2Many('cog_utils.o2m_deletion_child_test',
        'master', 'Test One2Many', delete_missing=True)


class O2MDeletionChild(model.CoopSQL):
    'O2M Deletion Child'

    __name__ = 'cog_utils.o2m_deletion_child_test'

    master = fields.Many2One('cog_utils.o2m_deletion_master_test', 'Master')


class TestVersionedObject(model.CoopSQL):
    'Test Versioned Object'

    __name__ = 'cog_utils.test_version'

    versions = fields.One2Many('cog_utils.test_version.version', 'master',
        'Versions', delete_missing=True, order=[('start', 'ASC')])
    current_version = fields.Function(
        fields.Many2One('cog_utils.test_version.version', 'Current Version'),
        'get_current_version')
    version_field = fields.Function(
        fields.Char('Versioned Field'),
        'get_current_version')
    versions_1 = fields.One2Many('cog_utils.test_version.version1',
        'master_1', 'Versions 1', delete_missing=True,
        order=[('start_1', 'ASC')])
    current_version_1 = fields.Function(
        fields.Many2One('cog_utils.test_version.version1',
            'Current Version 1'),
        'get_current_version_1')
    current_version_1_version_field = fields.Function(
        fields.Char('Versioned Field'),
        'get_current_version_1')

    test_field = fields.Char('Test Field')

    @classmethod
    def default_versions(cls):
        return [Pool().get(
                'cog_utils.test_version.version').get_default_version()]

    @classmethod
    def default_versions_1(cls):
        return [Pool().get(
                'cog_utils.test_version.version1').get_default_version()]

    @classmethod
    def get_current_version(cls, instances, names):
        return utils.version_getter(instances, names,
            'cog_utils.test_version.version', 'master', utils.today(),
            field_map={'id': 'current_version'})

    @classmethod
    def get_current_version_1(cls, instances, names):
        return utils.version_getter(instances, names,
            'cog_utils.test_version.version1', 'master_1', utils.today(),
            date_field='start_1', field_map={
                'id': 'current_version_1', 'version_field':
                'current_version_1_version_field'})

    @fields.depends('versions_1', 'current_version_1_version_field')
    def on_change_current_version_1_version_field(self):
        version = self.get_version_1_at_date(utils.today())
        version.version_field = self.current_version_1_version_field
        self.versions_1 = self.versions_1

    @fields.depends('versions', 'version_field')
    def on_change_version_field(self):
        version = self.get_version_at_date(utils.today())
        version.version_field = self.version_field
        self.versions = self.versions

    def get_version_at_date(self, at_date):
        assert at_date
        for version in sorted(self.versions,
                key=lambda x: x.start or datetime.date.min, reverse=True):
            if (version.start or datetime.date.min) <= at_date:
                return version
        raise KeyError

    def get_version_1_at_date(self, at_date):
        assert at_date
        for version in sorted(self.versions_1,
                key=lambda x: x.start_1 or datetime.date.min, reverse=True):
            if (version.start_1 or datetime.date.min) <= at_date:
                return version
        raise KeyError


class TestVersion(model.CoopSQL):
    'Test Version'

    __name__ = 'cog_utils.test_version.version'

    master = fields.Many2One('cog_utils.test_version', 'Master', required=True,
        ondelete='CASCADE')
    start = fields.Date('Start')
    version_field = fields.Char('Version Field')

    @classmethod
    def order_start(cls, tables):
        table, _ = tables[None]
        return [Coalesce(table.start, datetime.date.min)]

    @classmethod
    def get_default_version(cls):
        return {
            'start': None,
            'version_field': 'Default Value',
            }


class TestVersion1(model.CoopSQL):
    'Test Version'

    __name__ = 'cog_utils.test_version.version1'

    master_1 = fields.Many2One('cog_utils.test_version', 'Master 1',
        required=True, ondelete='CASCADE')
    start_1 = fields.Date('Start 1')
    version_field = fields.Char('Version Field')

    @classmethod
    def order_start_1(cls, tables):
        table, _ = tables[None]
        return [Coalesce(table.start_1, datetime.date.min)]

    @classmethod
    def get_default_version(cls):
        return {
            'start_1': None,
            'version_field': 'Default Value 1',
            }


class TestHistoryTable(model.CoopSQL):
    'Test History'

    __name__ = 'cog_utils.test_history'
    _history = True

    foo = fields.Char('Foo')
    childs = fields.One2Many('cog_utils.test_history.child', 'parent',
        'Childs', delete_missing=True)


class TestHistoryChildTable(model.CoopSQL):
    'Test History Child Table'

    __name__ = 'cog_utils.test_history.child'
    _history = True

    parent = fields.Many2One('cog_utils.test_history', 'Parent',
        ondelete='CASCADE', required=True, select=True)
    bar = fields.Char('Bar')


class TestLoaderUpdater(model.CoopSQL):
    'Test Loader Updater'

    __name__ = 'cog_utils.test_loader_updater'

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
