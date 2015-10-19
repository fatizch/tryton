from decimal import Decimal
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool
from trytond.rpc import RPC

from trytond.modules.cog_utils import fields, utils, model
from trytond.modules.currency_cog import ModelCurrency

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'CoveredElement',
    'ContractOption',
    'ContractOptionVersion',
    ]


class Contract:
    __name__ = 'contract'

    def check_coverage_amount(self):
        for covered_element in self.covered_elements:
            covered_element.check_coverage_amount()


class CoveredElement:
    __name__ = 'contract.covered_element'

    def check_coverage_amount(self):
        for option in self.options:
            option.check_coverage_amount()


class ContractOption:
    __name__ = 'contract.option'

    current_coverage_amount = fields.Function(
        fields.Numeric('Coverage Amount',
            states={
                'invisible': ~Eval('has_coverage_amount') | ~(
                    Eval('free_coverage_amount')),
                'required': (Eval('contract_status') == 'active') & Bool(
                    Eval('has_coverage_amount')),
                'readonly': Eval('contract_status') == 'active',
            },
            depends=['has_coverage_amount', 'free_coverage_amount',
                'contract_status']),
        'get_current_version', setter='setter_void')
    current_coverage_amount_selection = fields.Function(
        fields.Selection('get_possible_amounts', 'Coverage Amount',
            states={
                'invisible': ~Eval('has_coverage_amount') | Bool(
                    Eval('free_coverage_amount')),
                'required': ((Eval('contract_status') == 'active') &
                    Bool(Eval('has_coverage_amount')) & ~(
                    Eval('free_coverage_amount'))),
                'readonly': Eval('contract_status') == 'active',
                },
            depends=['free_coverage_amount', 'contract_status',
                'has_coverage_amount'],
            sort=False),
        'on_change_with_coverage_amount_selection', 'setter_void')
    has_coverage_amount = fields.Function(
        fields.Boolean('Has Coverage Amount'),
        'on_change_with_has_coverage_amount')
    free_coverage_amount = fields.Function(
        fields.Boolean('Free Coverage Amount'),
        'on_change_with_free_coverage_amount')

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls.__rpc__.update({'get_possible_amounts': RPC(instantiate=0)})
        cls._error_messages.update({
                'invalid_coverage_amount': 'Coverage amount '
                '"%(coverage_amount)s" is invalid for coverage "%(coverage)s"'
                })

    @classmethod
    def get_field_map(cls):
        field_map = super(ContractOption, cls).get_field_map()
        field_map.update({'coverage_amount': 'current_coverage_amount'})
        return field_map

    @fields.depends('parent_contract', 'coverage', 'start_date',
        'covered_element', 'currency', 'appliable_conditions_date',
        'has_coverage_amount', 'free_coverage_amount')
    def get_possible_amounts(self):
        if self.has_coverage_amount and not self.free_coverage_amount:
            vals = self.get_coverage_amount_rule_result(utils.today())
            if vals:
                return [('', '')] + map(
                    lambda x: (str(x), self.currency.amount_as_string(x)),
                    vals
                    )
        return [('', '')]

    def get_coverage_amount_rule_result(self, at_date):
        if not self.has_coverage_amount:
            return None
        context = {'date': at_date}
        self.init_dict_for_rule_engine(context)
        return self.coverage.get_coverage_amount_rule_result(context)

    def check_coverage_amount(self):
        if not self.has_coverage_amount:
            return
        for version in self.versions:
            rule_result = self.get_coverage_amount_rule_result(
                version.start_date)
            if (self.free_coverage_amount
                    and not rule_result or not self.free_coverage_amount
                    and version.coverage_amount not in rule_result):
                self.raise_user_error('invalid_coverage_amount', {
                        'coverage': self.coverage.rec_name,
                        'coverage_amount': self.current_coverage_amount,
                        })

    @fields.depends('current_coverage_amount', 'versions')
    def on_change_current_coverage_amount(self):
        current_version = self.get_version_at_date(self.start_date)
        if not current_version:
            return
        current_version.coverage_amount = self.current_coverage_amount
        self.versions = list(self.versions)

    @fields.depends('current_coverage_amount_selection', 'versions')
    def on_change_current_coverage_amount_selection(self):
        self.current_coverage_amount = (
            Decimal(self.current_coverage_amount_selection)
            if self.current_coverage_amount_selection else None)
        self.on_change_current_coverage_amount()

    @fields.depends('coverage_amount', 'coverage', 'free_coverage_amount')
    def on_change_with_coverage_amount_selection(self, name=None):
        return (str(self.current_coverage_amount)
            if self.current_coverage_amount and not self.free_coverage_amount
            else '')

    @fields.depends('coverage')
    def on_change_with_has_coverage_amount(self, name=None):
        return (bool(self.coverage.coverage_amount_rules)
            if self.coverage else False)

    @fields.depends('coverage')
    def on_change_with_free_coverage_amount(self, name=None):
        if not self.coverage or not self.coverage.coverage_amount_rules:
            return False
        return self.coverage.coverage_amount_rules[0].free_input


class ContractOptionVersion(model.CoopSQL, model.CoopView, ModelCurrency):
    __name__ = 'contract.option.version'

    coverage_amount = fields.Numeric('Coverage Amount',
        states={
            'invisible': ~Eval('_parent_option', {}).get(
                'has_coverage_amount', False)
            },
        depends=['option'])

    def get_currency(self):
        return self.option.currency
