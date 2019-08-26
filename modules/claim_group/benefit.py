# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, coog_string

__all__ = [
    'Benefit',
    ]


class Benefit(metaclass=PoolMeta):
    __name__ = 'benefit'

    is_group = fields.Boolean('Group Benefit',
        help='Define if the benefit is available only for a group coverage')

    @classmethod
    def get_beneficiary_kind(cls):
        return super(Benefit, cls).get_beneficiary_kind() + [
            ('subscriber_then_covered',
                gettext('claim_group.msg_subscriber_then_covered_enum')),
            ]

    def get_documentation_structure(self):
        doc = super(Benefit, self).get_documentation_structure()
        doc['parameters'].append(
            coog_string.doc_for_field(self, 'is_group'))
        return doc
