# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Bool, Eval

from trytond.modules.coog_core import fields, model
from trytond.modules.rule_engine import get_rule_mixin


__all__ = [
    'DocumentRule',
    'RuleDocumentDescriptionRelation',
    'Product',
    'OptionDescription',
    ]


class DocumentRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    'Document Managing Rule'

    __name__ = 'document.rule'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='CASCADE', select=True)
    option = fields.Many2One('offered.option.description',
        'Option Description', ondelete='CASCADE', select=True)
    documents = fields.One2Many('document.rule-document.description', 'rule',
        'Documents', delete_missing=True)
    reminder_delay = fields.Integer('Reminder Delay')
    reminder_unit = fields.Selection([
            ('', ''),
            ('month', 'Months'),
            ('day', 'Days')],
        'Reminder Unit', states={'required': Bool(Eval('reminder_delay'))},
        depends=['reminder_delay'])

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        TableHandler = backend.get('TableHandler')
        document_rule = TableHandler(cls)
        super(DocumentRule, cls).__register__(module_name)
        # Migration from 1.3: Drop sub_document_rules column
        cursor = Transaction().connection.cursor()
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
                'wrong_documents_rule': 'The return value of the document '
                'rule must be a dictionnary with document description code '
                'as keys.',
                })
        cls.rule.domain = [('type_', '=', 'doc_request')]
        cls.rule.help = ('The rule must return a dictionnary '
        'with document description codes as keys, and dictionnaries as values.'
        ' The possible keys for these sub dictionnaries are : %s ' %
            str(RuleDocumentDescriptionRelation.rule_result_fields))

    @staticmethod
    def default_reminder_unit():
        return ''

    def format_as_rule_result(self):
        return {x.document.code: x.to_dict() for x in self.documents}

    def calculate_required_documents(self, args):
        if not self.rule:
            return self.format_as_rule_result()
        result = self.calculate_rule(args)
        if type(result) is not dict:
            self.raise_user_error('wrong_documents_rule')
        result.update(self.format_as_rule_result())
        return result

    def get_func_key(self, name):
        if self.product:
            return getattr(self.product, self.product._func_key)
        elif self.option:
            return getattr(self.option, self.option._func_key)


class RuleDocumentDescriptionRelation(model.CoogSQL, model.CoogView):
    'Rule to Document Description Relation'

    __name__ = 'document.rule-document.description'

    rule = fields.Many2One('document.rule', 'Rule', ondelete='CASCADE',
        required=True, select=True)
    document = fields.Many2One('document.description', 'Document',
        ondelete='RESTRICT', required=True, select=True)
    blocking = fields.Boolean('Blocking')
    max_reminders = fields.Integer('Max Reminders')

    rule_result_fields = [('blocking', 'blocking'),
        ('max_reminders', 'max_reminders')]

    def to_dict(self):
        return {x[1]: getattr(self, x[0]) for x in self.rule_result_fields}


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    document_rules = fields.One2Many('document.rule', 'product',
        'Document Rules', delete_missing=True, size=1,
        target_not_required=True)

    @classmethod
    def __register__(cls, module_name):
        super(Product, cls).__register__(module_name)
        # Migration from 1.3: Drop sub_document_rules column
        TableHandler = backend.get('TableHandler')
        product = TableHandler(cls)
        if product.column_exist('sub_document_rules'):
            product.drop_column('sub_document_rules')

    def calculate_required_documents(self, args):
        if not self.document_rules:
            return []
        return self.document_rules[0].calculate_required_documents(args)

    @property
    def reception_requires_attachment(self):
        if self.document_rules:
            return self.document_rules[0].reception_requires_attachment


class OptionDescription:
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'

    document_rules = fields.One2Many('document.rule', 'option',
        'Document Rules', delete_missing=True, size=1,
        target_not_required=True)

    @classmethod
    def __register__(cls, module_name):
        super(OptionDescription, cls).__register__(module_name)
        # Migration from 1.3: Drop sub_document_rules column
        TableHandler = backend.get('TableHandler')
        option = TableHandler(cls)
        if option.column_exist('sub_document_rules'):
            option.drop_column('sub_document_rules')

    def calculate_required_documents(self, args):
        if not self.document_rules:
            return []
        return self.document_rules[0].calculate_required_documents(args)
