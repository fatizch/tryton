from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    ]


class Configuration:
    __name__ = 'offered.configuration'

    split_invoices_on_endorsement_dates = fields.Boolean(
        'Split Invoices on Endorsement Dates')
