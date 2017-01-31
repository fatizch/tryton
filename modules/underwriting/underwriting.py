# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql import Null

from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateTransition, StateAction
from trytond.wizard import Button
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, Bool, In, Len

from trytond.modules.coog_core import model, fields, coog_string, utils
from trytond.modules.coog_core import coog_date
from trytond.modules.report_engine import Printable
from trytond.modules.document_request import document

__all__ = [
    'UnderwritingType',
    'UnderwritingDecisionType',
    'UnderwritingTypeDecision',
    'UnderwritingTypeDocumentRule',
    'Underwriting',
    'UnderwritingResult',
    'PlanUnderwriting',
    'PlanUnderwritingDate',
    ]


class UnderwritingType(model.CoogSQL, model.CoogView):
    'Underwriting Type'

    __name__ = 'underwriting.type'
    _func_key = 'code'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    decisions = fields.Many2Many('underwriting.type-decision',
        'underwriting_type', 'decision', 'Decisions')
    waiting_decision = fields.Many2One('underwriting.decision.type',
        'Waiting Decision', required=True, ondelete='RESTRICT')
    document_rule = fields.One2Many('underwriting.document_rule',
        'underwriting_type', 'Document Rule', delete_missing=True)
    end_date_required = fields.Boolean('End date required',
        help='If True, the end date will be required on the related decisions')
    next_underwriting = fields.Many2One('underwriting.type',
        'Next Underwriting', ondelete='RESTRICT', states={
            'invisible': ~Eval('end_date_required')},
        depends=['end_date_required'])

    @classmethod
    def _export_skips(cls):
        return super(UnderwritingType, cls)._export_skips() | set(
            ['documents'])

    @classmethod
    def _export_light(cls):
        return super(UnderwritingType, cls)._export_light() | {'decisions',
            'waiting_decision'}

    @classmethod
    def default_document_rule(cls):
        return [{}]

    @fields.depends('decisions', 'waiting_decision')
    def on_change_decisions(self):
        if self.waiting_decision not in self.decisions:
            self.waiting_decision = None
        if not self.waiting_decision:
            if len(self.decisions) == 1:
                self.waiting_decision = self.decisions[0]

    @fields.depends('end_date_required', 'next_underwriting')
    def on_change_end_date_required(self):
        if not self.end_date_required:
            self.next_underwriting = None

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    def new_underwriting(self, on_object, party, decisions):
        pool = Pool()
        Underwriting = pool.get('underwriting')
        Result = pool.get('underwriting.result')
        underwriting = Underwriting()
        underwriting.type_ = self
        underwriting.party = party
        underwriting.on_object = on_object
        underwriting.state = 'draft'
        new_decisions = []
        for date, decision in decisions:
            new_decision = Result()
            new_decision.underwriting = underwriting
            new_decision.target = decision
            new_decision.effective_decision_date = date
            new_decision.on_change_underwriting()
            new_decisions.append(new_decision)
        underwriting.results = new_decisions
        return underwriting

    def calculate_documents(self, underwriting):
        rule = self.document_rule[0]
        results = []
        for decision in underwriting.results:
            data_dict = {}
            decision.init_dict_for_rule_engine(data_dict)
            results.append(rule.calculate_required_documents(data_dict))
        if len(results) > 1:
            return rule.merge_results(*results)
        return results[0]


class UnderwritingDecisionType(model.CoogSQL, model.CoogView):
    'Underwriting Decision Type'

    __name__ = 'underwriting.decision.type'
    _func_key = 'code'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    decision = fields.Selection([('nothing', 'Nothing')], 'Decision')
    decision_string = decision.translated('decision')
    model = fields.Selection([('party.party', 'Party')], 'Model')
    model_string = model.translated('model')

    @classmethod
    def default_decision(cls):
        return 'nothing'

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)


class UnderwritingTypeDecision(model.CoogSQL):
    'Underwriting Type - Decision relation'

    __name__ = 'underwriting.type-decision'

    underwriting_type = fields.Many2One('underwriting.type',
        'Underwriting Type', required=True, select=True, ondelete='CASCADE')
    decision = fields.Many2One('underwriting.decision.type', 'Decision',
        required=True, ondelete='RESTRICT')


