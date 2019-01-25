# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict

from sql import Null, Cast
from sql.operators import Concat
from sql.conditionals import Coalesce, Case
from sql.aggregate import Min, Max, Count

from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateTransition, StateAction
from trytond.wizard import Button
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, Bool, In, Len
from trytond.cache import Cache

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
    manual_activation = fields.Boolean('Manual Activation',
        help='If set, underwritings created with this type will not be '
        'automatically activated by the underwriting activation batch')

    _type_per_code_cache = Cache('_get_underwriting_type_from_code')

    @staticmethod
    def default_manual_activation():
        return False

    @classmethod
    def _export_skips(cls):
        return super(UnderwritingType, cls)._export_skips() | set(
            ['documents'])

    @classmethod
    def _export_light(cls):
        return super(UnderwritingType, cls)._export_light() | {'decisions',
            'waiting_decision'}

    @classmethod
    def create(cls, *args):
        res = super(UnderwritingType, cls).create(*args)
        cls._type_per_code_cache.clear()
        return res

    @classmethod
    def write(cls, *args):
        super(UnderwritingType, cls).write(*args)
        cls._type_per_code_cache.clear()

    @classmethod
    def delete(cls, *args):
        super(UnderwritingType, cls).delete(*args)
        cls._type_per_code_cache.clear()

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

    @classmethod
    def get_type_from_code(cls, code):
        cached = cls._type_per_code_cache.get(code, -1)
        if cached != -1:
            return cls(cached) if cached else None
        to_cache = cls.search([('code', '=', code)])
        cls._type_per_code_cache.set(code, to_cache[0].id if to_cache else None)
        return to_cache[0]


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
    result_descriptions = fields.Function(
        fields.Text('Decision Descriptions'),
        'getter_result_descriptions')
    document_request_descriptions = fields.Function(
        fields.Text('Document Requests Descriptions'),
        'getter_document_request_descriptions')
    type_code = fields.Function(
        fields.Char('Type Code'),
        'on_change_with_type_code')
    sub_status = fields.Function(fields.Selection([
                ('finalized', 'Finalized'),
                ('abandoned', 'Abandoned'),
                ('mixed', 'Mixed')
                ], 'Sub-status', depends=['results', 'state'], states={
                'invisible': Eval('state') != 'completed'}),
        'getter_sub_status', searcher='search_sub_status')
    documents_received = fields.Function(
        fields.Boolean('Documents received', depends=['requested_documents']),
        'on_change_with_documents_received',
        searcher='search_documents_received')
    effective_date = fields.Function(
        fields.Date('Effective Date'),
        'getter_effective_date', searcher='search_effective_date')
    new_result = fields.Function(
        fields.Selection('select_possible_results', 'New result',
            states={'readonly': Eval('state') != 'draft',
                'invisible': Eval('state') != 'draft'},
            depends=['state']),
        'getter_new_result', 'setter_void')

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
                'add_new_result': {
                    'readonly': ~Eval('new_result'),
                    'invisible': Eval('state') != 'draft',
                    },
                })
        cls._error_messages.update({
                'cannot_draft': 'Cannot draft completed underwritings',
                'cannot_draft_result': 'Cannot draft completed results',
                'non_completed_result': 'Results must be finalized first',
                'document_received_string': 'Received',
                'document_not_received_string': 'Not Received',
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

    @fields.depends('requested_documents')
    def on_change_with_documents_received(self, name=None):
        return all(x.received for x in self.requested_documents)

    @classmethod
    def search_documents_received(cls, name, clause):
        underwriting = cls.__table__()
        pool = Pool()
        document_request = pool.get('document.request.line').__table__()
        query = underwriting.join(document_request,
            condition=document_request.for_object ==
            Concat('underwriting,', Cast(underwriting.id, 'VARCHAR'))
            ).select(underwriting.id,
            where=(document_request.reception_date == Null))
        if (clause[1] == '=' and not clause[2]) \
                or (clause[1] == '!=' and clause[2]):
            domain = [('id', 'in', query)]
        elif (clause[1] == '=' and clause[2]) \
                or (clause[1] == '!=' and not clause[2]):
            domain = [('id', 'not in', query)]
        return domain

    @classmethod
    def getter_effective_date(cls, underwritings, name):
        pool = Pool()
        decision = pool.get('underwriting.result').__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: datetime.date.max for x in underwritings}
        cursor.execute(*decision.select(decision.underwriting,
                Min(Coalesce(decision.effective_decision_date,
                        datetime.date.max)),
                where=decision.underwriting.in_([x.id for x in underwritings]),
                group_by=[decision.underwriting],
                ))

        for underwriting_id, date in cursor.fetchall():
            result[underwriting_id] = date
        return result

    @classmethod
    def getter_sub_status(cls, underwritings, name):
        pool = Pool()
        result = pool.get('underwriting.result').__table__()
        cursor = Transaction().connection.cursor()

        status = {x.id: '' for x in underwritings}
        cursor.execute(*result.select(result.underwriting,
                Case((Count(result.state, distinct=True) > 1, 'mixed'),
                    else_=Max(result.state)), where=result.state != 'waiting',
                group_by=result.underwriting
                ))

        for underwriting_id, sub_status in cursor.fetchall():
            status[underwriting_id] = sub_status
        return status

    def getter_new_result(self, name):
        return ''

    def getter_result_descriptions(self, name):
        descs = []
        for result in self.results:
            desc = [result.provisional_decision.rec_name
                if result.state != 'finalized'
                else result.final_decision.rec_name,
                coog_string.translate_value(result, 'effective_decision_date'),
                coog_string.translate_value(result, 'effective_decision_end')]
            desc = ' - '.join([x for x in desc if x])
            descs.append(desc)
        return '\n'.join(descs)

    def getter_document_request_descriptions(self, name):
        return '\n'.join(['%s (%s)' % (x.document_desc.name,
                    self.raise_user_error('document_received_string'
                        if x.received else 'document_not_received_string',
                        raise_exception=False))
                for x in self.requested_documents])

    @fields.depends('on_object', 'party', 'results')
    def select_possible_results(self):
        possible = {'': ''}
        existing = set()
        for result in self.results or []:
            existing.add(str(result))
        for elem in self.get_possible_result_targets():
            if not elem or str(elem) in existing:
                continue
            possible[str(elem)] = elem.rec_name
        return [(k, v) for k, v in list(possible.items())]

    def get_possible_result_targets(self):
        result = [self.party] if self.party else []
        if self.on_object and self.on_object.id >= 0:
            result.append(self.on_object)
        return result

    @model.CoogView.button_change('new_result', 'on_object', 'results',
        'state', 'type_')
    def add_new_result(self):
        assert self.new_result
        self.results = list(self.results or []) + [self._new_result()]
        self.new_result = ''

    def _new_result(self):
        Result = Pool().get('underwriting.result')
        result = Result(target=self.new_result, underwriting=self,
            state='waiting')
        result.on_change_underwriting()
        return result

    @classmethod
    def search_sub_status(cls, name, clause):
        pool = Pool()
        result = pool.get('underwriting.result').__table__()
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        query = result.select(result.underwriting,
            where=(result.state != 'waiting'), group_by=result.underwriting,
            having=Operator(Case((Count(result.state, distinct=True) > 1,
                        'mixed'), else_=Max(result.state)),
                cls.sub_status.sql_format(value)))

        return [('id', 'in', query)]

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

    def get_rec_name(self, name):
        return self.type_.name + ' - ' + self.party.rec_name

    @classmethod
    def search_effective_date(cls, name, clause):
        pool = Pool()
        decision = pool.get('underwriting.result').__table__()
        underwriting = cls.__table__()
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        query = underwriting.join(decision, 'LEFT OUTER',
            condition=(decision.underwriting == underwriting.id)
            ).select(underwriting.id, group_by=[underwriting.id],
                having=Operator(Min(Coalesce(decision.effective_decision_date,
                            datetime.date.max)),
                    cls.effective_date.sql_format(value)))

        return [('id', 'in', query)]

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
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('party.rec_name',) + tuple(clause[1:]),
            ('type_.name',) + tuple(clause[1:]),
            ]

    @classmethod
    def order_effective_date(cls, tables):
        decision_order = tables.get('decision_order')
        if decision_order is not None:
            return [decision_order[None][0].order]

        table, _ = tables[None]
        decision = Pool().get('underwriting.result').__table__()

        query_table = table.join(decision, 'LEFT OUTER', condition=(
                decision.underwriting == table.id)
            ).select(table.id, Min(
                Coalesce(decision.effective_decision_date,
                    datetime.date.max)).as_('order'),
            group_by=[table.id])
        tables['decision_order'] = {
            None: (query_table,
                (query_table.id == table.id)
                )}

        return [query_table.order]

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
                    underwriting).items():
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
        for k, v in data.items():
            setattr(line, k, v)
        return line

    @classmethod
    @model.CoogView.button
    def complete(cls, underwritings, default_action=None):
        pool = Pool()
        Event = pool.get('event')
        with model.error_manager():
            for underwriting in underwritings:
                if default_action:
                    for result in underwriting.results:
                        if result.state != 'waiting':
                            continue
                        getattr(result, default_action)()
                    underwriting.results = list(underwriting.results)
                else:
                    underwriting.check_completable()
                underwriting.state = 'completed'
        cls.save(underwritings)
        copies_per_date = defaultdict(list)
        valid_underwritings = []
        for underwriting in underwritings:
            if any((x.state == 'finalized' for x in underwriting.results)):
                valid_underwritings.append(underwriting)
        for underwriting in valid_underwritings:
            if underwriting.type_.next_underwriting:
                copies_per_date[max(
                        (x.effective_decision_end or datetime.date.min)
                        for x in underwriting.results)
                    ].append(underwriting)
        for date, underwritings in copies_per_date.items():
            cls.plan_underwriting(underwritings, coog_date.add_day(date, 1))
        Event.notify_events(underwritings, 'underwriting_completed')

    def check_completable(self):
        for result in self.results:
            if result.state not in ('finalized', 'abandoned'):
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
        return self.type_.next_underwriting.new_underwriting(self.on_object,
            self.party, [(date, x.target) for x in self.results])

    def init_dict_for_rule_engine(self, data):
        data['underwriting'] = self
        if hasattr(self.on_object, 'init_dict_for_rule_engine'):
            self.on_object.init_dict_for_rule_engine(data)

    def get_contact(self):
        return self.party

    def get_sender(self):
        return self.on_object.get_sender()

    def get_recipients(self):
        res = set()
        if self.party:
            res.add(self.party)
        return list(res | set(self.on_object.get_recipients()))


