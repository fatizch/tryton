# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pyson import Eval, Len, If
from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import model, fields, utils
from trytond.modules.endorsement import (EndorsementWizardStepMixin,
    add_endorsement_step)


__metaclass__ = PoolMeta
__all__ = [
    'ManageClauses',
    'ClauseDisplayer',
    'StartEndorsement',
    ]


class ManageClauses(EndorsementWizardStepMixin):
    'Manage Clauses'

    __name__ = 'contract.manage_clauses'

    contract = fields.Many2One('endorsement.contract', 'Contract',
        domain=[('id', 'in', Eval('possible_contracts', []))],
        states={'invisible': Len(Eval('possible_contracts', [])) == 1},
        depends=['possible_contracts'])
    possible_contracts = fields.Many2Many('endorsement.contract', None, None,
        'Possible Contracts')
    all_clauses = fields.One2Many('contract.manage_clauses.clause',
        None, 'All Clauses')
    current_clauses = fields.One2Many(
        'contract.manage_clauses.clause', None, 'Current Clauses')
    new_clause = fields.Many2One('clause', 'New Clause',
        domain=[('id', 'in', Eval('possible_clauses'))],
        depends=['possible_clauses'])
    possible_clauses = fields.Many2Many('clause', None, None,
        'Possible Clauses')

    @classmethod
    def __setup__(cls):
        super(ManageClauses, cls).__setup__()
        cls._buttons.update({'add_clause': {
                    'readonly': ~Eval('new_clause')},
                'add_text_clause': {}})

    @classmethod
    def view_attributes(cls):
        return super(ManageClauses, cls).view_attributes() + [(
                '/form/group[@id="invisible"]',
                'states',
                {'invisible': True})]

    @fields.depends('all_clauses', 'contract', 'current_clauses',
        'possible_clauses')
    def on_change_contract(self):
        self.update_all_clauses()
        self.update_current_clauses()
        self.update_possible_clauses()

    @fields.depends('contract', 'current_clauses', 'possible_clauses')
    def on_change_current_clauses(self):
        self.update_possible_clauses()

    def update_all_clauses(self):
        if not self.current_clauses:
            return
        new_clauses = list(self.current_clauses)
        for clause in self.all_clauses:
            if clause.contract == new_clauses[0].contract:
                continue
            new_clauses.append(clause)
        self.all_clauses = new_clauses

    def update_current_clauses(self):
        new_clauses = []
        for clause in self.all_clauses:
            if clause.contract == self.contract:
                new_clauses.append(clause)
        self.current_clauses = new_clauses

    def update_possible_clauses(self):
        self.new_clause = None
        current_clauses = {
            x.clause for x in self.current_clauses
            if x.action != 'remove' and x.clause is not None
            }
        self.possible_clauses = list(
            self.get_all_possible_clauses(self.contract) - current_clauses)

    def get_all_possible_clauses(self, contract_endorsement):
        return {clause
            for clause in contract_endorsement.contract.product.clauses}

    def step_default(self, field_names):
        defaults = super(ManageClauses, self).step_default()
        possible_contracts = self.wizard.endorsement.contract_endorsements
        defaults['possible_contracts'] = [x.id for x in possible_contracts]
        per_contract = {x: self.get_updated_clauses_from_contract(x)
            for x in possible_contracts}

        all_clauses = []
        for contract, clauses in per_contract.iteritems():
            all_clauses += self.generate_displayers(contract, clauses)
        defaults['all_clauses'] = [x._changed_values for x in all_clauses]
        if defaults['possible_contracts']:
            defaults['contract'] = defaults['possible_contracts'][0]
        defaults['new_clause'] = None
        return defaults

    def step_update(self):
        self.update_all_clauses()
        endorsement = self.wizard.endorsement
        per_contract = defaultdict(list)
        for clause in self.all_clauses:
            per_contract[clause.contract].append(clause)

        for contract, clauses in per_contract.iteritems():
            self.update_endorsed_clauses(contract, clauses)

        new_endorsements = []
        for contract_endorsement in per_contract.keys():
            self._update_endorsement(contract_endorsement,
                contract_endorsement.contract._save_values)
            if not contract_endorsement.clean_up():
                new_endorsements.append(contract_endorsement)
        endorsement.contract_endorsements = new_endorsements
        endorsement.save()

    def update_endorsed_clauses(self, contract_endorsement, clauses):
        per_id = {x.id: x for x in contract_endorsement.contract.clauses}
        for clause in clauses:
            if clause.action == 'nothing':
                self._update_nothing(contract_endorsement.contract, clause,
                    per_id)
                continue
            if clause.action == 'removed':
                self._update_removed(contract_endorsement.contract, clause,
                    per_id)
                continue
            if clause.action == 'added':
                self._update_added(contract_endorsement.contract, clause,
                    per_id)
                continue
            if clause.action == 'modified':
                self._update_modified(contract_endorsement.contract, clause,
                    per_id)
                continue

    def _update_nothing(self, contract, clause, per_id):
        # Cancel modifications
        assert clause.clause_id
        Clause = Pool().get('contract.clause')
        prev_clause = Clause(clause.clause_id)
        clause = per_id[clause.clause_id]
        clause.text = prev_clause.text
        clause.clause = prev_clause.clause

    def _update_removed(self, contract, clause, per_id):
        if not clause.clause_id:
            return
        per_id.pop(clause.clause_id)
        contract.clauses = [x for x in contract.clauses
            if x.id != clause.clause_id]

    def _update_added(self, contract, clause, per_id):
        contract.clauses += (clause.to_clause(),)

    def _update_modified(self, contract, clause, per_id):
        assert clause.clause_id
        per_id[clause.clause_id].text = clause.text
        per_id[clause.clause_id].clause = clause.clause

    def get_updated_clauses_from_contract(self, contract_endorsement):
        contract = contract_endorsement.contract
        utils.apply_dict(contract, contract_endorsement.apply_values())
        return self.get_contract_clauses(contract)

    def get_contract_clauses(self, contract):
        return list(contract.clauses)

    def generate_displayers(self, contract_endorsement, clauses):
        pool = Pool()
        Contract = pool.get('contract')
        Clause = pool.get('contract.manage_clauses.clause')
        contract = contract_endorsement.contract
        existing_clauses = {x.id: x for x in Contract(contract.id).clauses}
        all_clauses = []
        for clause in clauses:
            displayer = Clause.new_displayer(clause)
            displayer.contract = contract_endorsement
            displayer.contract_rec_name = contract.rec_name
            if displayer.clause_id:
                existing_clauses.pop(displayer.clause_id)
                if clause._save_values:
                    displayer.action = 'modified'
                else:
                    displayer.action = 'nothing'
            all_clauses.append(displayer)

        for clause in existing_clauses.values():
            displayer = Clause. new_displayer(clause)
            displayer.contract = contract_endorsement
            displayer.contract_rec_name = contract.rec_name
            displayer.action = 'removed'
            all_clauses.append(displayer)
        return all_clauses

    @classmethod
    def state_view_name(cls):
        return 'endorsement_clause.contract_manage_clauses_view_form'

    @model.CoopView.button_change('contract', 'current_clauses', 'new_clause',
        'possible_clauses')
    def add_clause(self):
        assert self.new_clause
        new_clause = self.create_clause()
        self.new_clause = None
        self.current_clauses = list(self.current_clauses) + [new_clause]
        self.update_possible_clauses()

    def create_clause(self):
        new_clause = Pool().get('contract.manage_clauses.clause')()
        new_clause.clause = self.new_clause
        new_clause.text = self.new_clause.content
        new_clause.clause_id = None
        new_clause.action = 'added'
        new_clause.contract = self.contract
        new_clause.display_name = 'New clause (%s)' % (
            self.new_clause.rec_name)
        new_clause.customizable = self.new_clause.customizable
        return new_clause

    @model.CoopView.button_change('contract', 'current_clauses')
    def add_text_clause(self):
        Clause = Pool().get('contract.manage_clauses.clause')
        self.current_clauses = list(self.current_clauses) + [
            Clause(contract=self.contract, clause=None, action='added',
                text='', customizable=True)]


