# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'Package',
    ]


class Package(metaclass=PoolMeta):
    __name__ = 'offered.package'

    @classmethod
    def __setup__(cls):
        super(Package, cls).__setup__()
        cls.extra_data.domain = ['OR', cls.extra_data.domain,
            [('kind', '=', 'covered_element')]]

    def update_covered_options(self, covered):
        covered.options = self.clean_and_add_options(
            covered.contract, covered.options, False)
        return covered

    def update_contract_options(self, contract):
        contract = super(Package, self).update_contract_options(contract)
        new_covered = []
        for covered in contract.covered_elements:
            self.update_covered_options(covered)
            new_covered.append(covered)
        contract.covered_elements = new_covered
        return contract

    def update_covered_extra_datas(self, covered):
        for key, value in self.extra_data.items():
            covered.set_extra_data_value(key, value)
        return covered

    def update_covered_options_extra_datas(self, covered):
        options = []
        for option in covered.options:
            options.append(self.update_option_extra_data(option))
        covered.options = options
        return covered

    def update_options_extra_datas(self, contract):
        contract = super(Package, self).update_options_extra_datas(contract)
        new_covered = []
        for covered in contract.covered_elements:
            covered = self.update_covered_options_extra_datas(covered)
            new_covered.append(covered)
        contract.covered_elements = new_covered
        return contract

    def apply_package_on_covered(self, covered):
        if covered.contract.status != 'quote':
            self.raise_user_error('package_only_on_subscription')
        covered = self.update_covered_options(covered)
        covered = self.update_covered_extra_datas(covered)
        covered = self.update_covered_options_extra_datas(covered)
        return covered
