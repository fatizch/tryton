# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, model


__all__ = [
    'Benefit',
    'DocumentRule',
    'LossDescription',
    'LossDescriptionDocumentDescriptionRelation',
    ]


class Benefit(metaclass=PoolMeta):
    __name__ = 'benefit'

    documents_rules = fields.One2Many('document.rule', 'benefit',
        'Document Rules', help='Define which documents are requested and '
        'required during claim declaration', delete_missing=True, size=1,
        target_not_required=True)

    def calculate_required_documents(self, args):
        if not self.documents_rules:
            return []
        return self.documents_rules[0].calculate_required_documents(args)


class DocumentRule(metaclass=PoolMeta):
    __name__ = 'document.rule'

    benefit = fields.Many2One('benefit', 'Benefit', ondelete='CASCADE',
        select=True)

    def get_func_key(self, name):
        return getattr(self.benefit, self.benefit._func_key)


class LossDescription(metaclass=PoolMeta):
    __name__ = 'benefit.loss.description'

    documents = fields.Many2Many(
        'benefit.loss.description-document.description', 'loss', 'document',
        'Documents')

    def get_documents(self):
        if not (hasattr(self, 'documents') and self.documents):
            return []
        return self.documents


class LossDescriptionDocumentDescriptionRelation(model.CoogSQL):
    'Loss Description to Document Description Relation'

    __name__ = 'benefit.loss.description-document.description'

    document = fields.Many2One('document.description', 'Document',
        ondelete='RESTRICT', required=True, select=True)
    loss = fields.Many2One('benefit.loss.description', 'Loss',
        ondelete='CASCADE', required=True)
