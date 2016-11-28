# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta

__all__ = [
    'Attachment',
    ]


class Attachment:
    __name__ = 'ir.attachment'

    document_desc = fields.Many2One('document.description',
        'Document Description', ondelete='SET NULL')

    @classmethod
    def search(cls, domain, *args, **kwargs):
        # Never search any document for which the user is not allowed to view
        # the type
        document_descs = Pool().get('document.description').search([])
        domain = ['AND', domain,
            ['OR', ('document_desc', '=', None),
                ('document_desc', 'in', [x.id for x in document_descs])]]
        return super(Attachment, cls).search(domain, *args, **kwargs)

    @classmethod
    def search_for_export_import(cls, values):
        pool = Pool()
        if '_func_key' in values:
            return super(Attachment, cls).search_for_export_import(values)

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
