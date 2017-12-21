# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.tools import file_open
from trytond.model import ModelView, ModelSQL, ModelSingleton
from trytond.pyson import Eval

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Offered Configuration'
    __name__ = 'offered.configuration'

    use_default_style = fields.Boolean("Use Default Style",
        help="If checked, the report templates will use Coog's default style "
        "if there is no style defined on the product")
    style_template = fields.Binary('Default report style', states={
            'invisible': ~Eval('use_default_style')},
        depends=['use_default_style'])
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
