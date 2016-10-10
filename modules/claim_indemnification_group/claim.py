# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'ClaimService',
    'Indemnification',
    ]


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    def init_from_loss(self, loss, benefit):
        super(ClaimService, self).init_from_loss(loss, benefit)
        if (not self.benefit.is_group or
                self.benefit.benefit_rules[0].force_annuity_frequency):
            return
        option_benefit = self.option.get_version_at_date(
            self.loss.start_date).get_benefit(self.benefit)
        self.annuity_frequency = option_benefit.annuity_frequency


class Indemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    @classmethod
    def __setup__(cls):
        super(Indemnification, cls).__setup__()
        cls._error_messages.update({
                'bad_dates': 'The indemnification period (%(indemn_start)s - '
                "%(indemn_end)s) is not compatible with the contract's end "
                'date (%(contract_end)s).',
                })

    def get_possible_products(self, name):
        if not self.beneficiary or self.beneficiary.is_person:
            return super(Indemnification, self).get_possible_products(name)
        return [x.id for x in self.service.benefit.company_products]

    @fields.depends('beneficiary', 'possible_products', 'product')
    def on_change_beneficiary(self):
        self.update_product()

    @classmethod
    def check_calculable(cls, indemnifications):
        super(Indemnification, cls).check_calculable(indemnifications)
        for indemnification in indemnifications:
            if not indemnification.service:
                continue
            contract = indemnification.service.contract
            if not contract or contract.status != 'terminated':
                continue
            if (contract.post_termination_claim_behaviour !=
                    'stop_indemnisations'):
                continue
            if (contract.end_date > indemnification.start_date or
                    contract.end_date > indemnification.end_date):
                cls.append_functional_error('bad_dates', {
                        'indemn_start': indemnification.start_date,
                        'indemn_end': indemnification.end_date,
                        'contract_end': contract.end_date})
