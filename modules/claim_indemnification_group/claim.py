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

    def get_possible_products(self, name):
        if not self.beneficiary or self.beneficiary.is_person:
            return super(Indemnification, self).get_possible_products(name)
        return [x.id for x in self.service.benefit.company_products]

    @fields.depends('beneficiary', 'possible_products', 'product')
    def on_change_beneficiary(self):
        self.update_product()
