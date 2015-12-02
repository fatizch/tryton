import datetime
from decimal import Decimal
from dateutil.rrule import rrule, YEARLY, MONTHLY
from dateutil.relativedelta import relativedelta

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, export, utils

from .contract import FREQUENCIES

__metaclass__ = PoolMeta

__all__ = [
    'BillingMode',
    'BillingModeFeeRelation',
    'Product',
    'ProductBillingModeRelation',
    'BillingModePaymentTermRelation',
    'OptionDescription',
    'OptionDescriptionPremiumRule',
    'PaymentTerm',
    'PaymentTermLine',
    'PaymentTermLineRelativeDelta',
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
CONVERSION_TABLE = {
    'yearly': Decimal(12),
    'yearly_360': Decimal(12),
    'yearly_365': Decimal(12),
    'half_yearly': Decimal(6),
    'quarterly': Decimal(3),
    'monthly': Decimal(1),
    }


class BillingMode(model.CoopSQL, model.CoopView):
    'Billing Mode'
    __name__ = 'offered.billing_mode'
    _func_key = 'code'

    name = fields.Char('Name', required=True, translate=True)
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
        order=[('order', 'ASC')], delete_missing=True,
        states={'invisible': ~Eval('change_payment_terms_order')})
    sync_day = fields.Selection([('', '')] + [(str(x), str(x))
            for x in xrange(1, 29)], 'Sync Day', states={
            'required': Bool(Eval('sync_month', False))},
        depends=['sync_month', 'frequency'], sort=False,
        translate=False)
    sync_month = fields.Selection(MONTHS, 'Sync Month', sort=False, states={
            'invisible': Eval('frequency') == 'monthly'},
            depends=['frequency'])
    sync_month_string = sync_month.translated('sync_month')
    products = fields.Many2Many(
        'offered.product-offered.billing_mode',
        'billing_mode', 'product', 'Products', readonly=True)
    fees = fields.Many2Many('offered.billing_mode-account.fee', 'billing_mode',
        'fee', 'Fees')

    @classmethod
    def __setup__(cls):
        super(BillingMode, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
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

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_skips(cls):
        return super(BillingMode, cls)._export_skips() | {'products',
            'allowed_payment_terms'}

    @classmethod
    def _export_light(cls):
        return super(BillingMode, cls)._export_light() | {'fees'}

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

    @fields.depends('frequency')
    def on_change_frequency(self):
        if self.frequency == 'monthly':
            self.sync_month = None

    def get_change_payment_term_order(self, name):
        return False


class BillingModeFeeRelation(model.CoopSQL):
    'Billing Mode Fee Relation'

    __name__ = 'offered.billing_mode-account.fee'

    billing_mode = fields.Many2One('offered.billing_mode', 'Billing Mode',
        ondelete='CASCADE', select=True, required=True)
    fee = fields.Many2One('account.fee', 'Fee', ondelete='RESTRICT',
        select=True, required=True)


class PaymentTerm(export.ExportImportMixin):
    __name__ = 'account.invoice.payment_term'
    _func_key = 'name'


class PaymentTermLine(export.ExportImportMixin):
    __name__ = 'account.invoice.payment_term.line'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    def get_func_key(self, name):
        return '|'.join((self.payment.name, str(self.sequence)))

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        operands = clause[2].split('|')
        if len(operands) == 2:
            payment_name, sequence = operands
            res = []
            if payment_name != 'None':
                res.append(('payment.name', clause[1], payment_name))
            if sequence != 'None':
                res.append(('sequence', clause[1], sequence))
            return res
        else:
            return [('id', '=', None)]


class PaymentTermLineRelativeDelta(export.ExportImportMixin):
    __name__ = 'account.invoice.payment_term.line.relativedelta'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    def get_func_key(self, name):
        return '|'.join((self.line.payment.name, str(self.line.sequence),
                str(self.sequence)))

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        operands = clause[3].split('|')
        if len(operands) == 3:
            line_payment_name, line_sequence, sequence = operands
            res = []
            res.append(('line.payment.name', clause[1], line_payment_name))
            res.append(('line.sequence', clause[1], line_sequence))
            res.append(('sequence', clause[1], sequence))
            return res
        else:
            return [('id', '=', None)]


class Product:
    __name__ = 'offered.product'

    billing_modes = fields.Many2Many('offered.product-offered.billing_mode',
        'product', 'billing_mode', 'Billing Modes', order=[('order', 'ASC')],
        states={'invisible': Bool(Eval('change_billing_modes_order'))})
    change_billing_modes_order = fields.Function(
        fields.Boolean('Change Order'),
        'get_change_billing_modes_order', 'setter_void')
    ordered_billing_modes = fields.One2Many(
        'offered.product-offered.billing_mode', 'product',
        'Ordered Billing Mode', order=[('order', 'ASC')],
        states={'invisible': ~Eval('change_billing_modes_order')},
        delete_missing=True)
    days_offset_for_subscription_payments = fields.Integer(
        'Days Offset For Subscription Payments')
    taxes_included_in_premium = fields.Boolean('Taxes Included',
        help='Taxes Included In Premium',
        states={'invisible': Eval('tax_rounding') == 'document'},
        depends=['tax_rounding'])
    tax_rounding = fields.Function(
        fields.Char('Tax_Rounding'),
        'get_tax_rounding')

    @classmethod
    def __register__(cls, module_name):
        super(Product, cls).__register__(module_name)
        # Migration from 1.3: Drop account_for_billing column
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        product = TableHandler(cursor, cls)
        if product.column_exist('account_for_billing'):
            product.drop_column('account_for_billing')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.coverages.domain.extend([('taxes_included_in_premium', '=',
            Eval('taxes_included_in_premium'))])
        cls.coverages.depends.extend(['taxes_included_in_premium'])

    def get_tax_rounding(self, name):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        return config.tax_rounding

    def get_change_billing_modes_order(self, name):
        return False

    def get_non_periodic_payment_date(self, contract):
        offset = self.days_offset_for_subscription_payments
        return utils.today() + relativedelta(days=offset or 0)


class ProductBillingModeRelation(model.CoopSQL, model.CoopView):
    'Product Billing Mode Relation'

    __name__ = 'offered.product-offered.billing_mode'

    billing_mode = fields.Many2One('offered.billing_mode',
        'Billing Mode', ondelete='RESTRICT', required=True, select=True)
    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)
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
        'Payment Term', ondelete='RESTRICT', required=True, select=True)
    billing_mode = fields.Many2One('offered.billing_mode', 'Billing Mode',
        ondelete='CASCADE', required=True, select=True)
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

    @classmethod
    def _export_light(cls):
        return super(BillingModePaymentTermRelation, cls)._export_light() | {
            'payment_term'}


