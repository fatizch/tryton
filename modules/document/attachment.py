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
    def __setup__(cls):
        super(Attachment, cls).__setup__()
        cls._error_messages.update({
                'can_t_decode_base64': "Can't decode attachment in base 64"
                })

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
    def _import_json(cls, values, main_object=None):
        if 'data' in values:
            try:
                values['data'] = base64.b64decode(values['data'])
            except Exception:
                cls.raise_user_error('can_t_decode_base64')
        return super(Attachment, cls)._import_json(values, main_object)

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None):
        new_values = super(Attachment, self).export_json(skip_fields,
            already_exported, output, main_object)
        new_values['data'] = base64.b64encode(self.data)
        return new_values

    @classmethod
    def search_for_export_import(cls, values):
        pool = Pool()
        if ('resource' not in values or '__name__' not in values['resource'] or
                'document_desc' not in values):
            return super(Attachment, cls).search_for_export_import(values)
        resources = pool.get(values['resource']['__name__']).\
            search_for_export_import(values['resource'])
        if len(resources) != 1:
            cls.raise_user_error("Can't find object %s %s" % (
                values['resource']['__name__'],
                values['resource']['_func_key']))
        return cls.search([
                ('resource', '=', '%s,%s' % (resources[0].__name__,
                    resources[0].id)),
                ('document_desc.code', '=',
                    values['document_desc']['_func_key'])
                ])
