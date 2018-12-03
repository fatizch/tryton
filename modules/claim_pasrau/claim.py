# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.server_context import ServerContext

from trytond.modules.coog_core import utils

__all__ = [
    'Indemnification',
    ]


class Indemnification(metaclass=PoolMeta):
    __name__ = 'claim.indemnification'

    def get_amount(self, name):
        pasrau_dict = {}
        pasrau_dict['party'] = self.beneficiary
        pasrau_dict['period_start'] = self.start_date
        pasrau_dict['period_end'] = self.end_date
        pasrau_dict['income'] = sum([d.amount for d in self.details])
        pasrau_dict['invoice_date'] = utils.today()
        with ServerContext().set_context(pasrau_data=pasrau_dict):
            return super(Indemnification, self).get_amount(name)

    def _get_taxes(self):
        pasrau_dict = {}
        pasrau_dict['party'] = self.beneficiary
        pasrau_dict['period_start'] = self.start_date
        pasrau_dict['period_end'] = self.end_date
        pasrau_dict['income'] = sum([d.amount for d in self.details])
        pasrau_dict['invoice_date'] = utils.today()
        with ServerContext().set_context(pasrau_data=pasrau_dict):
            return super(Indemnification, self)._get_taxes()