class UnderwritingTypeDocumentRule(document.DocumentRuleMixin):
    'Underwriting Document Rule'
    __name__ = 'underwriting.document_rule'

    underwriting_type = fields.Many2One('underwriting.type', 'Parent',
        ondelete='CASCADE', required=True, select=True)

    @classmethod
    def __setup__(cls):
        super(UnderwritingTypeDocumentRule, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints = [
            ('one_per_underwriting_type',
                Unique(table, table.underwriting_type),
                'There may be only one document rule per underwriting type'),
            ]


class Underwriting(model.CoogSQL, model.CoogView, Printable):
    'Underwriting'

    __name__ = 'underwriting'

    party = fields.Many2One('party.party', 'Party', required=True, select=True,
        ondelete='CASCADE', states={'readonly': Eval('state') != 'draft'},
        depends=['state'])
    on_object = fields.Reference('For Object', [('party.party', 'Party')],
        select=True, required=True, states={
            'readonly': Eval('state') != 'draft'}, depends=['state'])
    type_ = fields.Many2One('underwriting.type', 'Type', required=True,
        ondelete='RESTRICT', states={'readonly': Eval('state') != 'draft'},
        depends=['state'])
    state = fields.Selection([('draft', 'Draft'), ('processing', 'Processing'),
            ('completed', 'Completed')],
        'State', readonly=True, select=True)
    state_string = state.translated('state')
    results = fields.One2Many('underwriting.result', 'underwriting',
        'Results', delete_missing=True, domain=['OR',
            ('final_decision', '=', None),
            ('final_decision', 'in', Eval('possible_decision_types'))],
        depends=['possible_decision_types'])
    possible_decision_types = fields.Function(
        fields.Many2Many('underwriting.decision.type', None, None,
            'Possible Decision Types'),
        'on_change_with_possible_decision_types')
    finalizable_result = fields.Function(
        fields.Boolean('Finalizable Result'),
        'get_finalizable_result', searcher='search_finalizable_result')
    finalizable = fields.Function(
        fields.Boolean('Finalizable'),
        'get_finalizable', searcher='search_finalizable')
    requested_documents = fields.One2Many('document.request.line',
        'for_object', 'Requested Documents', delete_missing=True)
    type_code = fields.Function(
        fields.Char('Type Code'),
        'on_change_with_type_code')

    @classmethod
    def __setup__(cls):
        super(Underwriting, cls).__setup__()
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') != 'processing',
                    },
                'process': {
                    'readonly': Len(Eval('results', [])) == 0,
                    'invisible': Eval('state') != 'draft',
                    },
                'complete': {
                    'invisible': Eval('state') != 'processing',
                    },
                'plan_button': {},
                'generic_send_letter': {},
                })
        cls._error_messages.update({
                'cannot_draft': 'Cannot draft completed underwritings',
                'cannot_draft_result': 'Cannot draft completed results',
                })

    @classmethod
    def view_attributes(cls):
        return [
            ("/form/group[@id='results_draft']", 'states', {
                        'invisible': Eval('state') != 'draft'}),
            ("/form/group[@id='results_other']", 'states', {
                        'invisible': Eval('state') == 'draft'}),
            ]

    @classmethod
    def default_state(cls):
        return 'draft'

    @fields.depends('type_')
    def on_change_with_possible_decision_types(self, name=None):
        if not self.type_:
            return []
        return [x.id for x in self.type_.decisions]

    @fields.depends('type_')
    def on_change_with_type_code(self, name=None):
        if not self.type_:
            return ''
        return self.type_.code

    @fields.depends('finalizable', 'finalizable_result', 'results', 'state')
    def on_change_results(self):
        self.finalizable = True
        self.finalizable_result = False
        if self.state != 'processing':
            return
        for elem in self.results:
            if elem.state != 'waiting':
                continue
            self.finalizable = False
            if elem.final_decision and elem.decision_date:
                self.finalizable_result = True

    @classmethod
    def get_finalizable(cls, underwritings, name):
        pool = Pool()
        decision = pool.get('underwriting.result').__table__()
        underwriting = cls.__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: False for x in underwritings}
        cursor.execute(*underwriting.join(decision, 'LEFT OUTER',
                condition=(decision.underwriting == underwriting.id)
                & (decision.state == 'waiting')
                & (underwriting.state == 'processing')
                ).select(underwriting.id, where=(
                    underwriting.state == 'processing')
                & (decision.id == Null)))

        for underwriting_id, in cursor.fetchall():
            result[underwriting_id] = True
        return result

    @classmethod
    def get_finalizable_result(cls, underwritings, name):
        pool = Pool()
        decision = pool.get('underwriting.result').__table__()
        underwriting = cls.__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: False for x in underwritings}
        cursor.execute(*decision.join(underwriting,
                condition=decision.underwriting == underwriting.id
                ).select(underwriting.id, where=(
                    underwriting.state == 'processing')
                & (decision.state == 'waiting')
                & (decision.final_decision != Null)
                & (decision.decision_date != Null)))

        for underwriting_id, in cursor.fetchall():
            result[underwriting_id] = True
        return result

    @classmethod
    def search_finalizable(cls, name, clause):
        pool = Pool()
        decision = pool.get('underwriting.result').__table__()
        underwriting = cls.__table__()

        if (clause[1] == '=' and clause[2] is True) or (
                clause[1] == '!=' and clause[2] is False):
            expected = True
        else:
            expected = False
        query = underwriting.join(decision, 'LEFT OUTER',
            condition=(decision.underwriting == underwriting.id)
            & (decision.state == 'waiting')
            & (underwriting.state == 'processing')
            ).select(underwriting.id, where=(
                    underwriting.state == 'processing')
                & (decision.id == Null))

        return [('id', 'in' if expected else 'not in', query)]

    @classmethod
    def search_finalizable_result(cls, name, clause):
        pool = Pool()
        decision = pool.get('underwriting.result').__table__()
        underwriting = cls.__table__()

        if (clause[1] == '=' and clause[2] is True) or (
                clause[1] == '!=' and clause[2] is False):
            expected = True
        else:
            expected = False
        query = decision.join(underwriting,
            condition=decision.underwriting == underwriting.id
            ).select(underwriting.id, where=(
                underwriting.state == 'processing')
            & (decision.state == 'waiting')
            & (decision.final_decision != Null)
            & (decision.decision_date != Null))

        return [('id', 'in' if expected else 'not in', query)]

    @classmethod
    @model.CoogView.button
    def draft(cls, underwritings):
        if any(x.state != 'processing' for x in underwritings):
            cls.raise_user_error('cannot_draft')
        for underwriting in underwritings:
            for result in underwriting.results:
                if result.state == 'finalized':
                    cls.raise_user_error('cannot_draft_result')
        cls.write(underwritings, {'state': 'draft'})

    @classmethod
    @model.CoogView.button
    def process(cls, underwritings):
        Event = Pool().get('event')
        cls.create_documents(underwritings)
        cls.write(underwritings, {
                'state': 'processing',
                })
        Event.notify_events(underwritings, 'underwriting_validated')

    @classmethod
    def create_documents(cls, underwritings):
        Line = Pool().get('document.request.line')
        to_create = []
        for underwriting in underwritings:
            existing = {x.document_desc.code
                for x in underwriting.requested_documents}
            for key, data in underwriting.type_.calculate_documents(
                    underwriting).iteritems():
                if key in existing:
                    # TODO : Handle update / deletion ?
                    continue
                to_create.append(underwriting.add_document(key, data))
        if to_create:
            Line.save(to_create)

    def add_document(self, document_code, data):
        pool = Pool()
        doc_desc = pool.get('document.description').get_document_per_code(
            document_code)
        line = pool.get('document.request.line')()
        line.document_desc = doc_desc
        line.for_object = self
        for k, v in data.iteritems():
            setattr(line, k, v)
        return line

    @classmethod
    @model.CoogView.button
    def complete(cls, underwritings, abandon=False):
        pool = Pool()
        Event = pool.get('event')
        Result = pool.get('underwriting.result')
        if abandon:
            Result.write(Result.search([
                        ('underwriting', 'in', [x.id for x in underwritings]),
                        ('state', '=', 'waiting'),
                        ]), {'state': 'abandonned'})
        else:
            with model.error_manager():
                for underwriting in underwritings:
                    underwriting.check_completable()
        cls.write(underwritings, {
                'state': 'completed',
                })
        copies_per_date = defaultdict(list)
        valid_underwritings = []
        for underwriting in underwritings:
            if any((x.state == 'finalized' for x in underwriting.results)):
                valid_underwritings.append(underwriting)
        for underwriting in valid_underwritings:
            if underwriting.type_.next_underwriting:
                copies_per_date[max(x.effective_decision_end
                        for x in underwriting.results)].append(underwriting)
        for date, underwritings in copies_per_date.iteritems():
            cls.plan_underwriting(underwritings, coog_date.add_day(date, 1))
        Event.notify_events(underwritings, 'underwriting_completed')

    def check_completable(self):
        for result in self.results:
            if result.state not in ('finalized', 'abandonned'):
                self.append_functional_error('non_completed_result',
                    {'target': result.target.rec_name})

    @classmethod
    @model.CoogView.button_action('underwriting.act_plan_underwriting')
    def plan_button(cls, instances):
        pass

    @classmethod
    def plan_underwriting(cls, underwritings, date):
        copies = []
        for elem in underwritings:
            copies.append(elem._get_planned_duplicate(date))
        cls.save(copies)
        return copies

    def _get_planned_duplicate(self, date):
        return self.type_.new_underwriting(self.on_object, self.party,
            [(date, x.target) for x in self.results])

    def init_dict_for_rule_engine(self, data):
        data['underwriting'] = self
        if hasattr(self.on_object, 'init_dict_for_rule_engine'):
            self.on_object.init_dict_for_rule_engine(data)

    def get_contact(self):
        return self.party


