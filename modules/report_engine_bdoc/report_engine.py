# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.config import config

from trytond.modules.coog_core import fields

__all__ = [
    'ReportTemplate',
    'ReportGenerate',
    'ReportTemplateVersion',
    ]


class ReportTemplate(metaclass=PoolMeta):
    __name__ = 'report.template'

    @classmethod
    def __setup__(cls):
        super(ReportTemplate, cls).__setup__()
        cls.format_for_internal_edm.states = {
            'invisible': (Eval('input_kind') == 'bdoc') |
                         (Eval('input_kind') == 'shared_genshi_template')}
        cls.export_dir.states = {
            'invisible': (Eval('input_kind') == 'bdoc')}
        cls.modifiable_before_printing.states = {
            'invisible': (Eval('input_kind') == 'bdoc') |
                         (Eval('input_kind') == 'shared_genshi_template')}

    @classmethod
    def get_possible_input_kinds(cls):
        return super().get_possible_input_kinds() + [
            ('bdoc', 'BDOC'),
        ]

    @fields.depends('input_kind', 'possible_process_methods', 'versions')
    def on_change_input_kind(self):
        super().on_change_input_kind()
        if self.input_kind == 'bdoc':
            self.export_dir = ''
            for version in self.versions:
                version.is_shared_template = True

    def get_export_dirname(self):
        if self.input_kind == 'bdoc':
            return config.get('bdoc', 'export_root_dir', default='/export_dir')
        return super().get_export_dirname()

    @fields.depends('input_kind')
    def get_possible_process_methods(self):
        if self.input_kind == 'bdoc':
            return [('bdoc', 'BDOC')]
        else:
            return super().get_possible_process_methods()

    def _must_export_generated_file(self):
        if self.input_kind == 'bdoc':
            return True
        return super()._must_export_generated_file()


class ReportGenerate(metaclass=PoolMeta):
    __name__ = 'report.generate'

    @classmethod
    def process_bdoc(cls, ids, data):
        return cls.process_shared_genshi_template(ids, data)


class ReportTemplateVersion(metaclass=PoolMeta):
    __name__ = 'report.template.version'

    @fields.depends('template')
    def on_change_template(self):
        if self.template:
            self.is_shared_template = self.template.input_kind in [
                'shared_genshi_template', 'bdoc']
