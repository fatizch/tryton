import datetime
from dateutil.rrule import rrule, YEARLY, MONTHLY

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool
from trytond import backend
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, export

from .contract import FREQUENCIES

__metaclass__ = PoolMeta

__all__ = [
    'BillingMode',
    'Product',
    'ProductBillingModeRelation',
    'BillingModePaymentTermRelation',
    'OptionDescription',
    'FeeDesc',
    'TaxDesc',
    'PaymentTerm',
    'PaymentTermLine',
    ]

MONTHS = [
    ('', ''),
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


class BillingMode(model.CoopSQL, model.CoopView):
    'Billing Mode'
    __name__ = 'offered.billing_mode'
    _func_key = 'code'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    frequency = fields.Selection(FREQUENCIES, 'Invoice Frequency',
        required=True, sort=False)
    frequency_string = frequency.translated('frequency')
    direct_debit = fields.Boolean('Direct Debit Payment')
    allowed_direct_debit_days = fields.Char('Allowed Direct Debit Dates',
        states={'invisible': ~Eval('direct_debit')},
        help='Days of the month allowed for direct debit payment separated '
        'by comma.\n\n'
        'An empty list means that all dates are allowed')
    allowed_payment_terms = fields.Many2Many(
        'offered.billing.mode-account.invoice.payment_term', 'billing_mode',
        'payment_term', 'Allowed Payment Terms', required=True,
        states={'invisible': Bool(Eval('change_payment_terms_order'))})
    change_payment_terms_order = fields.Function(
        fields.Boolean('Change Payment Term Order'),
        'get_change_payment_term_order', 'setter_void')
    ordered_payment_terms = fields.One2Many(
        'offered.billing.mode-account.invoice.payment_term',
        'billing_mode', 'Ordered Payment Terms',
        order=[('order', 'ASC')],
        states={'invisible': ~Eval('change_payment_terms_order')})
    sync_day = fields.Selection([('', '')] + [(str(x), str(x))
            for x in xrange(1, 29)], 'Sync Day', states={
            'required': Bool(Eval('sync_month', False))},
        depends=['sync_month', 'frequency'], sort=False,
        translate=False)
    sync_month = fields.Selection(MONTHS, 'Sync Month', sort=False, states={
            'invisible': Eval('frequency') == 'monthly'},
            depends=['frequency'])
    products = fields.Many2Many(
        'offered.product-offered.billing_mode',
        'billing_mode', 'product', 'Products', readonly=True)

    @classmethod
    def __setup__(cls):
        super(BillingMode, cls).__setup__()
        cls._sql_constraints += [
            ('code_unique', 'UNIQUE(code)',
                'The code must be unique'),
            ]

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.1: Billing change
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        need_migrate = False
        if (not TableHandler.table_exist(cursor, 'offered_billing_mode') and
                TableHandler.table_exist(cursor, 'offered_invoice_frequency')):
            need_migrate = True
        super(BillingMode, cls).__register__(module_name)
        if need_migrate:
            cursor.execute('insert into '
                '"offered_billing_mode" '
                '(id, create_uid, create_date, write_uid, write_date,'
                'frequency, sync_day, sync_month, code, name) '
                'select id, create_uid, create_date, write_uid, write_date,'
                'frequency, sync_day, sync_month, frequency, frequency from '
                'offered_invoice_frequency')

    def get_allowed_direct_debit_days(self):
        if not self.direct_debit:
            return [('', '')]
        if not self.allowed_direct_debit_days:
            return [(str(x), str(x)) for x in xrange(1, 28)]
        return [(str(x), str(x)) for x in
            self.allowed_direct_debit_days.split(',')]

    @classmethod
    def default_frequency(cls):
        return 'yearly'

    @staticmethod
    def default_sync_day():
        return ''

    @staticmethod
    def default_sync_month():
        return ''

    @classmethod
    def _export_skips(cls):
        result = super(BillingMode, cls)._export_skips()
        result.add('products')
        return result

    def get_rrule(self, start, until=None):
        bymonthday = int(self.sync_day) if self.sync_day else None
        bymonth = int(self.sync_month) if self.sync_month else None
        if self.frequency in ('yearly', 'quarterly', 'half_yearly'):
            freq = YEARLY
            if self.frequency in ('quarterly', 'half_yearly'):
                interval = {
                    'monthly': 1,
                    'quarterly': 3,
                    'half_yearly': 6,
                    }.get(self.frequency)
                if not bymonth:
                    bymonth = start.month
                bymonth = [((bymonth - 1 + interval * x) % 12) + 1
                    for x in range(0, 12 / interval)]
        elif self.frequency == 'monthly':
            freq = MONTHLY
            bymonth = None
        elif self.frequency == 'once_per_contract':
            return [start, datetime.date.max], until
        else:
            return [], until
        return (rrule(freq, dtstart=start, until=until, bymonthday=bymonthday,
                bymonth=bymonth), until)

    @classmethod
    def _export_keys(cls):
        return set(['code'])

    @fields.depends('frequency')
    def on_change_frequency(self):
        if self.frequency == 'monthly':
            self.sync_month = None

    def get_change_payment_term_order(self, name):
        return False


class PaymentTerm(export.ExportImportMixin):
    __name__ = 'account.invoice.payment_term'

    @classmethod
    def _export_keys(cls):
        return set(['name'])


class PaymentTermLine(export.ExportImportMixin):
    __name__ = 'account.invoice.payment_term.line'


class Product:
    __name__ = 'offered.product'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', required=True, depends=['company'],
        domain=[('kind', '=', 'revenue'), ('company', '=', Eval('company'))],
        ondelete='RESTRICT')
    billing_modes = fields.Many2Many('offered.product-offered.billing_mode',
        'product', 'billing_mode', 'Billing Modes', order=[('order', 'ASC')],
        states={'invisible': Bool(Eval('change_billing_modes_order'))})
    change_billing_modes_order = fields.Function(
        fields.Boolean('Change Order'),
        'get_change_billing_modes_order', 'setter_void')
    ordered_billing_modes = fields.One2Many(
        'offered.product-offered.billing_mode', 'product',
        'Ordered Billing Mode', order=[('order', 'ASC')],
        states={'invisible': ~Eval('change_billing_modes_order')})

    @classmethod
    def _export_light(cls):
        return (super(Product, cls)._export_light()
            | set(['account_for_billing']))

    def get_change_billing_modes_order(self, name):
        return False


