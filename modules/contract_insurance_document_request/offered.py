from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model
from trytond.modules.rule_engine import RuleMixin


__all__ = [
    'DocumentRule',
    'RuleDocumentDescriptionRelation',
    'Product',
    'OptionDescription',
    ]

__metaclass__ = PoolMeta


class DocumentRule(RuleMixin, model.CoopSQL, model.CoopView):
    'Document Managing Rule'

    __name__ = 'document.rule'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='CASCADE')
    option = fields.Many2One('offered.option.description',
        'Option Description', ondelete='CASCADE')
    documents = fields.Many2Many('document.rule-document.description', 'rule',
        'document', 'Documents')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        super(DocumentRule, cls).__register__(module_name)
        # Migration from 1.3: Drop sub_document_rules column
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        document_rule = TableHandler(cursor, cls)
        if document_rule.column_exist('start_date'):
            document_rule.drop_column('start_date')
        if document_rule.column_exist('end_date'):
            document_rule.drop_column('end_date')
        if document_rule.column_exist('config_kind'):
            document_rule.drop_column('config_kind')
        if document_rule.column_exist('template'):
            document_rule.drop_column('template')
        if document_rule.column_exist('offered'):
            cursor.execute('update document_rule '
                'set product=CAST(substr(offered,17) as integer) '
                "where offered like 'offered.product,%'")
            cursor.execute('update document_rule '
                'set option=CAST(substr(offered,28) as integer) '
                "where offered like 'offered.option.description,%'")
            document_rule.drop_column('offered')

    @classmethod
    def __setup__(cls):
        super(DocumentRule, cls).__setup__()
        cls._error_messages.update({
                'wrong_documents_rule': 'The return of the document rule must '
                'be a list with required document code.',
                })
        cls.rule.required = False
        cls.rule.help = 'The rule must return a list of documents code.'

    def calculate_required_documents(self, args):
        pool = Pool()
        DocumentDescription = pool.get('document.description')
        if not self.rule:
            return list(self.documents)
        documents_in_rules = []
        documents_code = self.calculate(args)
        if type(documents_code) == list:
            if documents_code:
                documents_in_rules = DocumentDescription.search(
                    [('code', 'in', documents_code)])
        else:
            self.raise_user_error('wrong_documents_rule')
        return list(set(documents_in_rules + list(self.documents)))


class RuleDocumentDescriptionRelation(model.CoopSQL):
    'Rule to Document Description Relation'

    __name__ = 'document.rule-document.description'

    rule = fields.Many2One('document.rule', 'Rule', ondelete='CASCADE')
    document = fields.Many2One('document.description', 'Document',
        ondelete='RESTRICT')


class Product:
    __name__ = 'offered.product'

    document_rules = fields.One2Many('document.rule', 'product',
        'Document Rules', delete_missing=True, size=1)

    @classmethod
    def __register__(cls, module_name):
        super(Product, cls).__register__(module_name)
        # Migration from 1.3: Drop sub_document_rules column
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        product = TableHandler(cursor, cls)
        if product.column_exist('sub_document_rules'):
            product.drop_column('sub_document_rules')

    def calculate_required_documents(self, args):
        if not self.document_rules:
            return []
        return self.document_rules[0].calculate_required_documents(args)


class OptionDescription:
    __name__ = 'offered.option.description'

    document_rules = fields.One2Many('document.rule', 'option',
        'Document Rules', delete_missing=True, size=1)

    @classmethod
    def __register__(cls, module_name):
        super(OptionDescription, cls).__register__(module_name)
        # Migration from 1.3: Drop sub_document_rules column
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        option = TableHandler(cursor, cls)
        if option.column_exist('sub_document_rules'):
            option.drop_column('sub_document_rules')

    def calculate_required_documents(self, args):
        if not self.document_rules:
            return []
        return self.document_rules[0].calculate_required_documents(args)
