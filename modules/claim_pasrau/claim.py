# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.server_context import ServerContext

__all__ = [
    'Indemnification',
    ]


class Indemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    def get_amount(self, name):
        pasrau_dict = {}
        pasrau_dict['party'] = self.beneficiary
        pasrau_dict['period_start'] = self.start_date
        pasrau_dict['period_end'] = self.end_date
        pasrau_dict['income'] = self.total_amount
        with ServerContext().set_context(pasrau_data=pasrau_dict):
            return super(Indemnification, self).get_amount(name)

    def _get_taxes(self):
        pasrau_dict = {}
        pasrau_dict['party'] = self.beneficiary
        pasrau_dict['period_start'] = self.start_date
        pasrau_dict['period_end'] = self.end_date
        pasrau_dict['income'] = self.amount
        with ServerContext().set_context(pasrau_data=pasrau_dict):
            return super(Indemnification, self)._get_taxes()
