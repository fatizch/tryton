# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, utils

__all__ = [
    'Contract',
    'ContractOption',
    'ContractOptionVersion',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    @classmethod
    def _pre_renew_methods(cls):
        return super(Contract, cls)._pre_renew_methods() | \
            {'calculate_revaluated_coverage_amount_for_renewal'}

    @classmethod
    def calculate_revaluated_coverage_amount_for_renewal(cls, contracts,
            new_start_date=None, caller=None):
        for contract in contracts:
            contract.calculate_revaluated_coverage_amount(new_start_date or
                contract.activation_history[-1].end_date +
                relativedelta(days=1))

    def calculate_revaluated_coverage_amount(self, at_date):
        covered_elements = list(self.covered_elements)
        for covered_element in covered_elements:
            options = list(covered_element.options)
            for option in options:
                option.calculate_revaluated_coverage_amount(at_date)
            covered_element.options = options
        self.covered_elements = covered_elements


class ContractOption:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    @fields.depends('versions')
    def on_change_with_free_coverage_amount(self, name=None):
        result = super(ContractOption,
            self).on_change_with_free_coverage_amount(name)
        if result or not self.versions:
            return result
        current_version = self.get_version_at_date(utils.today())
        return current_version and current_version.coverage_amount_revaluation

    @fields.depends('versions')
    def on_change_with_current_coverage_amount_selection(self, name=None):
        if not self.versions:
            return None
        current_version = self.get_version_at_date(utils.today())
        if current_version and current_version.coverage_amount_revaluation:
            return None
        return super(ContractOption,
            self).on_change_with_current_coverage_amount_selection(name)

    def calculate_revaluated_coverage_amount(self, at_date):
        if (not self.coverage
                or not self.coverage.has_revaluated_coverage_amount):
            return
        args = {'date': at_date}
        self.init_dict_for_rule_engine(args)
        new_cov_amount = self.coverage.calculate_revaluated_coverage_amount(
            args)
        version = self.new_version_at_date(at_date)
        version.coverage_amount = new_cov_amount
        version.coverage_amount_revaluation = True


class ContractOptionVersion:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option.version'

    coverage_amount_revaluation = fields.Boolean('Coverage Amount Revaluation',
        readonly=True, help='If True, this coverage amount is a revaluation '
        'of the initially selected coverage amount')

    @classmethod
    def __setup__(cls):
        super(ContractOptionVersion, cls).__setup__()
        # Required to make contract.option on_changes ok
        cls.coverage_amount.depends.append('coverage_amount_revaluation')

    @classmethod
    def default_coverage_amount_revaluation(cls):
        return False
