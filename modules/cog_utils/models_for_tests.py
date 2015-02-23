# -*- coding: utf-8 -*-
from trytond.pool import PoolMeta

import model
import export
import fields

__metaclass__ = PoolMeta

__all__ = [
    'ExportTestTarget',
    'ExportTestTarget2',
    'ExportTestTargetSlave',
    'ExportTestTargetSlave2',
    'ExportTest',
    'ExportTestRelation',
    'O2MDeletionMaster',
    'O2MDeletionChild',
    ]


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
