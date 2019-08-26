# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import Unique
from trytond.model.exceptions import ValidationError
from sql import Literal

from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

from trytond.modules.coog_core import model, fields
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.offered.extra_data import with_extra_data_def
from trytond.modules.offered.extra_data import ExtraDataDefTable

__all__ = [
    'Questionnaire',
    'QuestionnairePart',
    'ProductQuestionnaireRuleRelation',
    'QuestionnaireExtraDataRelation',
    'QuestionnaireDistribution',
    ]


class Questionnaire(model.CodedMixin, model.CoogView, model.SequenceMixin,
        model.IconMixin, model.TaggedMixin):
    'Questionnaire'

    __name__ = 'questionnaire'

    parts = fields.One2Many('questionnaire.part', 'questionnaire', 'Parts',
        delete_missing=True, help='The list of sub-questionnaire definitions')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='RESTRICT')
    products = fields.Many2Many('questionnaire-offered.product',
        'questionnaire', 'product', 'Products',
        help='The list of products this questionnaire will be limited to')
    description = fields.Text('Description',
        help='A short text that can be used to describe the purpose of this '
        'questionnaire')

    @classmethod
    def _export_light(cls):
        return super()._export_light() | {'products', 'company'}

    def calculate_questionnaire_result(self, parameters):
        '''
            Expected parameters is a list of answers with the associated part:

            [
                {
                    'part': Part(1),
                    'answers': {'data1': 10, 'data2': 'hello'},
                    },
                {
                    'part': Part(2),
                    'answers': ...
                    },
                ...
            }

            Return value will be a list of dictionnaries, with a key
            referencing the part, and the rule output in the 'results' key
        '''
        result = []
        for part_data in parameters:
            result.append({
                    'part': part_data['part'],
                    'results': part_data['part'].compute(part_data['answers']),
                    })
        return result

    @fields.depends('name', 'parts')
    def on_change_name(self):
        if not self.name:
            return
        if self.parts:
            return
        self.parts = [
            Pool().get('questionnaire.part')(
                name=self.name),
            ]


class QuestionnairePart(model.CoogSQL, model.CoogView, model.SequenceMixin,
        with_extra_data_def('questionnaire-extra_data', 'questionnaire_part',
            'questionnaire'),
        get_rule_mixin('rule', 'Rule')):
    'Questionnaire Part'

    __name__ = 'questionnaire.part'

    name = fields.Char('Name', required=True,
        help='The name of this specific part of the questionnaire')
    questionnaire = fields.Many2One('questionnaire', 'Questionnaire',
        ondelete='CASCADE', select=True, required=True,
        help='The questionnaire this is a part of')
    mandatory = fields.Boolean('Mandatory',
        help='If set, a choice will have to be made among the results provided'
        ' by this part for the questionnaire to be valid')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.rule.required = True
        cls.rule.domain = [('type_', '=', 'questionnaire')]
        cls.rule.help = ('Returns a list of dictionnaries, with the following '
            'keys:\n\n- score: integer between 0-100, the computed '
            'recommandation for this proposition'
            '\n- description: a string which will be used to describe the '
            'proposition'
            '\n- product: the code of the suggested product'
            '\n- eligible: whether the product will be selectable or not for '
            'subscription')

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')

        Questionnaire = Pool().get('questionnaire')

        q_handler = TableHandler(Questionnaire, module)
        to_migrate = (not TableHandler.table_exist(cls._table) and
            q_handler.column_exist('rule'))

        super().__register__(module)

        if to_migrate:
            part_table = cls.__table__()
            questionnaire_table = Pool().get('questionnaire').__table__()
            cursor = Transaction().connection.cursor()
            cursor.execute(*part_table.insert(
                    columns=[part_table.questionnaire, part_table.name,
                        part_table.sequence,
                        part_table.rule,
                        part_table.rule_extra_data],
                    values=questionnaire_table.select(questionnaire_table.id,
                        questionnaire_table.name, Literal(1),
                        questionnaire_table.rule,
                        questionnaire_table.rule_extra_data)
                    ))
            questionnaire = TableHandler(Pool().get('questionnaire'), module)
            if questionnaire.column_exist('rule'):
                questionnaire.drop_column('rule')
                questionnaire.drop_column('rule_extra_data')

    @classmethod
    def _export_light(cls):
        return super()._export_light() | {'rule'}

    @classmethod
    def default_mandatory(cls):
        return False

    def compute(self, parameters):
        # Parameters are assumed to only be extra data
        data = {'extra_data': parameters}
        results = []
        for result in self.calculate_rule(data):
            self._check_result_contents(result)
            if self._accept_result(result):
                results.append(result)
        return results

    def _check_result_contents(self, result):
        try:
            assert isinstance(result, dict)
            requirements = set(result.keys())
            assert all(x in requirements
                for x in ['score', 'description', 'product', 'eligible'])
        except AssertionError:
            raise ValidationError(gettext('questionnaire.msg_invalid_rule_output',
                    rule=self.rule.rec_name))

    def _accept_result(self, result):
        # Returns whether or not this result should be considered, depending on
        # the questionnaire configuration
        codes = [x.code for x in self.questionnaire.products]
        if not codes:
            return True
        return result['product'] in codes


class ProductQuestionnaireRuleRelation(model.CoogSQL):
    'Product to Questionnaire Rule Relation'
    __name__ = 'questionnaire-offered.product'

    questionnaire = fields.Many2One('questionnaire', 'Questionnaire',
        ondelete='CASCADE', required=True, select=True)
    product = fields.Many2One('offered.product', 'Product', ondelete='RESTRICT',
        required=True, select=True)


class QuestionnaireExtraDataRelation(ExtraDataDefTable):
    'Relation between Questionnaires and Extra Data'

    __name__ = 'questionnaire-extra_data'

    questionnaire_part = fields.Many2One('questionnaire.part', 'Questionnaire',
        ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        Part = Pool().get('questionnaire.part')
        relation_table = cls.__table__()
        part_table = Part.__table__()
        relation = TableHandler(cls, module_name)

        super().__register__(module_name)

        if relation.column_exist('questionnaire'):
            cursor = Transaction().connection.cursor()
            cursor.execute(*relation_table.update(
                    columns=[relation_table.questionnaire_part],
                    values=[part_table.id],
                    from_=[part_table],
                    where=(relation_table.questionnaire ==
                        part_table.questionnaire)
                    ))
            relation.drop_column('questionnaire')


class QuestionnaireDistribution(metaclass=PoolMeta):
    __name__ = 'questionnaire'

    def calculate_questionnaire_result(self, parameters):
        '''
            Override to include dist network informations and associated
            commercial products
        '''
        Product = Pool().get('offered.product')

        results = []
        for part_params, part_result in zip(parameters,
                super().calculate_questionnaire_result(parameters)):
            filtered_results = []
            for result in part_result['results']:
                if 'dist_network' not in part_params:
                    filtered_results.append(result)
                    continue
                product = Product.get_instance_from_code(result['product'])

                com_products = [
                    x for x in part_params['dist_network'].all_com_products
                    if x.product == product]
                if not com_products:
                    continue

                for com_product in com_products:
                    new_result = dict(result)
                    new_result['commercial_product'] = com_product.code
                    filtered_results.append(new_result)
            if filtered_results:
                part_result['results'] = filtered_results
                results.append(part_result)
        return results
