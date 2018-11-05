# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import Unique

from trytond.modules.coog_core import model, fields, coog_string
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.offered.extra_data import with_extra_data_def

__all__ = [
    'Questionnaire',
    'ProductQuestionnaireRuleRelation',
    ]


class Questionnaire(model.CoogSQL, model.CoogView, model.TaggedMixin,
        with_extra_data_def('questionnaire-extra_data',
            'questionnaire', 'questionnaire'),
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data')):
    'Questionnaire'

    __name__ = 'questionnaire'
    _func_key = 'code'

    rule_result_fields = [('score', 'Score'), ('eligible', 'Eligible'),
        ('message', 'Message')]

    code = fields.Char('Code', required=True)
    name = fields.Char('Title', required=True, translate=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    description = fields.Text('Description', translate=True)
    icon = fields.Many2One('ir.ui.icon', 'Icon', ondelete='RESTRICT',
        help='This icon will be used to quickly identify the questionnaire')
    icon_name = fields.Function(
        fields.Char('Icon Name'),
        'getter_icon_name')
    sequence = fields.Integer('Sequence')
    products = fields.Many2Many('questionnaire-offered.product',
        'questionnaire', 'product', 'Products')

    @classmethod
    def __setup__(cls):
        super(Questionnaire, cls).__setup__()
        t = cls.__table__()
        cls._order = [('sequence', 'ASC NULLS LAST')]
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]
        cls._error_messages.update({
                'wrong_products_rule': 'The return value of the questionnaire '
                'rule must be a dictionnary with products code as keys.',
                })
        cls.rule.domain = [('type_', '=', 'questionnaire')]
        cls.rule.help = ('The rule must return a dictionnary '
        'with products codes as keys, and dictionnaries as values.'
        ' The possible keys for these sub dictionnaries are : %s ' %
            str(Questionnaire.rule_result_fields))

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        return self.code if self.code else coog_string.slugify(self.name)

    def getter_icon_name(self, name):
        if self.icon:
            return self.icon.name
        return ''

    def calculate_questionnaire_result(self, args):
        if not self.rule:
            return {}
        result = self.calculate_rule(args)
        if type(result) is not dict:
            self.raise_user_error('wrong_products_rule')
        if not self.products:
            return result
        product_codes = [p.code for p in self.products]
        result = {product_code: product_result for product_code, product_result
            in result.iteritems() if product_code in product_codes}
        return result


class ProductQuestionnaireRuleRelation(model.CoogSQL, model.CoogView):
    'Product to Questionnaire Rule Relation'
    __name__ = 'questionnaire-offered.product'

    questionnaire = fields.Many2One('questionnaire', 'Questionnaire',
        ondelete='CASCADE', required=True, select=True)
    product = fields.Many2One('offered.product', 'Product', ondelete='RESTRICT',
        required=True, select=True)