class OptionDescription:
    __name__ = 'offered.option.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'],
        domain=[['OR', [('kind', '=', 'revenue')], [('kind', '=', 'other')]],
            ('company', '=', Eval('company'))],
        required=True, ondelete='RESTRICT')
    taxes_included_in_premium = fields.Boolean('Taxes Included',
        help='Taxes Included In Premium',
        states={'invisible': Eval('tax_rounding') == 'document'},
        depends=['tax_rounding'])
    tax_rounding = fields.Function(
        fields.Char('Tax_Rounding'),
        'get_tax_rounding')

    @classmethod
    def _export_light(cls):
        return (super(OptionDescription, cls)._export_light() |
            set(['account_for_billing']))

    def get_account_for_billing(self, line):
        return self.account_for_billing

    def get_tax_rounding(self, name):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        return config.tax_rounding


class OptionDescriptionPremiumRule:
    __name__ = 'offered.option.description.premium_rule'

    match_contract_frequency = fields.Boolean('Match Contract Frequency',
        help='Should the premium be stored at the contract\'s frequency ?')

    @classmethod
    def get_premium_result_class(cls):
        Parent = super(OptionDescriptionPremiumRule,
            cls).get_premium_result_class()

        class Child(Parent):
            def __init__(self, amount, data_dict):
                super(Child, self).__init__(amount, data_dict)
                self.account = self.rated_entity.get_account_for_billing(self)

        return Child

    @classmethod
    def convert_premium_frequency(cls, src_frequency, dest_frequency):
        if src_frequency in ('once_per_invoice', 'once_per_contract',
                'once_per_year'):
            return
        if dest_frequency in ('once_per_invoice', 'once_per_contract',
                'once_per_year'):
            return
        return CONVERSION_TABLE[src_frequency] / CONVERSION_TABLE[
            dest_frequency]

    def set_line_frequencies(self, lines, rated_instance, date):
        super(OptionDescriptionPremiumRule, self).set_line_frequencies(lines,
            rated_instance, date)
        if not self.match_contract_frequency:
            return
        contract = lines[0].contract if lines else None
        if not contract:
            return lines
        pool = Pool()
        ContractBillingInformation = pool.get('contract.billing_information')
        ContractBillingMode = pool.get('offered.billing_mode')
        contract_billing_mode = ContractBillingInformation.get_values(
            [contract], date=date,)['billing_mode'][contract.id]
        new_frequency = ContractBillingMode(contract_billing_mode).frequency
        for line in lines:
            factor = self.convert_premium_frequency(line.frequency,
                new_frequency)
            if factor is None:
                continue
            line.frequency = new_frequency
            line.amount = line.amount / factor
