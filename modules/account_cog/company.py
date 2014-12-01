from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Company',
    ]


class Company:
    __name__ = 'company.company'

    fiscal_years = fields.One2Many('account.fiscalyear', 'company',
        'Fiscal Years')

    @classmethod
    def _export_skips(cls):
        return (super(Company, cls)._export_skips() |
            set(['fiscal_years']))
