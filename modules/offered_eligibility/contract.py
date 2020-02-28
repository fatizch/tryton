# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError, UserWarning

from trytond.modules.coog_core import fields

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

    @classmethod
    def decline_non_eligible_options(cls, contracts):
        pool = Pool()
        Option = pool.get('contract.option')
        to_decline = []
        for contract in contracts:
            for option in contract.options + \
                    contract.covered_element_options:
                try:
                    option.check_eligibility()
                except UserError as e:
                    to_decline.append([option, e.message])
        Option.auto_decline(to_decline)


class ContractOption(metaclass=PoolMeta):
    __name__ = 'contract.option'

    eligibility_message = fields.Char('Eligibility Message', readonly=True,
        help="Explanations on the eligibilty status of the option")

    def check_eligibility(self):
        if self.status in ('void', 'declined'):
            return True
        exec_context = {'date': self.start_date}
        self.init_dict_for_rule_engine(exec_context)
        if not self.coverage.check_eligibility(exec_context):
            self.append_functional_error(
                ValidationError(gettext(
                        'offered_eligibility.msg_option_not_eligible',
                        coverage=self.coverage.name)))
            return False
        if (self.final_end_date and self.initial_start_date
                and self.initial_start_date > self.final_end_date):
            pool = Pool()
            Date = pool.get('ir.date')
            Warning = pool.get('res.user.warning')
            key = 'bad_dates_%s' % ' - '.join([
                    self.rec_name,
                    Date.date_as_string(self.initial_start_date)])
            if Warning.check(key):
                raise UserWarning(key, gettext('contract.msg_bad_dates',
                    option=self.rec_name))
        return True
