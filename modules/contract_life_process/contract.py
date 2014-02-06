from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, utils


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'CoveredData',
    ]


class Contract:
    __name__ = 'contract'

    def set_subscriber_as_covered_element(self):
        CoveredElement = Pool().get('contract.covered_element')
        subscriber = self.get_policy_owner(self.start_date)
        if not utils.is_none(self, 'covered_elements'):
            for covered_element in self.covered_elements:
                if covered_element.party == subscriber:
                    return True
            CoveredElement.delete(self.covered_elements)

        covered_element = CoveredElement()
        covered_element.start_date = self.start_date
        item_descs = CoveredElement.get_possible_item_desc(self)
        covered_element.contract = self
        item_descs = CoveredElement.get_possible_item_desc(self)
        if len(item_descs) == 1:
            item_desc = item_descs[0]
            if (subscriber.is_person and item_desc.kind == 'person'
                    or subscriber.is_company and item_desc.kind == 'company'
                    or item_desc.kind == 'party'):
                covered_element.party = subscriber
            covered_element.item_desc = item_desc
            covered_element.main_contract = self
            cov_as_dict = covered_element.on_change_item_desc()
            for key, val in cov_as_dict.iteritems():
                setattr(covered_element, key, val)
        if not hasattr(self, 'covered_elements'):
            self.covered_elements = [covered_element]
        else:
            self.covered_elements = list(self.covered_elements)
            self.covered_elements.append(covered_element)
        return True


class CoveredData:
    __name__ = 'contract.covered_data'

    coverage_amount_selection = fields.Function(
        fields.Selection('get_possible_amounts', 'Coverage Amount',
            depends=['option', 'start_date', 'coverage_amount',
                'with_coverage_amount'], sort=False,
            states={
                'invisible': ~Eval('with_coverage_amount'),
                # 'required': ~~Eval('with_coverage_amount'),
                }),
        'get_coverage_amount_selection', 'setter_void')
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

    @classmethod
    def __setup__(cls):
        super(CoveredData, cls).__setup__()
        cls._error_messages.update({
                'coverage_amount_needed': 'A coverage amount must be provided',
                })

    @fields.depends('option', 'start_date', 'covered_element', 'currency')
    def get_possible_amounts(self):
        return super(CoveredData, self).get_possible_amounts()

    def get_coverage_amount_selection(self, name):
        if (hasattr(self, 'coverage_amount') and self.coverage_amount):
            # return '%.2f' % self.coverage_amount
            return self.currency.amount_as_string(self.coverage_amount)
        return ''

    @fields.depends('coverage_amount', 'coverage_amount_selection', 'currency')
    def on_change_coverage_amount_selection(self):
        if not utils.is_none(self, 'coverage_amount_selection'):
            return {'coverage_amount':
                self.currency.get_amount_from_string(
                    self.coverage_amount_selection)}
        else:
            return {'coverage_amount': None}

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
        'need_to_chose_beneficiary_clause', 'beneficiary_clause_selection')
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
            }
        result['clauses'] = {
            'remove': existing_beneficiary_clauses,
            'add': [{
                    'clause': self.beneficiary_clause_selection.id,
                    'override_text':
                    self.beneficiary_clause_selection.may_be_overriden,
                    'contract': self.option.contract.id,
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