class ClauseDisplayer(model.CoopView):
    'Clause Displayer'

    __name__ = 'contract.manage_clauses.clause'

    action = fields.Selection([('nothing', ''), ('removed', 'Removed'),
        ('modified', 'Modified'), ('added', 'Added')], 'Action',
        domain=[If(Eval('action') == 'modified',
                ('action', 'in', ('modified', 'nothing')),
                If(Eval('action') == 'added',
                    ('action', 'in', ('added', 'removed')),
                    ('action', 'in', ('removed', 'nothing'))))],
        depends=['action'])
    contract = fields.Many2One('endorsement.contract', 'Contract',
        readonly=True)
    contract_rec_name = fields.Char('Contract', readonly=True)
    display_name = fields.Char('Name', readonly=True)
    clause = fields.Many2One('clause', 'Clause', readonly=True)
    clause_id = fields.Integer('Clause Id', readonly=True)
    customizable = fields.Boolean('Customizable', readonly=True)
    text = fields.Text('Text', states={
            'readonly': ~Eval('customizable', False)},
        depends=['customizable'])

    @fields.depends('action', 'clause', 'clause_id', 'text')
    def on_change_action(self):
        if self.clause_id and self.action == 'nothing':
            self.text = Pool().get('contract.clause')(self.clause_id).text

    @fields.depends('action', 'clause', 'clause_id', 'text')
    def on_change_text(self):
        if not self.clause_id:
            return
        old_text = Pool().get('contract.clause')(self.clause_id).text
        if self.action == 'modified' and self.text == old_text:
            self.action = 'nothing'
        elif self.action == 'nothing' and self.text != old_text:
            self.action = 'modified'

    @classmethod
    def new_displayer(cls, clause):
        displayer = cls()
        if getattr(clause, 'id', None):
            displayer.clause_id = clause.id
            displayer.display_name = clause.rec_name
        else:
            displayer.display_name = 'New Clause (%s)' % (
                clause.clause.rec_name if clause.clause else 'Custom')
            displayer.action = 'added'
            displayer.clause_id = None
        displayer.text = clause.text
        displayer.clause = clause.clause
        if clause.clause:
            displayer.customizable = clause.clause.customizable
        else:
            displayer.customizable = True
        return displayer

    def to_clause(self):
        clause = Pool().get('contract.clause')()
        clause.clause = self.clause
        clause.text = self.text
        return clause

    @classmethod
    def _clause_fields_to_extract(cls):
        return {
            'contract.clause': ['clause', 'text'],
            }


class StartEndorsement:
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsement, ManageClauses,
    'manage_clauses')
