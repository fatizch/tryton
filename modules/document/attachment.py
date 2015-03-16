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
    origin = fields.Reference('Origin',
        selection='get_possible_origin', select=True)

    @classmethod
    def get_possible_origin(cls):
        res = cls.models_get()
        res.append(('', ''))
        return res

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
            set(['resource', 'document_desc', 'origin']))

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
            output=None, main_object=None, configuration=None):
        new_values = super(Attachment, self).export_json(skip_fields,
            already_exported, output, main_object, configuration)
        if not configuration or 'data' in new_values:
            new_values['data'] = base64.b64encode(self.data)
        return new_values

    @classmethod
    def search_for_export_import(cls, values):
        pool = Pool()

        def domain_by_attribute_name(attribute_name):
            attribute_present = (attribute_name in values and
                values[attribute_name])
            if not attribute_present:
                return []
            assert '__name__' in values[attribute_name]

            attributes = pool.get(values[attribute_name]['__name__']).\
                search_for_export_import(values[attribute_name])
            if len(attributes) != 1:
                cls.raise_user_error("Can't find object %s %s" % (
                    values[attribute_name]['__name__'],
                    values[attribute_name]['_func_key']))
            domain_res = [
                    (attribute_name, '=', '%s,%s' % (attributes[0].__name__,
                        attributes[0].id))
                    ]
            return domain_res

        if 'document_desc' in values:
            my_domain = [
                ('document_desc.code', '=',
                    values['document_desc']['_func_key'])]
        else:
            my_domain = []

        for attribute_name in ['resource', 'origin']:
            dom = domain_by_attribute_name(attribute_name)
            if dom:
                my_domain.extend(dom)

        if my_domain:
            return cls.search(my_domain)
        return super(Attachment, cls).search_for_export_import(values)
