# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = [
    'Contract',
    'ContractOption'
]


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    @classmethod
    def _calculate_methods(cls, product):
        return [('options', 'check_eligibility')] + \
            super(Contract, cls)._calculate_methods(product)

    @classmethod
    def _calculate_methods_after_endorsement(cls):
        return super(Contract, cls)._calculate_methods_after_endorsement() | \
            {'check_eligibility'}

    @classmethod
    def check_eligibility(cls, contracts, caller=None):
        for contract in contracts:
            for option in contract.options:
                option.check_eligibility()
            for covered in contract.covered_elements:
                for option in covered.options:
                    option.check_eligibility()


class ContractOption(metaclass=PoolMeta):
    __name__ = 'contract.option'

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._error_messages.update({
                'option_not_eligible': 'Option %s is not eligible',
                })

    def check_eligibility(self):
        if self.status in ('void', 'declined'):
            return True
        exec_context = {'date': self.start_date}
        self.init_dict_for_rule_engine(exec_context)
        if not self.coverage.check_eligibility(exec_context):
            self.append_functional_error('option_not_eligible',
                (self.coverage.name))
            return False
        if (self.final_end_date and self.initial_start_date
                and self.initial_start_date > self.final_end_date):
            Date = Pool().get('ir.date')
            self.raise_user_warning('bad_dates_%s' %
                ' - '.join([
                        self.rec_name,
                        Date.date_as_string(self.initial_start_date)]),
                'bad_dates', {'option': self.rec_name})
        return True
