from trytond.pool import PoolMeta
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, utils
from trytond.modules.offered_insurance.business_rule.business_rule import \
    BusinessRuleRoot, STATE_ADVANCED
from trytond.modules.offered import NonExistingRuleKindException


__all__ = [
    'DocumentRule',
    'RuleDocumentDescriptionRelation',
    'Offered',
    'OfferedProduct',
    'OfferedOptionDescription',
    ]

__metaclass__ = PoolMeta


class DocumentRule(BusinessRuleRoot, model.CoopSQL):
    'Document Managing Rule'

    __name__ = 'document.rule'

    kind = fields.Selection([
            ('', ''),
            ('main', 'Main'),
            ('sub', 'Sub Elem'),
            ('loss', 'Loss'),
            ], 'Kind')
    documents = fields.Many2Many('document.rule-document.description', 'rule',
        'document', 'Documents', states={'invisible': STATE_ADVANCED})

    def give_me_documents(self, args):
        if self.config_kind == 'simple':
            return self.documents, []
        if not self.rule:
            return [], []
        try:
            rule_result = self.get_rule_result(args)
        except Exception:
            return [], ['Invalid rule']
        try:
            result = utils.get_those_objects(
                'document.request.line', [
                    ('code', 'in', rule_result.result)])
            return result, []
        except:
            return [], ['Invalid documents']

    @classmethod
    def default_kind(cls):
        return Transaction().context.get('doc_rule_kind', None)


class RuleDocumentDescriptionRelation(model.CoopSQL):
    'Rule to Document Description Relation'

    __name__ = 'document.rule-document.description'

    rule = fields.Many2One('document.rule', 'Rule', ondelete='CASCADE')
    document = fields.Many2One('document.description', 'Document',
        ondelete='RESTRICT')


class Offered:
    __name__ = 'offered'

    document_rules = fields.One2ManyDomain('document.rule', 'offered',
        'Document Rules', context={'doc_rule_kind': 'main'},
        domain=[('kind', '=', 'main')], delete_missing=True)
    sub_document_rules = fields.One2ManyDomain('document.rule', 'offered',
        'Sub Document Rules', context={'doc_rule_kind': 'sub'},
        domain=[('kind', '=', 'sub')], delete_missing=True)

    def give_me_documents(self, args):
        try:
            return self.get_result('documents', args, kind='document')
        except NonExistingRuleKindException:
            return [], ()


class OfferedProduct(Offered):
    'Offered Product'

    __name__ = 'offered.product'
    # This empty override is necessary to have in the product, the fields added
    # in the override of offered


class OfferedOptionDescription(Offered):
    'OptionDescription'

    __name__ = 'offered.option.description'
    # This empty override is necessary to have in the coverage the fields added
    # in the override of offered
