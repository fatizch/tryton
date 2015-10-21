from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract:
    __name__ = 'contract'

    def do_renew(self, new_start_date):
        self.calculate_revaluated_coverage_amount(new_start_date)
        super(Contract, self).do_renew(new_start_date)

    def calculate_revaluated_coverage_amount(self, at_date):
        covered_elements = list(self.covered_elements)
        for covered_element in covered_elements:
            options = list(covered_element.options)
            for option in options:
                option.calculate_revaluated_coverage_amount(at_date)
            covered_element.options = options
        self.covered_elements = covered_elements


class ContractOption:
    __name__ = 'contract.option'

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
