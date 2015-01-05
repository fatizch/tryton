from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'ContractOption'
]


class ContractOption:
    __name__ = 'contract.option'

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._error_messages.update({
                'option_not_eligible': 'Option %s is not eligible',
                })

    def check_eligibility(self):
        exec_context = {'date': self.start_date}
        self.init_dict_for_rule_engine(exec_context)
        if not self.coverage.check_eligibility(exec_context):
            self.append_functional_error('option_not_eligible',
                (self.coverage.name))
            return False
        return True

    @classmethod
    def _calculate_methods(cls, coverage):
        return super(ContractOption, cls)._calculate_methods(coverage) + \
            ['check_eligibility']
