# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Company',
    ]


class Company:
    __metaclass__ = PoolMeta
    __name__ = 'company.company'

    fiscal_years = fields.One2Many('account.fiscalyear', 'company',
        'Fiscal Years')

    @classmethod
    def _export_skips(cls):
        return (super(Company, cls)._export_skips() |
            set(['fiscal_years']))
