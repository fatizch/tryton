from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.rpc import RPC

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract:
    __name__ = 'contract'

    def update_coverage_amounts_if_needed(self, at_date=None):
        if not at_date:
            at_date = self.start_date
        for covered_element in self.covered_elements:
            values = {}
            to_update = {}
            for option in covered_element.options:
                values[option.coverage.id] = option.coverage_amount
                rule_dict = {'date': at_date}
                option.init_dict_for_rule_engine(rule_dict)
                result, errs = option.coverage.get_result(
                    'dependant_amount_coverage', rule_dict)
                if errs or result is None:
                    continue
                to_update[option] = result.id
            for option, offered in to_update.iteritems():
                option.coverage_amount = values[offered]
                option.save()
        return True

    def check_covered_amounts(self, at_date=None):
        if not at_date:
            at_date = self.start_date
        res, errs = (True, [])
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                if not option.has_coverage_amount:
                    continue
                validity, errors = option.coverage.get_result(
                    'coverage_amount_validity', {
                        'date': at_date,
                        'elem': covered_element,
                        'option': option,
                        'contract': self,
                        'appliable_conditions_date':
                        self.appliable_conditions_date,
                        })
                res = res and (not validity or validity[0])
                if validity:
                    errs += validity[1]
                errs += errors
        return (res, errs)

    @classmethod
    def get_possible_contracts_from_party(cls, party, at_date):
        # TODO : Move to claim ?
        res = super(Contract, cls).get_possible_contracts_from_party(party,
            at_date)
        if not party:
            return res
        for cov_elem in cls.get_possible_covered_elements(party, at_date):
            contract = cov_elem.main_contract
            # TODO : Temporary Hack Date validation should be done with domain
            # and in get_possible_covered_elements
            if contract and contract.is_active_at_date(at_date):
                res.append(contract)
        return res

    @classmethod
    def get_possible_covered_elements(cls, party, at_date):
        # TODO : Move to claim ?
        CoveredElement = Pool().get('contract.covered_element')
        return CoveredElement.get_possible_covered_elements(party, at_date)


class ContractOption:
    __name__ = 'contract.option'

    coverage_amount = fields.Numeric('Coverage Amount', states={
            'invisible': ~Eval('has_coverage_amount'),
            }, depends=['has_coverage_amount'])
    coverage_amount_selection = fields.Function(
        fields.Selection('get_possible_amounts', 'Coverage Amount',
            states={'invisible': ~Eval('has_coverage_amount')},
            depends=['has_coverage_amount'], sort=False),
        'on_change_with_coverage_amount_selection', 'setter_void')
    person = fields.Function(
        fields.Many2One('party.party', 'Person'),
        'on_change_with_person')
    has_coverage_amount = fields.Function(
        fields.Boolean('Has Coverage Amount'),
        'on_change_with_has_coverage_amount')

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls.__rpc__.update({'get_possible_amounts': RPC(instantiate=0)})

    @classmethod
    def default_coverage_amount(cls):
        return None

    @fields.depends('coverage', 'start_date', 'covered_element', 'currency',
        'appliable_conditions_date')
    def get_possible_amounts(self):
        if not self.covered_element or not self.coverage:
            return [('', '')]
        vals = self.coverage.get_result(
            'allowed_amounts', {
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date,
                })[0]
        if vals:
            res = map(lambda x: (str(x), self.currency.amount_as_string(x)),
                vals)
            return [('', '')] + res
        return [('', '')]

    @fields.depends('coverage_amount_selection', 'coverage')
    def on_change_with_coverage_amount(self, name=None):
        if not self.coverage:
            return None
        if self.coverage_amount_selection:
            return self.currency.get_amount_from_string(
                    self.coverage_amount_selection)
        return None

    @fields.depends('coverage_amount', 'currency', 'coverage')
    def on_change_with_coverage_amount_selection(self, name=None):
        if not self.coverage:
            return ''
        if self.coverage_amount:
            return self.currency.amount_as_string(self.coverage_amount)
        return ''

    @fields.depends('covered_element')
    def on_change_with_person(self, name=None):
        if self.covered_element and self.covered_element.party:
            return self.covered_element.party.id

    @fields.depends('coverage', 'start_date', 'covered_element', 'currency',
        'appliable_conditions_date')
    def on_change_with_has_coverage_amount(self, name=None):
        if not self.coverage:
            return False
        if not len(self.get_possible_amounts()) > 1:
            return False
        if not self.coverage.get_result(
                'dependant_amount_coverage', {
                    'date': self.start_date,
                    'appliable_conditions_date':
                    self.appliable_conditions_date,
                })[0]:
            return True
        return False
