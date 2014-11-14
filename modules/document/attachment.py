import base64

from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields, export

__metaclass__ = PoolMeta

__all__ = [
    'Attachment',
    ]


class Attachment(export.ExportImportMixin):
    __name__ = 'ir.attachment'

    document_desc = fields.Many2One('document.description',
        'Document Description', ondelete='SET NULL')

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['name']

    @classmethod
    def _export_light(cls):
        return (super(Attachment, cls)._export_light() |
            set(['resource', 'document_desc']))

    @classmethod
    def _export_skips(cls):
        return (super(Attachment, cls)._export_skips() |
            set(['digest', 'collision']))

    @classmethod
    def _import_ws_json(cls, values, main_object=None):
        if 'data' in values:
            values['data'] = base64.b64decode(values['data'])
        return super(Attachment, cls)._import_ws_json(values, main_object)

    def export_ws_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None):
        new_values = super(Attachment, self).export_ws_json(skip_fields,
            already_exported, output, main_object)
        new_values['data'] = base64.b64encode(self.data)
        return new_values

    @classmethod
    def search_for_export_import(cls, values):
        pool = Pool()
        if ('resource' not in values or '__name__' not in values['resource'] or
                'document_desc' not in values):
            return super(Attachment, cls).search_for_export_import(values)
        resource, = pool.get(values['resource']['__name__']).\
            search_for_export_import(values['resource'])
        return cls.search([
                ('resource', '=', '%s,%s' % (resource.__name__, resource.id)),
                ('document_desc.code', '=',
                    values['document_desc']['_func_key'])
               ])
