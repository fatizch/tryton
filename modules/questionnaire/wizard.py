# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.wizard import StateAction
from trytond.pyson import Eval, Len, If
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, model, utils
from trytond.modules.offered.extra_data import with_extra_data


__all__ = [
    'RunQuestionnaire',
    'RunQuestionnaireQuestions',
    'RunQuestionnaireAnswers',
    'RunQuestionnaireQuestionPart',
    'RunQuestionnaireResult',
    'RunQuestionnaireResultChoice',
    'RunQuestionnaireProposition',
    'ContractProcessRunQuestionnaire',
    'ContractSubscribeQuestionnaire',
    'ContractSubscribeFindProcess',
    'ContractSubscribeFindProcessDistribution',
    'RunDistributionQuestionnaire',
    'RunDistributionQuestionnaireQuestions',
    'RunDistributionQuestionnaireResultChoice',
    ]


class RunQuestionnaire(Wizard):
    'Run Questionnaire'

    __name__ = 'questionnaire.run'

    start_state = 'check_questionnaire'

    check_questionnaire = StateTransition()
    questionnaire = StateView('questionnaire.run.questions',
        'questionnaire.questionnaire_run_questions_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'check_answer', 'tryton-go-next',
                default=True)])
    check_answer = StateTransition()
    answer = StateView('questionnaire.run.questions.answers',
        'questionnaire.questionnaire_run_questions_answers_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'check_proposition', 'tryton-go-next',
                default=True)])
    check_proposition = StateTransition()
    proposition = StateView('questionnaire.run.questions.proposition',
        'questionnaire.questionnaire_run_questions_proposition_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Results', 'questionnaire_results', 'tryton-go-next',
                default=True)])
    questionnaire_results = StateTransition()

    def transition_check_questionnaire(self):
        Questionnaire = Pool().get('questionnaire')
        questionnaires = Questionnaire.search([])
        if questionnaires:
            self.questionnaire.possible_questionnaires = questionnaires
            return 'questionnaire'
        raise ValidationError(gettext('questionnaire.msg_no_questionnaires'))

    def default_questionnaire(self, name):
        ids = [x.id for x in self.questionnaire.possible_questionnaires]
        return {
            'questionnaire': ids[0] if len(ids) == 1 else None,
            'possible_questionnaires': ids,
            }

    def transition_check_answer(self):
        return 'answer'

    def default_answer(self, name):
        if self.questionnaire.questionnaire:
            answers = [{'part': part.id} for part in
                self.questionnaire.questionnaire.parts]
        else:
            answers = []
        return {'answers': answers}

    def transition_check_proposition(self):
        ExtraData = Pool().get('extra_data')
        for answer in self.answer.answers:
            ExtraData.check_extra_data(answer, 'questions')
        return 'proposition'

    def default_proposition(self, name):
        if self.answer.answers:
            results = [{
                    'part': res.part.id,
                    'choices': [x.as_default_value() for x in res.choices],
                    } for res in self.calculate()]
        else:
            results = []
        return {'results': results}

    def calculate(self):
        pool = Pool()
        Result = pool.get('questionnaire.run.questions.result')
        Choice = pool.get('questionnaire.run.questions.result.choice')
        rule_results = \
            self.questionnaire.questionnaire.calculate_questionnaire_result(
                self._calculate_parameters())

        results = []
        for rule_result in rule_results:
            part_id = rule_result['part']
            choices = rule_result['results']
            if not choices:
                continue
            result = Result()
            result.part = part_id
            result.choices = sorted(
                [Choice.init_from_rule_result(r) for r in choices],
                key=lambda x: -x.score)
            if result.choices:
                result.choices[0].selected = True
                results.append(result)
        results = sorted(results, key=lambda x: x.part.sequence)
        return results

    def _calculate_parameters(self):
        return [{'part': x.part, 'answers': x.questions}
            for x in self.answer.answers]

    def transition_questionnaire_results(self):
        self._check_results()

        # For now, we start the subscription on the first mandatory part, or
        # the first selected part if None is mandatory
        cur_choice = self._get_selected_choice()
        if cur_choice is None:
            raise ValidationError(gettext('questionnaire.msg_nothing_selected'))

        # Maybe there is something to do here if contract_process is not
        # installed
        return 'end'

    def _get_selected_choice(self):
        cur_choice = None
        for result in self.proposition.results:
            if cur_choice is None or result.part.mandatory:
                selected = [x for x in result.choices if x.selected]
                if not selected:
                    continue
                cur_choice, = selected
                if result.part.mandatory:
                    break
        return cur_choice

    def _check_results(self):
        for result in self.proposition.results:
            if result.part.mandatory and all(not x.selected for x in
                    result.choices):
                raise ValidationError(gettext('questionnaire.msg_mandatory_choice',
                    part=result.part.result))


