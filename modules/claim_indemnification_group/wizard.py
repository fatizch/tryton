# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields


__all__ = [
    'IndemnificationDefinition',
    ]


class IndemnificationDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    @fields.depends('beneficiary')
    def on_change_service(self):
        super(IndemnificationDefinition, self).on_change_service()

    @fields.depends('beneficiary', 'possible_products', 'product', 'service')
    def on_change_beneficiary(self):
        self.update_product()

    def get_possible_products(self, name):
        if not self.beneficiary or self.beneficiary.is_person:
            return super(IndemnificationDefinition,
                self).get_possible_products(name)
        if self.service:
            return [x.id for x in self.service.benefit.company_products]
        return []
