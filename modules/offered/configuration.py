# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.tools import file_open
from trytond.model import ModelView, ModelSQL, ModelSingleton
__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Offered Configuration'
    __name__ = 'offered.configuration'

    style_template = fields.Binary('Default report style')
    path = fields.Function(fields.Char('Path'),
        'get_path', setter='setter_default_report_style_template')

    def get_path(self, name):
        return ''

    @classmethod
    def setter_default_report_style_template(cls, instances, name, value):
        if value:
            with file_open(value, 'rb') as template_file:
                cls.write(instances, {'style_template': template_file.read()})
        else:
            cls.write(instances, {'style_template': None})
