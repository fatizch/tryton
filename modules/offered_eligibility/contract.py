from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption'
]


class Contract:
    __name__ = 'contract'

    @classmethod
    def _calculate_methods(cls, product):
        return super(Contract, cls)._calculate_methods(product) + [('options',
                'check_eligibility')]

    @classmethod
    def check_eligibility(cls, contracts, caller=None):
        for contract in contracts:
            for option in contract.options:
                option.check_eligibility()
            for covered in contract.covered_elements:
                for option in covered.options:
                    option.check_eligibility()

    @classmethod
    def _calculate_methods_after_endorsement(cls):
        return super(Contract, cls)._calculate_methods_after_endorsement() | \
            {'check_eligibility'}


class ContractOption:
    __name__ = 'contract.option'

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._error_messages.update({
                'option_not_eligible': 'Option %s is not eligible',
                })

    def check_eligibility(self):
        if self.status == 'void':
            return True
        exec_context = {'date': self.start_date}
        self.init_dict_for_rule_engine(exec_context)
        if not self.coverage.check_eligibility(exec_context):
            self.append_functional_error('option_not_eligible',
                (self.coverage.name))
            return False
        return True
