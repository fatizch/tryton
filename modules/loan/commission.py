# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'SimulateCommissionsParameters',
    ]


class SimulateCommissionsParameters(metaclass=PoolMeta):
    __name__ = 'commission.simulate.params'

    def mock_contract(self, product):
        contract = super(SimulateCommissionsParameters, self).mock_contract(
            product)
        contract.is_loan = contract.on_change_with_is_loan()
        contract.used_loans = []
        contract.ordered_loans = []
        return contract

    def mock_option(self, coverage, parent_contract, contract=None,
            covered=None):
        option = super(SimulateCommissionsParameters, self).mock_option(
            coverage, parent_contract, contract, covered)
        option.loan_shares = []
        return option
