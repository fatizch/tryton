from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta

__all__ = [
    'Beneficiary',
    'ContractClause',
    'CoveredData',
    ]


class Beneficiary(model.CoopSQL, model.CoopView):
    'Contract Beneficiary'

    __name__ = 'contract.clause.beneficiary'

    accepting = fields.Boolean('Accepting')
    clause = fields.Many2One('contract.clause', 'Clause', required=True,
        states={'invisible': True})
    party = fields.Many2One('party.party', 'Party', states={
            'required': ~~Eval('accepting')}, depends=['accepting'])
    incomplete_beneficiary = fields.Text('Incomplete Beneficiary',
        states={'invisible': ~Eval('accepting')}, depends=['accepting'])
    share = fields.Numeric('Share', digits=(4, 4), required=True)
    beneficiary_description = fields.Function(
        fields.Char('Beneficiary Description'),
        'on_change_with_beneficiary_description')

    @fields.depends('party', 'incomplete_beneficiary')
    def on_change_with_beneficiary_description(self, name=None):
        if self.party:
            return self.party.get_rec_name(name)
        return self.incomplete_beneficiary.replace('\n', ' ')


class ContractClause:
    __name__ = 'contract.clause'

    beneficiaries = fields.One2Many('contract.clause.beneficiary', 'clause',
        'Beneficiaries', states={'invisible': ~Eval('with_beneficiary_list')},
        depends=['with_beneficiary_list'])
    with_beneficiary_list = fields.Function(
        fields.Boolean('With Beneficiay list', states={'invisible': True}),
        'on_change_with_with_beneficiary_list')

    @fields.depends('clause')
    def on_change_with_with_beneficiary_list(self, name=None):
        if not self.clause:
            return False
        return self.clause.with_beneficiary_list