class RunQuestionnaireQuestions(model.CoogView):
    'Questionnaire'

    __name__ = 'questionnaire.run.questions'

    questionnaire = fields.Many2One('questionnaire', 'Questionnaire',
        domain=[('id', 'in', Eval('possible_questionnaires', []))],
        depends=['possible_questionnaires'])
    description = fields.Text('Description', readonly=True,
        states={'invisible': ~Eval('questionnaire')})
    possible_questionnaires = fields.Many2Many('questionnaire', None, None,
        'Possible Questionnaires', states={'invisible': True}, readonly=True)


class RunQuestionnaireAnswers(model.CoogView):
    'Run Questionnaire Answers'
    __name__ = 'questionnaire.run.questions.answers'

    answers = fields.One2Many('questionnaire.run.questions.part', None,
        'Answers', states={'invisible': ~Eval('answers')})

    def _init_answer(self, part):
        answer = Pool().get('questionnaire.run.questions.part')()
        answer.part = part
        answer.on_change_part()
        return answer

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ("/form/group[@id='one_answer']", 'states',
             {'invisible': Len(Eval('answers', [])) != 1}),
            ("/form/group[@id='multiple_answers']", 'states',
             {'invisible': Len(Eval('answers', [])) <= 1}),
            ]


class RunQuestionnaireProposition(model.CoogView):
    'Run Questionnaire Proposition'
    __name__ = 'questionnaire.run.questions.proposition'

    results = fields.One2Many('questionnaire.run.questions.result', None,
        'Results', readonly=True, states={'invisible': ~Eval('results')})

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ("/form/group[@id='one_result']", 'states',
             {'invisible': Len(Eval('results', [])) != 1}),
            ("/form/group[@id='multiple_results']", 'states',
             {'invisible': Len(Eval('results', [])) <= 1}),
            ]


class RunQuestionnaireQuestionPart(model.CoogView,
        with_extra_data(['questionnaire'], field_name='questions',
            field_string='Questions', schema='part')):
    'Questionnaire Part'

    __name__ = 'questionnaire.run.questions.part'

    part = fields.Many2One('questionnaire.part', 'Questionnaire',
        readonly=True, states={'invisible': True})
    title = fields.Char('Title', readonly=True)

    @fields.depends('part')
    def on_change_part(self):
        super().on_change_part()
        self.title = self.part.name if self.part else ''

    def init_dict_for_rule_engine(self, data):
        data['questionnaire_answer'] = self

    def get_rec_name(self, name):
        # Required because 'check_extra_data'
        return self.title


class RunQuestionnaireResult(model.CoogView):
    'Questionnaire Result'
    __name__ = 'questionnaire.run.questions.result'

    part = fields.Many2One('questionnaire.part', 'Questionnaire Part',
        readonly=True)
    choices = fields.One2Many(
        'questionnaire.run.questions.result.choice', None, 'Choices',
        readonly=True)

    @fields.depends('choices')
    def on_change_choices(self):
        model.update_selection(self.choices)


class RunQuestionnaireResultChoice(model.CoogView,
        model.MonoSelectedMixin):
    'Questionnaire Result Choice'

    __name__ = 'questionnaire.run.questions.result.choice'

    selectable = fields.Boolean('Selectable', readonly=True)
    description = fields.Char('Description', readonly=True)
    product = fields.Char('Product', readonly=True)
    score = fields.Integer('Score', readonly=True,
        help='The score (0-100) that represents the accuracy of this choice '
        'according to the provided answers')
    data_as_json = fields.Text('Data', readonly=True,
        states={'invisible': True},
        help='The json data that describes the actual answer')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.selected.states['readonly'] = ~Eval('selectable')
        cls.selected.depends.append('selectable')

    @classmethod
    def init_from_rule_result(cls, data):
        choice = cls()
        choice.description = data['description']
        choice.score = data['score']
        choice.data_as_json = json.dumps(data)
        choice.product = Pool().get('offered.product').get_instance_from_code(
            data['product']).name
        choice.selectable = data['eligible']
        return choice

    def as_default_value(self):
        return {
            'score': self.score,
            'description': self.description,
            'data_as_json': self.data_as_json,
            'selectable': self.selectable,
            'product': self.product,
            'selected': False,
            'was_selected': False,
            }

    @property
    def data(self):
        return json.loads(self.data_as_json)