class ProductBillingModeRelation(model.CoopSQL, model.CoopView):
    'Product Billing Mode Relation'

    __name__ = 'offered.product-offered.billing_mode'

    billing_mode = fields.Many2One('offered.billing_mode',
        'Billing Mode', ondelete='RESTRICT', required=True)
    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True)
    order = fields.Integer('Order')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.1: Billing change
        migrate = False
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        if (not TableHandler.table_exist(cursor,
                'offered_product-offered_billing_mode') and
                TableHandler.table_exist(cursor,
                    'offered_product-offered_invoice_frequency')):
            migrate = True

        super(ProductBillingModeRelation, cls).__register__(
            module_name)

        # Migration from 1.1: Billing change
        if migrate:
            cursor.execute('insert into '
                '"offered_product-offered_billing_mode" '
                '(id, create_uid, create_date, write_uid, write_date,'
                'product, billing_mode) '
                'select id, create_uid, create_date, write_uid, write_date,'
                'product, invoice_frequency from '
                '"offered_product-offered_invoice_frequency"')


class BillingModePaymentTermRelation(model.CoopSQL, model.CoopView):
    'Billing Mode Payment Term Relation'

    __name__ = 'offered.billing.mode-account.invoice.payment_term'

    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', ondelete='RESTRICT', required=True)
    billing_mode = fields.Many2One('offered.billing_mode', 'Billing Mode',
        ondelete='CASCADE', required=True)
    order = fields.Integer('Order')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.1: Billing change
        migrate = False
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        if (not TableHandler.table_exist(cursor,
                'offered_billing_mode-account_invoice_payment_term') and
                TableHandler.table_exist(cursor,
                    'offered_product-account_invoice_payment_term')):
            migrate = True

        super(BillingModePaymentTermRelation, cls).__register__(module_name)

        # Migration from 1.1: Billing change
        if migrate:
            cursor.execute('insert into '
                '"offered_billing_mode-account_invoice_payment_term" '
                '(payment_term,billing_mode) '
                'select p.payment_term, b.billing_mode from '
                '"offered_product-account_invoice_payment_term" as p,'
                '"offered_product-offered_billing_mode" as b '
                'where p.product=b.product')


class OptionDescription:
    __name__ = 'offered.option.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'], domain=[
            ('kind', '=', 'revenue'), ('company', '=', Eval('company'))],
        states={
            'required': ~Eval('is_package'),
            'invisible': ~~Eval('is_package'),
            }, ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return (super(OptionDescription, cls)._export_light()
            | set(['account_for_billing']))


class FeeDesc:
    __name__ = 'account.fee.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('context', {}).get('company'))],
        required=True, ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return (super(FeeDesc, cls)._export_light()
            | set(['account_for_billing']))


class TaxDesc:
    __name__ = 'account.tax.description'

    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT')
