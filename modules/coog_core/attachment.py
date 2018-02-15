# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.cache import Cache
from trytond.ir.resource import ResourceMixin
import utils
import fields
import export


__all__ = [
    'Attachment',
    ]


class Attachment(export.ExportImportMixin):
    __name__ = 'ir.attachment'
    _func_key = 'func_key'

    origin = fields.Reference('Origin',
        selection='get_possible_origin', select=True)
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    _models_get_cache = Cache('models_get_cache')

    @classmethod
    def is_master_object(cls):
        return True

    def get_func_key(self, name):
        return '%s|%s' % (self.name, self.resource)

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                name, resource = clause[2].split('|')
                return [('name', clause[1], name),
                    ('resource', clause[1], resource)]
            else:
                return [('id', '=', None)]
        else:
            return [('id', '=', None)]

    @staticmethod
    def get_models():
        result = Attachment._models_get_cache.get('get_models', None)
        if result is None:
            result = ResourceMixin.get_models()
            Attachment._models_get_cache.set('get_models', result)
        return result

    @classmethod
    def get_possible_origin(cls):
        return utils.models_get()

    @classmethod
    def __setup__(cls):
        super(Attachment, cls).__setup__()
        cls._export_binary_fields.add('data')

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['name']

    @classmethod
    def _export_light(cls):
        return (super(Attachment, cls)._export_light() |
            set(['resource', 'document_desc', 'origin']))

    @classmethod
    def _export_skips(cls):
        return (super(Attachment, cls)._export_skips() |
            set(['digest', 'collision']))
