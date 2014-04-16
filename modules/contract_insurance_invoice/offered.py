from dateutil.rrule import rrule, YEARLY, MONTHLY
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields, model

from .contract import FREQUENCIES

__metaclass__ = PoolMeta

__all__ = [
    'InvoiceFrequency',
    'Product',
    'ProductInvoiceFrequencyRelation',
    'OptionDescription',
    'FeeDesc',
    'TaxDesc',
    ]

MONTHS = [
    ('1', 'January'),
    ('2', 'February'),
    ('3', 'March'),
    ('4', 'April'),
    ('5', 'May'),
    ('6', 'June'),
    ('7', 'July'),
    ('8', 'August'),
    ('9', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
    ]


class InvoiceFrequency(model.CoopSQL, model.CoopView):
    'Invoice Frequency'

    __name__ = 'offered.invoice.frequency'

    frequency = fields.Selection(FREQUENCIES, 'Invoice Frequency',
        required=True)
    sync_day = fields.Selection([(str(x), str(x))
            for x in xrange(1, 29)] + [('', '')], 'Sync Day', states={
            'required': Bool(Eval('sync_month', False))},
        depends=['sync_month'], sort=False)
    sync_month = fields.Selection(MONTHS, 'Sync Month', sort=False)
    products = fields.Many2Many('offered.product-offered.invoice.frequency',
        'invoice_frequency', 'product', 'Products', readonly=True)

    @classmethod
    def default_frequency(cls):
        return 'yearly'

    @classmethod
    def _export_skips(cls):
        result = super(InvoiceFrequency, cls)._export_skips()
        result.add('products')
        return result

    def get_rrule(self, start, until=None):
        if self.frequency in ('monthly', 'quarterly', 'biannual'):
            freq = MONTHLY
            interval = {
                'monthly': 1,
                'quarterly': 3,
                'biannual': 6,
                }.get(self.frequency)
        elif self.frequency == 'yearly':
            freq = YEARLY
            interval = 1
        elif self.frequency == 'once_per_contract':
            return [start, self.end_date + relativedelta(days=+1)], until
        else:
            return [], until
        sync_date = None
        if self.sync_month:
            sync_date = (int(self.sync_day), int(self.sync_month))
        return (rrule(freq, interval=interval, dtstart=start, until=until,
                bymonthday=sync_date), until)


class Product:
    __name__ = 'offered.product'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', required=True, depends=['company'],
        domain=[('kind', '=', 'revenue'), ('company', '=', Eval('company'))],
        ondelete='RESTRICT')
    frequencies = fields.Many2Many('offered.product-offered.invoice.frequency',
        'product', 'invoice_frequency', 'Frequencies')
    default_frequency = fields.Many2One('offered.invoice.frequency',
        'Default Frequency', domain=[('id', 'in', Eval('frequencies'))],
        depends=['frequencies'], ondelete='RESTRICT')

    @fields.depends('frequencies', 'default_frequency')
    def on_change_frequencies(self):
        if not self.frequencies:
            return {'default_frequency': None}
        if (self.default_frequency and
                self.default_frequency in self.frequencies):
            return {}
        return {'default_frequency': self.frequencies[0].id}


class ProductInvoiceFrequencyRelation(model.CoopSQL):
    'Product Invoice Frequency Relation'

    __name__ = 'offered.product-offered.invoice.frequency'

    invoice_frequency = fields.Many2One('offered.invoice.frequency',
        'Invoice Frequency', ondelete='RESTRICT', required=True)
    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True)


class OptionDescription:
    __name__ = 'offered.option.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'], domain=[
            ('kind', '=', 'revenue'), ('company', '=', Eval('company'))],
        states={
            'required': ~Eval('is_package'),
            'invisible': ~~Eval('is_package'),
            }, ondelete='RESTRICT')


class FeeDesc:
    __name__ = 'account.fee.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('context', {}).get('company'))],
        required=True, ondelete='RESTRICT')


class TaxDesc:
    __name__ = 'account.tax.description'

    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT')