class CoveredData:
    __name__ = 'contract.covered_data'

    beneficiary_clause = fields.Function(
        fields.Many2One('clause.contract', 'Beneficiary clause', domain=[
                ('clause.kind', '=', 'beneficiary')]),
        'get_beneficiary_clause')
    need_to_chose_beneficiary_clause = fields.Function(
        fields.Boolean('Need to chose beneficiary clause', states={
                'invisible': True}),
        'on_change_with_need_to_chose_beneficiary_clause')
    possible_beneficiary_clauses = fields.Function(
        fields.One2Many('clause', None,
            'Possible beneficiary Clauses', states={'invisible': True}),
        'on_change_with_possible_beneficiary_clauses')
    beneficiary_clause_selection = fields.Function(
        fields.Many2One('clause',
            'Beneficiary Clause', states={
                'invisible': ~Eval('need_to_chose_beneficiary_clause'),
                'required': ~~Eval('need_to_chose_beneficiary_clause'),
                },
            domain=[('id', 'in', Eval('possible_beneficiary_clauses', []))],
            depends=['possible_beneficiary_clauses']),
        'get_beneficiary_clause_selection', 'setter_void')
    may_override_beneficiary_clause_text = fields.Function(
        fields.Boolean('May override Beneficiary Clause Texte',
            states={'invisible': True}),
        'get_may_override_beneficiary_clause_text')
    beneficiary_clause_override_text = fields.Function(
        fields.Text('Beneficiary Clause Override Text',
            states={'readonly': ~Eval('may_override_beneficiary_clause_text'),
                'invisible': ~Eval('need_to_chose_beneficiary_clause')}),
        'get_beneficiary_clause_override_text', 'setter_void')
    need_beneficiary_list = fields.Function(
        fields.Boolean('Need beneficiary list'),
        'get_need_beneficiary_list')
    beneficiaries = fields.Function(
        fields.One2Many('contract.clause.beneficiary', None, 'Beneficiaries',
            states={'invisible': ~Eval('need_beneficiary_list')},
            depends=['need_beneficiary_list']),
        'get_beneficiaries', 'setter_void')

    @fields.depends('start_date', 'option')
    def on_change_need_to_chose_beneficiary_clause(self):
        return {
            'beneficiary_clause_selection': None,
            'may_override_beneficiary_clause_text': False,
            'beneficiary_clause_override_text': '',
            }

    @fields.depends('start_date', 'option')
    def on_change_with_need_to_chose_beneficiary_clause(self, name=None):
        return len(self.on_change_with_possible_beneficiary_clauses()) > 1

    @fields.depends('option', 'start_date')
    def on_change_with_possible_beneficiary_clauses(self, name=None):
        if not self.option:
            return []
        clauses, errs = self.option.offered.get_result('all_clauses', {
                'date': self.start_date,
                'appliable_conditions_date':
                self.option.contract.appliable_conditions_date,
                })
        if not clauses or errs:
            return []
        beneficiary_clauses = []
        for clause in clauses:
            if clause.kind == 'beneficiary':
                beneficiary_clauses.append(clause)
        return [x.id for x in beneficiary_clauses]

    def get_beneficiary_clause_selection(self, name):
        for clause in self.clauses:
            if clause.clause.kind == 'beneficiary':
                return clause.clause.id
        return None

    @fields.depends('clauses', 'may_override_beneficiary_clause_text',
        'beneficiary_clause_override_text', 'option', 'start_date',
        'need_to_chose_beneficiary_clause', 'beneficiary_clause_selection',
        'beneficiaries')
    def on_change_beneficiary_clause_selection(self):
        if not self.beneficiary_clause_selection:
            return self.on_change_need_to_chose_beneficiary_clause()
        existing_beneficiary_clauses = []
        for clause in self.clauses:
            if clause.clause.kind == 'beneficiary':
                # TODO: It should be possible to break here as there should not
                # be more than one beneficiary clause. To check later.
                existing_beneficiary_clauses.append(clause.id)
        result = {
            'may_override_beneficiary_clause_text':
            self.beneficiary_clause_selection.may_be_overriden,
            'beneficiary_clause_override_text':
            self.beneficiary_clause_selection.get_version_at_date(
                self.start_date).content,
            'need_beneficiary_list':
            self.beneficiary_clause_selection.with_beneficiary_list,
            }
        result['beneficiaries'] = {
            'remove': [x.id for x in self.beneficiaries]}
        result['clauses'] = {
            'remove': existing_beneficiary_clauses,
            'add': [{
                    'clause': self.beneficiary_clause_selection.id,
                    'override_text':
                    self.beneficiary_clause_selection.may_be_overriden,
                    'contract': self.option.contract.id,
                    'beneficiaries': [],
                    'text': (
                        result['beneficiary_clause_override_text']
                        if self.beneficiary_clause_selection.may_be_overriden
                        else '')}]}
        return result

    def get_may_override_beneficiary_clause_text(self, name):
        for clause in self.clauses:
            if clause.clause.kind == 'beneficiary':
                return clause.clause.may_be_overriden
        return False

    @fields.depends('clauses', 'beneficiary_clause_override_text')
    def on_change_beneficiary_clause_override_text(self):
        beneficiary_clause = None
        for clause in self.clauses:
            if clause.clause.kind == 'beneficiary':
                beneficiary_clause = clause
                break
        if not beneficiary_clause:
            # TODO : Raise error ?
            return {}
        return {
            'clauses': {
                'update': [{
                        'id': beneficiary_clause.id,
                        'text': self.beneficiary_clause_override_text}]}}

    def get_beneficiary_clause_override_text(self, name):
        beneficiary_clause = None
        for clause in self.clauses:
            if clause.clause.kind == 'beneficiary':
                beneficiary_clause = clause
                break
        if not beneficiary_clause:
            return ''
        return beneficiary_clause.clause.get_version_at_date(
            self.start_date).content

    def get_need_beneficiary_list(self, name):
        if not self.beneficiary_clause_selection:
            return False
        return self.beneficiary_clause_selection.with_beneficiary_list

    def get_beneficiary_clause(self, name):
        for clause in self.clauses:
            if clause.clause.kind == 'beneficiary':
                return clause.id
        return None

    def get_beneficiaries(self, name):
        if not self.beneficiary_clause:
            return []
        return [x.id for x in self.beneficiary_clause]

    @fields.depends('clauses', 'beneficiaries')
    def on_change_beneficiaries(self):
        beneficiary_clause = None
        for clause in self.clauses:
            if clause.clause.kind == 'beneficiary':
                beneficiary_clause = clause
                break
        if beneficiary_clause is None:
            return {}
        to_delete = [x.id for x in beneficiary_clause.beneficiaries]
        to_add = []
        for elem in self.beneficiaries:
            if elem.id not in to_delete:
                to_add.append(elem)
        to_add = [model.serialize_this(elem) for elem in to_add]
        return {
            'clauses': {
                'update': [{
                        'id': beneficiary_clause.id,
                        'beneficiaries': {
                            'delete': to_delete,
                            'add': to_add}}]}}