class UnderwritingResult(model.CoogSQL, model.CoogView):
    'Underwriting Result'

    __name__ = 'underwriting.result'

    underwriting = fields.Many2One('underwriting', 'Underwriting',
        required=True, select=True, ondelete='CASCADE')
    state = fields.Selection([('waiting', 'Waiting'),
            ('abandoned', 'Abandoned'),
            ('finalized', 'Finalized')], 'State', states={
            'readonly': Eval('state') != 'processing'})
    state_string = state.translated('state')
    target = fields.Reference('Target', [], select=True, required=True,
        states={'readonly': (In(Eval('state'), ['abandoned', 'finalized']))
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
            'readonly': In(Eval('state'), ['abandoned', 'finalized'])},
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
                    | In(Eval('state'), ['abandoned', 'finalized']),
                    'readonly': ~Eval('final_decision') |
                    ~Eval('effective_decision_date'),
                    },
                'abandon': {
                    'invisible': (Eval('underwriting_state') == 'draft')
                    | In(Eval('state'), ['abandoned', 'finalized']),
                    }})
        cls._error_messages.update({
                'result_wait_expected': 'The underwriting result \'%s\' should'
                ' be in \'waiting\' state instead of \'%s\''
                })

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
        finalized, abandoned = [], []
        with model.error_manager():
            for instances, values in zip(params, params):
                if 'state' not in values:
                    continue
                if values['state'] in ['finalized', 'abandoned']:
                    for instance in instances:
                        if instance.state != 'waiting':
                            cls.append_functional_error(
                                'result_wait_expected', (instance.rec_name,
                                    coog_string.translate_value(
                                        instance, 'state')))
                if values['state'] == 'finalized':
                    finalized += instances
                elif values['state'] == 'abandoned':
                    abandoned += instances
        super(UnderwritingResult, cls).write(*args)
        if finalized:
            cls.do_finalize(finalized)
        if abandoned:
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
        if self.state != 'waiting':
            self.__class__.raise_user_error('result_wait_expected',
                (self.rec_name, coog_string.translate_value(self, 'state')))
        self.decision_date = utils.today()
        self.state = 'finalized'

    @model.CoogView.button_change('decision_date', 'state')
    def abandon(self):
        if self.state != 'waiting':
            self.__class__.raise_user_error('result_wait_expected',
                (self.rec_name, coog_string.translate_value(self, 'state')))
        self.decision_date = utils.today()
        self.state = 'abandoned'

    @classmethod
    def do_finalize(cls, results):
        Pool().get('event').notify_events(results,
            'underwriting_result_finalized')

    @classmethod
    def do_abandon(cls, instances):
        Pool().get('event').notify_events(instances,
            'underwriting_result_abandoned')

    def init_dict_for_rule_engine(self, data):
        self.underwriting.init_dict_for_rule_engine(data)
        data['underwriting_result'] = self
        if hasattr(self.target, 'init_dict_for_rule_engine'):
            self.target.init_dict_for_rule_engine(data)


