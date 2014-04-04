from decimal import Decimal

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields, model, utils

__metaclass__ = PoolMeta

__all__ = [
    'Beneficiary',
    'ContractClause',
    'ContractOption',
    'Contract',
    ]


class Beneficiary(model.CoopSQL, model.CoopView):
    'Contract Beneficiary'

    __name__ = 'contract.clause.beneficiary'

    accepting = fields.Boolean('Accepting')
    clause = fields.Many2One('contract.clause', 'Clause', required=True,
        ondelete='RESTRICT')
    party = fields.Many2One('party.party', 'Party', states={
            'required': Eval('accepting', False)}, depends=['accepting'],
        ondelete='RESTRICT')
    details = fields.Text('Details', states={'invisible': ~~Eval('accepting')})
    share = fields.Numeric('Share', digits=(4, 4), required=True)
    description = fields.Function(
        fields.Char('Description'),
        'on_change_with_description')

    @fields.depends('party', 'details')
    def on_change_with_description(self, name=None):
        if self.party:
            return self.party.rec_name
        return self.details.splitlines().join(' ')

    @classmethod
    def default_share(cls):
        return Decimal('1')


class ContractClause:
    __name__ = 'contract.clause'

    beneficiaries = fields.One2Many('contract.clause.beneficiary', 'clause',
        'Beneficiaries', states={'invisible': ~Eval('with_beneficiary_list')},
        depends=['with_beneficiary_list'])
    with_beneficiary_list = fields.Function(
        fields.Boolean('With Beneficiay list', states={'invisible': True}),
        'on_change_with_with_beneficiary_list')

    @classmethod
    def __setup__(cls):
        super(ContractClause, cls).__setup__()
        cls._error_messages.update({
                'invalid_beneficiary_shares': 'Total share for clause %s is'
                'invalid',
                })

    @classmethod
    def default_clause(cls):
        default_clause = Transaction().context.get('default_clause', None)
        return default_clause if default_clause else None

    @classmethod
    def default_text(cls):
        default_clause = Transaction().context.get('default_clause', None)
        if not default_clause:
            return None
        Clause = Pool().get('clause')
        return Clause(default_clause).versions[-1].content

    @classmethod
    def default_with_beneficiary_list(cls):
        default_clause = Transaction().context.get('default_clause', None)
        if not default_clause:
            return False
        Clause = Pool().get('clause')
        return Clause(default_clause).with_beneficiary_list

    @classmethod
    def default_customized_text(cls):
        default_clause = Transaction().context.get('default_clause', None)
        if not default_clause:
            return False
        Clause = Pool().get('clause')
        return Clause(default_clause).customizable

    @fields.depends('clause')
    def on_change_with_with_beneficiary_list(self, name=None):
        return self.clause.with_beneficiary_list if self.clause else False

    @classmethod
    def validate(cls, clauses):
        for clause in clauses:
            if not clause.with_beneficiary_list:
                continue
            if not clause.beneficiaries:
                return
            if not(sum((x.share for x in clause.beneficiaries)) ==
                    Decimal('1')):
                cls.raise_user_error('invalid_beneficiary_shares',
                    (clause.rec_name))


class ContractOption:
    __name__ = 'contract.option'

    beneficiary_clauses = fields.One2ManyDomain('contract.clause',
        'option', 'Beneficiary clauses', domain=[
            ('clause.kind', '=', 'beneficiary'),
            ('clause', 'in', Eval('possible_clauses'))],
        context={'default_clause': Eval('default_beneficiary_clause', 0)},
        states={'invisible': ~Bool(Eval('has_beneficiary_clause', False))},
        depends=['possible_clauses', 'has_beneficiary_clause',
            'default_beneficiary_clause'])
    default_beneficiary_clause = fields.Function(
        fields.Many2One('clause', 'Default Beneficiary Clause'),
        'on_change_with_default_beneficiary_clause')
    has_beneficiary_clause = fields.Function(
        fields.Boolean('Has Beneficiary Clause'),
        'on_change_with_has_beneficiary_clause')

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls.clauses = fields.One2ManyDomain.init_from_One2Many(cls.clauses)
        cls.clauses.domain += [('clause.kind', '!=', 'beneficiary')]

    @fields.depends('coverage', 'appliable_conditions_date')
    def on_change_with_default_beneficiary_clause(self, name=None):
        good_rule = utils.find_date(self.coverage.clause_rules,
            self.appliable_conditions_date)
        if good_rule is None or good_rule.default_beneficiary_clause is None:
            return None
        return good_rule.default_beneficiary_clause.id

    @fields.depends('coverage')
    def on_change_with_has_beneficiary_clause(self, name=None):
        good_rule = utils.find_date(self.coverage.clause_rules,
            self.appliable_conditions_date)
        if good_rule is None:
            return False
        for elem in good_rule.clauses:
            if elem.kind == 'beneficiary':
                return True
        return False

    def init_from_coverage(self, coverage, start_date=None, end_date=None):
        super(ContractOption, self).init_from_coverage(coverage, start_date,
            end_date)
        self.beneficiary_clauses = self.init_beneficiary_clauses(coverage)

    def init_beneficiary_clauses(self, coverage):
        if not coverage.clause_rules:
            return None
        good_rule = utils.find_date(coverage.clause_rules,
            self.appliable_conditions_date)
        if not good_rule or not good_rule.default_beneficiary_clause:
            return None
        ContractClause = Pool().get('contract.clause')
        clause = ContractClause()
        the_clause = good_rule.default_beneficiary_clause
        clause.clause = the_clause
        clause_version = the_clause.get_version_at_date(self.start_date)
        if not clause_version:
            clause_version = the_clause.versions[0]
        clause.text = clause_version.content
        return [clause]

    def check_beneficiary_clauses(self):
        if not self.coverage.clause_rules:
            return True, []
        good_rule = utils.find_date(self.coverage.clause_rules,
            self.appliable_conditions_date)
        if not good_rule.has_beneficiary_clauses:
            return True, []
        if not self.beneficiary_clauses:
            return False, [('no_beneficiary_clause_selected', (self.rec_name))]
        return True, []


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._error_messages.update({
                'no_beneficiary_clause_selected': 'No beneficiary clause selected '
                'on %s',
                })

    def check_beneficiary_clauses(self):
        res, errs = True, []
        for option in [x for y in self.covered_elements for x in y.options]:
            option_res, option_errs = option.check_beneficiary_clauses()
            res = res and option_res
            if option_errs:
                errs += option_errs
        return res, errs