class UnderwritingResult(model.CoogSQL, model.CoogView):
    'Underwriting Result'

    __name__ = 'underwriting.result'

    underwriting = fields.Many2One('underwriting', 'Underwriting',
        required=True, select=True, ondelete='CASCADE')
    state = fields.Selection([('waiting', 'Waiting'),
            ('abandonned', 'Abandonned'),
            ('finalized', 'Finalized')], 'State', states={
            'readonly': Eval('state') != 'processing'})
    state_string = state.translated('state')
    target = fields.Reference('Target', [], select=True, required=True,
        states={'readonly': (In(Eval('state'), ['abandonned', 'finalized']))
            | (Eval('underwriting_state') != 'draft')},
        depends=['state', 'underwriting_state'])
    target_description = fields.Function(
        fields.Char('Target'),
        'on_change_with_target_description')
    target_model = fields.Function(
        fields.Char('Target Model', states={'invisible': True}),
        'on_change_with_target_model')
    final_decision = fields.Many2One('underwriting.decision.type',
        'Final Decision', states={
            'required': Eval('state') == 'finalized',
            'readonly': In(Eval('state'), ['abandonned', 'finalized'])},
        domain=[If(Bool(Eval('final_decision', False)),
                ['model', '=', Eval('target_model')], [])],
        depends=['state', 'target_model'], ondelete='RESTRICT')
    decision_date = fields.Date('Decision Date', states={
            'required': Eval('state') == 'finalized',
            'readonly': Eval('state') != 'processing'},
        depends=['state'])
    effective_decision_date = fields.Date('Effective Decision Date', states={
            'required': Eval('state') != 'draft',
            'readonly': Eval('state') != 'waiting'},
        depends=['state'])
    effective_decision_end = fields.Date('Effective Decision End', states={
            'required': Eval('end_date_required') & (
                (Eval('state') == 'finalized') |
                Bool(Eval('final_decision', False))),
            },
        domain=['OR', ('effective_decision_end', '=', None),
            ('effective_decision_end', '>=', Eval('effective_decision_date'))],
        depends=['effective_decision_date', 'final_decision',
            'end_date_required', 'state'])
    provisional_decision = fields.Function(
        fields.Many2One('underwriting.decision.type', 'Provisional Decision',
            states={'invisible': Eval('state') != 'waiting'},
            depends=['state']),
        'get_provisional_decision')
    end_date_required = fields.Function(
        fields.Boolean('End Date Required'),
        'get_end_date_required')
    underwriting_state = fields.Function(
        fields.Selection([], 'Underwriting State'),
        'get_underwriting_state')
    underwriting_state_string = underwriting_state.translated(
        'underwriting_state')

    @classmethod
    def __setup__(cls):
        super(UnderwritingResult, cls).__setup__()
        cls._buttons.update({
                'finalize': {
                    'invisible': (Eval('underwriting_state') == 'draft')
                    | In(Eval('state'), ['abandonned', 'finalized']),
                    'readonly': ~Eval('final_decision') |
                    ~Eval('effective_decision_date'),
                    },
                'abandon': {
                    'invisible': (Eval('underwriting_state') == 'draft')
                    | In(Eval('state'), ['abandonned', 'finalized']),
                    }})

    @classmethod
    def __post_setup__(cls):
        pool = Pool()
        Decision = pool.get('underwriting.decision.type')
        Underwriting = pool.get('underwriting')
        cls.target.selection = list(Decision.model.selection)
        cls.underwriting_state._field.selection = list(
            Underwriting.state.selection)
        super(UnderwritingResult, cls).__post_setup__()

    @classmethod
    def write(cls, *args):
        params = iter(args)
        finalized, abandonned = [], []
        for instances, values in zip(params, params):
            if 'state' not in values:
                continue
            if values['state'] == 'finalized':
                assert all(x.state == 'waiting' for x in instances)
                finalized += instances
            elif values['state'] == 'abandonned':
                assert all(x.state == 'waiting' for x in instances)
                abandonned += instances
        super(UnderwritingResult, cls).write(*args)
        if finalized:
            cls.do_finalize(finalized)
        if abandonned:
            cls.do_abandon(finalized)

    @classmethod
    def default_state(cls):
        return 'waiting'

    @fields.depends('end_date_required', 'provisional_decision',
        'underwriting', 'underwriting_state')
    def on_change_underwriting(self):
        if not self.underwriting:
            return
        self.provisional_decision = self.underwriting.type_.waiting_decision
        self.decision = self.provisional_decision
        self.underwriting_state = self.underwriting.state
        self.end_date_required = self.underwriting.type_.end_date_required

    @fields.depends('target')
    def on_change_with_target_description(self, name=None):
        if not self.target:
            return ''
        return self.target.rec_name

    @fields.depends('target')
    def on_change_with_target_model(self, name=None):
        if not self.target:
            return ''
        return self.target.__name__

    def get_decision(self):
        if self.state == 'finalized':
            return self.final_decision
        return self.provisional_decision

    def get_provisional_decision(self, name):
        return self.underwriting.type_.waiting_decision.id

    def get_end_date_required(self, name):
        return self.underwriting.type_.end_date_required

    def get_underwriting_state(self, name):
        return self.underwriting.state

    def get_rec_name(self, name):
        return '[%s - %s] %s' % (self.state_string,
            coog_string.translate_value(self, 'effective_decision_date'),
            self.provisional_decision.rec_name
            if self.state != 'finalized'
            else self.final_decision.rec_name)

    @model.CoogView.button_change('decision_date', 'final_decision', 'state')
    def finalize(self):
        assert self.state == 'waiting'
        self.decision_date = utils.today()
        self.state = 'finalized'

    @model.CoogView.button_change('decision_date', 'state')
    def abandon(self):
        assert self.state == 'waiting'
        self.decision_date = utils.today()
        self.state = 'abandonned'

    @classmethod
    def do_finalize(cls, instances):
        Pool().get('event').notify_events(instances,
            'underwriting_result_finalized')

    @classmethod
    def do_abandon(cls, instances):
        Pool().get('event').notify_events(instances,
            'underwriting_result_abandonned')

    def init_dict_for_rule_engine(self, data):
        self.underwriting.init_dict_for_rule_engine(data)
        data['underwriting_result'] = self
        if hasattr(self.target, 'init_dict_for_rule_engine'):
            self.target.init_dict_for_rule_engine(data)


