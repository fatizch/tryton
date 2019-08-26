# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json

from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Len, Eval

from trytond.modules.coog_core import model, fields
from trytond.modules.offered.extra_data import with_extra_data


__all__ = [
    'Contract',
    'ContractQuestionnaire',
    'ContractQuestionnaireAnswer',
    'ContractQuestionnaireResult',
    'ContractQuestionnaireResultDistribution',
    ]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    questionnaires = fields.One2Many('contract.questionnaire', 'contract',
        'Questionnaires', delete_missing=True,
        help='The questionnaire(s) whose answers ended up with this contract')


class ContractQuestionnaire(model.CoogSQL, model.CoogView):
    'Contract Questionnaire'

    __name__ = 'contract.questionnaire'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        select=True, required=True)
    questionnaire = fields.Many2One('questionnaire',
        'Questionnaire Configuration',
        ondelete='RESTRICT', readonly=True, required=True,
        help='The questionnaire template which provided the questions')
    answers = fields.One2Many('contract.questionnaire.answer', 'questionnaire',
        'Answers', delete_missing=True, readonly=True,
        states={'invisible': Len(Eval('answers', [])) <= 1},
        depends=['answers'],
        help='The answers that were given by the subscriber')
    results = fields.One2Many('contract.questionnaire.result', 'questionnaire',
        'Results', delete_missing=True, readonly=True,
        states={'invisible': Len(Eval('results', [])) <= 1},
        depends=['results'],
        help='The results that were suggested by the questionnaire algorithm')
    one_answer = fields.Function(
        fields.Text('Answer',
            states={'invisible': Len(Eval('answers', [])) > 1},
            depends=['answers']),
        'getter_one_answer')
    one_result = fields.Function(
        fields.Text('Result',
            states={'invisible': Len(Eval('results', [])) > 1},
            depends=['results']),
        'getter_one_result')

    def getter_one_answer(self, name):
        if not self.answers:
            return ''
        return self.answers[0].answers_summary

    def getter_one_result(self, name):
        if not self.results:
            return ''
        return self.results[0].results_summary


class ContractQuestionnaireAnswer(model.CoogSQL, model.CoogView,
        with_extra_data(['questionnaire'], field_name='answers',
            field_string='Answers', schema='part')):
    'Contract Questionnaire Answer'

    __name__ = 'contract.questionnaire.answer'

    questionnaire = fields.Many2One('contract.questionnaire', 'Questionnaire',
        required=True, ondelete='CASCADE', readonly=True, select=True)
    part = fields.Many2One('questionnaire.part', 'Questionnaire Part',
        required=True, ondelete='RESTRICT', readonly=True,
        help='The questionnaire part that asked the questions')
    title = fields.Function(
        fields.Char('Title', help='The questionnaire part that asked the'
            'questions'),
        'getter_title')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.answers.help = 'The answers that were provided by the client'
        cls.answers.readonly = True

    def getter_title(self, name):
        return self.part.rec_name


class ContractQuestionnaireResult(model.CoogSQL, model.CoogView):
    'Contract Questionnaire Result'

    __name__ = 'contract.questionnaire.result'

    questionnaire = fields.Many2One('contract.questionnaire', 'Questionnaire',
        required=True, ondelete='CASCADE', readonly=True, select=True)
    part = fields.Many2One('questionnaire.part', 'Questionnaire Part',
        required=True, ondelete='RESTRICT', readonly=True,
        help='The questionnaire part that provided this result')
    title = fields.Function(
        fields.Char('Title', help='The questionnaire part that provided the'
            'result'),
        'getter_title')
    results_as_text = fields.Text('Results', readonly=True,
        help='The results that were provided, encoded as a JSON object')
    results_summary = fields.Function(
        fields.Text('Results Summary', help='The results provided as a human '
            'readable text'),
        'getter_results_summary')

    def getter_title(self, name):
        return self.part.rec_name

    def getter_results_summary(self, name):
        return '\r\r'.join(self._format_result(x) for x in self.results_as_json)

    def _format_result(self, result):
        product = Pool().get('offered.product').get_instance_from_code(
            result['product'])
        return '\r'.join(
            [
                '%s: %s' % (gettext('questionnaire.msg_score'),
                    result['score']),
                '%s: %s' % (gettext('questionnaire.msg_product'),
                    product.rec_name),
                '%s: %s' % (gettext('questionnaire.msg_description'),
                    result['description']),
                gettext('msg_selected') if result.get('selected', False)
                else gettext('msg_not_selected'),
                ])

    @property
    def results_as_json(self):
        return json.loads(self.results_as_text)


class ContractQuestionnaireResultDistribution(metaclass=PoolMeta):
    __name__ = 'contract.questionnaire.result'

    def _format_result(self, result):
        CommercialProduct = Pool().get('distribution.commercial_product')

        formatted = super()._format_result(result)

        commercial_product = CommercialProduct.get_instance_from_code(
            result['commercial_product'])
        return '%s\r%s: %s' % (formatted,
            gettext('msg_commercial_product'),
            commercial_product.rec_name)
