#-*- coding:utf-8 -*-
import copy

from trytond.model import fields

from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.modules.coop_utils import model, utils
from trytond.modules.insurance_product.business_rule.business_rule import \
    BusinessRuleRoot, STATE_SIMPLE

__all__ = [
    'DocumentDesc',
    'DocumentRule',
    'DocumentRuleRelation',
    'Document',
    'DocumentRequest',
]


class DocumentDesc(model.CoopSQL, model.CoopView):
    'Document Descriptor'

    __name__ = 'ins_product.document_desc'

    code = fields.Char('Code', required=True)

    name = fields.Char('Name', required=True)


class DocumentRule(BusinessRuleRoot, model.CoopSQL):
    'Document Managing Rule'

    __name__ = 'ins_product.document_rule'

    kind = fields.Selection(
        [
            ('main', 'Main'),
            ('sub', 'Sub Elem'),
            ('loss', 'Loss'),
            ('', ''),
        ],
        'Kind',
    )

    documents = fields.Many2Many(
        'ins_product.document-rule-relation',
        'rule',
        'document',
        'Documents',
        states={
            'invisible': STATE_SIMPLE,
        },
    )

    def give_me_documents(self, args):
        if self.config_kind == 'simple':
            return self.documents, []

        if not self.rule:
            return [], []

        try:
            res, mess, errs = self.rule.compute(args)
        except Exception:
            return [], ['Invalid rule']

        try:
            result = utils.get_those_objects(
                'ins_product.document', [
                    ('code', 'in', res)])
            return result, []
        except:
            return [], ['Invalid documents']

    @classmethod
    def default_kind(cls):
        return Transaction().context.get('doc_rule_kind', None)


class DocumentRuleRelation(model.CoopSQL):
    'Relation between rule and document'

    __name__ = 'ins_product.document-rule-relation'

    rule = fields.Many2One(
        'ins_product.document_rule',
        'Rule',
        ondelete='CASCADE',
    )

    document = fields.Many2One(
        'ins_product.document_desc',
        'Document',
        ondelete='CASCADE',
    )


class Document(model.CoopSQL, model.CoopView):
    'Document'

    __name__ = 'ins_product.document'

    document_desc = fields.Many2One(
        'ins_product.document_desc',
        'Document Definition',
        required=True,
    )

    for_object = fields.Reference(
        'Needed For',
        [('', '')],
    )

    received = fields.Boolean(
        'Received',
        depends=['attachment'],
    )

    request = fields.Many2One(
        'ins_product.document_request',
        'Document Request',
        ondelete='CASCADE',
    )

    attachment = fields.Many2One(
        'ir.attachment',
        'Attachment',
        domain=[
            ('resource', '=', Eval('_parent_request', {}).get(
                'needed_by_str', ''))],
    )

    last_modification = fields.Function(
        fields.DateTime(
            'Last Modification',
            depends=['attachment'],
            on_change_with=['attachment'],
        ),
        'on_change_with_last_modification',
    )

    def on_change_with_last_modification(self, name=None):
        if not (hasattr(self, 'attachment') and self.attachment):
            return None

        return self.attachment.last_modification

    def get_rec_name(self, name):
        if not (hasattr(self, 'document_desc') and self.document_desc):
            return ''

        if not (hasattr(self, 'for_object') and self.for_object):
            return self.document_desc.name

        return self.document_desc.name + ' - ' + \
            self.for_object.get_rec_name(name)


class DocumentRequest(model.CoopSQL, model.CoopView):
    'Document Request'

    __name__ = 'ins_product.document_request'

    send_date = fields.Date(
        'Send Date',
    )

    reception_date = fields.Date(
        'Reception Date',
    )

    needed_by = fields.Reference(
        'Requested for',
        [('', '')],
    )

    documents = fields.One2Many(
        'ins_product.document',
        'request',
        'Documents',
        depends=['needed_by_str'],
    )

    is_complete = fields.Function(
        fields.Boolean(
            'Is Complete',
            depends=['documents'],
            on_change_with=['documents'],
        ),
        'on_change_with_is_complete',
    )

    needed_by_str = fields.Function(
        fields.Char(
            'Master as String',
            on_change_with=['needed_by'],
            depends=['needed_by'],
        ),
        'on_change_with_needed_by_str',
    )

    def on_change_with_needed_by_str(self, name=None):
        if not (hasattr(self, 'needed_by') and self.needed_by):
            return ''

        return utils.convert_to_reference(self.needed_by)

    def on_change_with_is_complete(self, name=None):
        if not (hasattr(self, 'documents') and self.documents):
            return False

        for doc in self.documents:
            if not doc.received:
                return False

        return True