class PlanUnderwriting(Wizard):
    'Plan Underwriting'

    __name__ = 'underwriting.plan'

    start_state = 'select_date'
    select_date = StateView('underwriting.plan.date',
        'underwriting.underwriting_plan_date_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Plan Copy', 'plan_copy', 'tryton-go-next',
                default=True)])
    plan_copy = StateTransition()
    open_created = StateAction('underwriting.act_underwriting')

    def default_select_date(self, name):
        assert Transaction().context.get('active_model', '') == 'underwriting'
        underwriting = Pool().get('underwriting')(
            Transaction().context.get('active_id'))
        return {
            'underwriting': underwriting.id,
            }

    def transition_plan_copy(self):
        copy, = self.select_date.underwriting.plan_underwriting(
            [self.select_date.underwriting], self.select_date.date)
        self.select_date.planned_copy = copy
        return 'open_created'

    def do_open_created(self, action):
        return action, {
            'res_ids': [self.select_date.planned_copy.id],
            'res_id': self.select_date.planned_copy.id,
            'res_model': 'underwriting',
            }


class PlanUnderwritingDate(model.CoogView):
    'Underwriting Plan Date'

    __name__ = 'underwriting.plan.date'

    underwriting = fields.Many2One('underwriting', 'Underwriting',
        readonly=True)
    date = fields.Date('Date', required=True)
    planned_copy = fields.Many2One('underwriting', 'Planned Copy',
        readonly=True)