class ContractProcessRunQuestionnaire(metaclass=PoolMeta):
    __name__ = 'questionnaire.run'

    start_subscription = StateAction(
        'contract_process.subscription_process_launcher')

    def transition_questionnaire_results(self):
        super().transition_questionnaire_results()

        # Initiate new subscription process
        return 'start_subscription'

    def _as_contract_questionnaire(self):
        return {
            'questionnaire': self.questionnaire.questionnaire.id,
            'answers': [{'part': x.part.id, 'answers': x.questions}
                for x in self.answer.answers],
            'results': [{
                    'part': x.part.id,
                    'results_as_text': json.dumps([
                            {
                                'selected': c.selected,
                                'description': c.description,
                                'score': c.score,
                                'data': c.data,
                                } for c in x.choices]),
                    } for x in self.proposition.results],
            }

    def do_start_subscription(self, action):
        Product = Pool().get('offered.product')
        forced_product = Product.get_instance_from_code(
            self._get_selected_choice().data['product'])
        context = {
            'extra_context': {
                'forced_product': forced_product.id,
                'questionnaire_data': self._as_contract_questionnaire(),
                },
            }
        if Transaction().context.get('active_model', None) == 'party.party':
            context['model'] = 'party.party'
            context['id'] = Transaction().context.get('active_id')
            context['ids'] = Transaction().context.get('active_ids')
        return action, context


class ContractSubscribeQuestionnaire(metaclass=PoolMeta):
    __name__ = 'contract.subscribe'

    def default_process_parameters(self, name):
        res = super().default_process_parameters(name)
        forced_product = Transaction().context.get('forced_product', None)
        if forced_product:
            res['forced_product'] = forced_product
            res['start_date'] = utils.today()
        return res

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super().init_main_object_from_process(obj, process_param)
        questionnaire_data = Transaction().context.get('questionnaire_data',
            None)
        if res and questionnaire_data:
            obj.questionnaires = [questionnaire_data]
        return res, errs


class ContractSubscribeFindProcess(metaclass=PoolMeta):
    __name__ = 'contract.subscribe.find_process'

    forced_product = fields.Many2One('offered.product', 'Product',
        readonly=True, states={'invisible': True},
        help='If set, only this product can be subscribed')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.product.domain = [
            'AND',
            cls.product.domain,
            If(Eval('forced_product'), ['id', '=', Eval('forced_product')],
                [])]
        cls.product.depends.append('forced_product')


class ContractSubscribeFindProcessDistribution(metaclass=PoolMeta):
    __name__ = 'contract.subscribe.find_process'

    @fields.depends('forced_product')
    def simulate_init(self):
        return super().simulate_init()

    def _authorized_commercial_products(self):
        authorized = super()._authorized_commercial_products()
        if self.forced_product:
            authorized = [x for x in authorized
                if x.product.id == self.forced_product.id]
        return authorized


class RunDistributionQuestionnaire(metaclass=PoolMeta):
    __name__ = 'questionnaire.run'

    def default_questionnaire(self, name):
        defaults = super().default_questionnaire(name)
        candidates = [x.id for x in
            Pool().get('res.user')(Transaction().user).network_distributors]
        defaults['authorized_distributors'] = [x for x in candidates]
        defaults['distributor'] = (
            candidates[0] if len(candidates) == 1 else None)
        return defaults

    def _calculate_parameters(self):
        parameters = super()._calculate_parameters()
        for part_parameters in parameters:
            part_parameters['dist_network'] = self.questionnaire.distributor
        return parameters

    def do_start_subscription(self, action):
        ComProduct = Pool().get('distribution.commercial_product')
        forced_com_product = ComProduct.get_instance_from_code(
            self._get_selected_choice().data['commercial_product'])

        action, context = super().do_start_subscription(action)
        context['extra_context']['forced_dist_network'] = \
            self.questionnaire.distributor.id
        context['extra_context']['forced_com_product'] = forced_com_product.id
        return action, context


class RunDistributionQuestionnaireQuestions(metaclass=PoolMeta):
    __name__ = 'questionnaire.run.questions'

    authorized_distributors = fields.Many2Many(
        'distribution.network', None, None, 'Authorized distributors',
        states={'invisible': True})
    distributor = fields.Many2One(
        'distribution.network', 'Distributor', required=True,
        domain=[('id', 'in', Eval('authorized_distributors'))],
        depends=['authorized_distributors'])


class RunDistributionQuestionnaireResultChoice(metaclass=PoolMeta):
    __name__ = 'questionnaire.run.questions.result.choice'

    @classmethod
    def init_from_rule_result(cls, data):
        ComProduct = Pool().get('distribution.commercial_product')
        choice = super().init_from_rule_result(data)
        choice.product = ComProduct.get_instance_from_code(
            data['commercial_product']).name
        return choice