class OpenGeneratedUnderwritingChoice(model.CoogView):
    'Open Generated Underwriting Choice'

    __name__ = 'underwriting.generated.open.choice'

    generated_underwriting = fields.Many2One('underwriting',
        'Generated Underwriting', readonly=True)
    info = fields.Text('Info', readonly=True)


class OpenGeneratedUnderwriting(Wizard):
    'Open Generated Underwriting'

    __name__ = 'underwriting.generated.open'

    start_state = 'detect'
    detect = StateTransition()
    choice = StateView('underwriting.generated.open.choice',
        'underwriting.underwriting_generated_open_choice_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_generated', 'tryton-go-next',
                default=True)])
    open_generated = StateAction('underwriting.act_generated_underwriting')

    @classmethod
    def __setup__(cls):
        super(OpenGeneratedUnderwriting, cls).__setup__()
        cls._error_messages.update({
                'ask_open_generated':
                'Do you want to open the generated underwriting?'
                })

    def get_generated(self):
        current = Transaction().context.get('active_id')
        if not current:
            return
        Underwriting = Pool().get('underwriting')
        current = Underwriting(current)
        return Underwriting.search([
                ('on_object', '=', str(current.on_object)),
                ('create_date', '>=', current.write_date),
                ('create_uid', '=', Transaction().user)],
            order=[('id', 'DESC')])

    def transition_detect(self):
        res = self.get_generated()
        if not res:
            return 'end'
        return 'choice'

    def default_choice(self, name):
        res = self.get_generated()
        info = self.raise_user_error('ask_open_generated',
            raise_exception=False)
        return {
            'generated_underwriting': res[0].id,
            'info': info,
            }

    def do_open_generated(self, action):
        return action, {
            'res_ids': [self.choice.generated_underwriting.id],
            'res_id': self.choice.generated_underwriting.id,
            'res_model': 'underwriting',
            }


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
