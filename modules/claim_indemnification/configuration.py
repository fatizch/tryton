# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Bool, Eval
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields

__all__ = [
    'Configuration'
    ]


class Configuration:
    'Claim Configuration'

    __metaclass__ = PoolMeta
    __name__ = 'claim.configuration'

    payment_journal = fields.Many2One('account.payment.journal',
        'Default Payment Journal',
        required=True, ondelete='RESTRICT')
    control_rule = fields.Many2One('claim.indemnification.control.rule',
        'Control Rule', ondelete='RESTRICT')
    show_indemnification_limit = fields.Integer('Show Indemnification Limit')
    sorting_method = fields.Selection(
        [('ASC', 'Ascending'), ('DESC', 'Descending')], 'Sorting Method',
        states={
            'required': Bool(Eval('show_indemnification_limit')),
            'invisible': ~Eval('show_indemnification_limit'),
            },
        help='This value will be used to sort indemnifications by start date')
    claim_default_payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Default Payment Term', required=True,
        ondelete='RESTRICT')
    tax_at_indemnification_date = fields.Boolean('Tax At Indemnification Date',
        help='If true, the tax date for invoices will be the date of the '
        'indemnification. Oherwise, the tax date will be the invoice date')

    @staticmethod
    def default_show_indemnification_limit():
        return 30

    @staticmethod
    def default_sorting_method():
        return 'DESC'

    @classmethod
    def write(cls, *args):
        Pool().get('benefit')._indemnification_tax_date_config_cache.clear()
        super(Configuration, cls).write(*args)
