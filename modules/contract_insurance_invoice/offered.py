# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from decimal import Decimal, InvalidOperation
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from sql import Literal

from dateutil.rrule import rrule, YEARLY, MONTHLY
from dateutil.relativedelta import relativedelta

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, If
from trytond.transaction import Transaction
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields, model, export, utils, coog_string
from trytond.modules.rule_engine import get_rule_mixin

from .contract import FREQUENCIES


__all__ = [
    'BillingMode',
    'BillingModeFeeRelation',
    'Product',
    'RuleEngine',
    'ProductBillingRule',
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


class BillingMode(model.CodedMixin, model.CoogView):
    'Billing Mode'
    __name__ = 'offered.billing_mode'

    frequency = fields.Selection(FREQUENCIES, 'Invoice Frequency',
        required=True, sort=False)
    frequency_string = frequency.translated('frequency')
    direct_debit = fields.Function(
        fields.Boolean('Direct Debit Payment', depends=['process_method']),
        'getter_direct_debit', 'setter_direct_debit',
        searcher='searcher_direct_debit')
    process_method = fields.Selection(
        'get_process_method',
        'Process Method')
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
            for x in range(1, 29)], 'Sync Day', states={
            'required': Bool(Eval('sync_month', False))},
        depends=['sync_month', 'frequency'], sort=False,
        translate=False)
    sync_month = fields.Selection(MONTHS, 'Sync Month', sort=False, states={
            'invisible': Eval('frequency') == 'monthly'},
            depends=['frequency'])
    sync_month_string = sync_month.translated('sync_month')
    products = fields.Function(
        fields.Many2Many('offered.product', None, None, 'Products'),
        'getter_products', searcher='search_products')
    fees = fields.Many2Many('offered.billing_mode-account.fee', 'billing_mode',
        'fee', 'Fees')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._function_auto_cache_fields.append('direct_debit')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.1: Billing change
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        need_migrate = False
        if (not TableHandler.table_exist('offered_billing_mode') and
                TableHandler.table_exist('offered_invoice_frequency')):
            need_migrate = True
        # Migration from 2.4: Direct debit
        handler = TableHandler(cls, module_name)
        migrate_debit = (handler.column_exist('direct_debit')
            and not handler.column_exist('process_method'))
        sepa_modes_ids = []
        manual_modes_ids = []

        if migrate_debit:
            table = cls.__table__()
            cursor.execute(*table.select(
                    table.id,
                    where=table.direct_debit == Literal(True)))
            sepa_modes_ids = [x for x, in cursor.fetchall()]
            cursor.execute(*table.select(
                    table.id,
                    where=table.direct_debit == Literal(False)))
            manual_modes_ids = [x for x, in cursor.fetchall()]
            handler.drop_column('direct_debit')

        super(BillingMode, cls).__register__(module_name)

        if sepa_modes_ids:
            cursor.execute(*table.update(
                    columns=[table.process_method],
                    values=[Literal('sepa')],
                    where=table.id.in_(sepa_modes_ids)))
        if manual_modes_ids:
            cursor.execute(*table.update(
                    columns=[table.process_method],
                    values=[Literal('manual')],
                    where=table.id.in_(manual_modes_ids)))

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
            'allowed_payment_terms', 'billing_rules'}

    @classmethod
    def _export_light(cls):
        return super(BillingMode, cls)._export_light() | {'fees'}

    def get_allowed_direct_debit_days(self):
        if not self.direct_debit:
            return [('', '')]
        if not self.allowed_direct_debit_days:
            return [(str(x), str(x)) for x in range(1, 28)]
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

    def _custom_rrule(self, start, end):
        # Do not handle the case where the global configuration is to sync all
        # invoices on the 31 / 30 / 29 of january
        assert not self.sync_day and not self.sync_month
        interval = {
            'monthly': 1,
            'quarterly': 3,
            'half_yearly': 6,
            'yearly': 12,
            }.get(self.frequency)
        base_date = start
        # Sync on the contract date / billing_info date
        billing_info = ServerContext().get('cur_billing_information', None)
        if billing_info:
            if billing_info.date:
                base_date = billing_info.date
            else:
                base_date = billing_info.contract.get_field_value_at_date(start)
        return utils.CustomRrule(start, interval, end=end, base_date=base_date)

    def get_rrule(self, start, until=None):
        bymonthday = int(self.sync_day) if self.sync_day else None
        bymonth = int(self.sync_month) if self.sync_month else None
        if (not bymonthday and start.day in (28, 29, 30, 31) or
                bymonthday in (28, 29, 30, 31)) and (
                self.frequency in ('yearly', 'quarterly', 'half_yearly',
                    'monthly')):
            return self._custom_rrule(start, until), until
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
                    for x in range(0, 12 // interval)]
            elif bymonth is None:
                bymonth = start.month
        elif self.frequency == 'monthly':
            freq = MONTHLY
            bymonth = None
        elif self.frequency == 'once_per_contract':
            return [datetime.datetime.combine(start, datetime.time()),
                datetime.datetime.combine(datetime.date.max, datetime.time())
                ], until
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

    def getter_products(self, name):
        return [rule.product.id for rule in self.billing_rules]

    @classmethod
    def search_products(cls, name, domain):
        return [('billing_rules.product',) + tuple(domain[1:])]

    @classmethod
    def getter_direct_debit(cls, billing_modes, name):
        return {b.id: b.process_method == 'sepa' for b in billing_modes}

    @classmethod
    def setter_direct_debit(cls, billing_modes, name, value):
        value_to_write = 'manual'
        if value is True:
            value_to_write = 'sepa'
        cls.write(billing_modes, {'process_method': value_to_write})

    @classmethod
    def searcher_direct_debit(cls, name, clause):
        _, operator, value = clause
        if ((operator == '=' and value is True) or
                (operator == '!=' and value is False)):
            return [('process_method', '=', 'sepa')]
        else:
            return [('process_method', '!=', 'sepa')]

    @classmethod
    def get_process_method(cls):
        Journal = Pool().get('account.payment.journal')
        return list(set(Journal.process_method.selection + [('sepa', 'SEPA')]))


class BillingModeFeeRelation(model.ConfigurationMixin):
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
    __name__ = 'account.invoice.payment_term.line.delta'
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


class RuleEngine(metaclass=PoolMeta):
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.extend([('billing_mode', 'Billing Mode'), ])


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    billing_rules = fields.One2Many('offered.product.billing_rule', 'product',
        'Billing Rules', delete_missing=True, size=1,
        help='Define which billing mode are available'
        ' during contract subscription')
    days_offset_for_subscription_payments = fields.Integer(
        'Days Offset For Subscription Payments')
    taxes_included_in_premium = fields.Boolean('Taxes Included',
        help='Taxes Included In Premium. Requires tax rounding to be set to'
        '"line"', domain=[If(Eval('tax_rounding', '') == 'document', [
                    ('taxes_included_in_premium', '=', False)], [])],
        states={'readonly': Eval('tax_rounding') == 'document'},
        depends=['tax_rounding'])
    tax_rounding = fields.Function(
        fields.Char('Tax_Rounding'),
        'get_tax_rounding')
    billing_behavior = fields.Function(
        fields.Selection('get_allowed_billing_behavior', 'Billing Behavior'),
        'on_change_with_billing_behavior',
        searcher='search_billing_behavior')

    @classmethod
    def __register__(cls, module_name):
        super(Product, cls).__register__(module_name)
        # Migration from 1.3: Drop account_for_billing column
        TableHandler = backend.get('TableHandler')
        product = TableHandler(cls)
        if product.column_exist('account_for_billing'):
            product.drop_column('account_for_billing')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.coverages.domain.extend([('taxes_included_in_premium', '=',
            Eval('taxes_included_in_premium'))])
        cls.coverages.depends.extend(['taxes_included_in_premium'])
        cls._function_auto_cache_fields.append('billing_behavior')

    @classmethod
    def default_billing_rules(cls):
        return [{}]

    @classmethod
    def default_tax_rounding(cls):
        return Pool().get('account.configuration')(1).tax_rounding

    @fields.depends('coverages')
    def on_change_taxes_included_in_premium(self):
        self.coverages = []

    @fields.depends('billing_rules')
    def get_allowed_billing_behavior(self):
        if not self.billing_rules:
            return [('', '')]
        return self.billing_rules[0].BILLING_BEHAVIOR

    @classmethod
    def get_tax_rounding(cls, products, name):
        method = cls.default_tax_rounding()
        return {x.id: method for x in products}

    def get_non_periodic_payment_date(self, contract):
        offset = self.days_offset_for_subscription_payments
        return utils.today() + relativedelta(days=offset or 0)

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['parameters'].extend([
                coog_string.doc_for_field(self,
                    'days_offset_for_subscription_payments'),
                coog_string.doc_for_field(self, 'taxes_included_in_premium'),
                ])
        doc['rules'].append(coog_string.doc_for_rules(self, 'billing_rules'))
        return doc

    def get_default_billing_mode(self):
        if not self.billing_rules:
            return None
        if not self.billing_rules[0].billing_modes:
            return None
        return self.billing_rules[0].billing_modes[0]

    @fields.depends('billing_rules')
    def on_change_with_billing_behavior(self, name=None):
        if self.billing_rules:
            return self.billing_rules[0].billing_behavior

    @classmethod
    def search_billing_behavior(cls, name, domain):
        return [('billing_rules.billing_behavior',) + tuple(domain[1:])]


class ProductBillingRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.ConfigurationMixin, model.CoogView):
    'ProductBilling Rule'

    __name__ = 'offered.product.billing_rule'
    _func_key = 'func_key'

    BILLING_BEHAVIOR = [
        ('next_period', 'Invoice until requested period'),
        ('whole_term', 'Invoice whole term'),
    ]

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        required=True, select=True)
    billing_modes = fields.Many2Many('offered.product-offered.billing_mode',
        'billing_rule', 'billing_mode', 'Billing Modes',
        order=[('order', 'ASC')],
        states={'invisible': Bool(Eval('change_billing_modes_order'))},
        help="Billing mode available to invoice the contract")
    change_billing_modes_order = fields.Function(
        fields.Boolean('Change Order'),
        'get_change_billing_modes_order', 'setter_void')
    ordered_billing_modes = fields.One2Many(
        'offered.product-offered.billing_mode', 'billing_rule',
        'Ordered Billing Mode', order=[('order', 'ASC')],
        states={'invisible': ~Eval('change_billing_modes_order')},
        delete_missing=True)
    billing_behavior = fields.Selection(BILLING_BEHAVIOR, 'Billing Behavior',
        help="Defines invoicing strategy for this product")
    func_key = fields.Function(
        fields.Char('Funtional Key'),
        'getter_func_key', searcher='searcher_func_key')

    @classmethod
    def __setup__(cls):
        super(ProductBillingRule, cls).__setup__()
        cls.rule.domain = [('type_', '=', 'billing_mode')]
        cls.rule.help = ('The rule must return a list with billing mode codes.')
        cls.rule.string = 'Billing Rule'

    @classmethod
    def __register__(cls, module):
        cursor = Transaction().connection.cursor()
        TableHandler = backend.get('TableHandler')
        Product = Pool().get('offered.product')
        BillingRule_table = cls.__table__()
        Product_table = Product.__table__()
        to_migrate = not TableHandler.table_exist(cls._table)
        super(ProductBillingRule, cls).__register__(module)

        if to_migrate:
            cursor.execute(*BillingRule_table.insert(
                columns=[BillingRule_table.product],
                values=Product_table.select(Product_table.id)
            ))

    @classmethod
    def _export_light(cls):
        return super()._export_light() | {'ordered_billing_modes'}

    @classmethod
    def _export_skips(cls):
        return super()._export_skips() | {'billing_modes'}

    def getter_func_key(self, name):
        return self.product.code

    @classmethod
    def searcher_func_key(cls, name, clause):
        return [('product.code',) + tuple(clause[1:])]

    def format_as_rule_result(self):
        return [x for x in self.billing_modes]

    @classmethod
    def default_billing_behavior(cls):
        return 'next_period'

    def calculate_available_billing_modes(self, args):
        if not self.rule:
            return self.format_as_rule_result()
        result = self.calculate_rule(args, crash_on_missing_arguments=False)
        if type(result) not in (list, type(None)):
            raise ValidationError(gettext(
                    'contract_insurance_invoice.msg_wrong_rule_format'))
        if result:
            return [x for x in self.billing_modes if x.code in result]
        else:
            return self.billing_modes

    def get_change_billing_modes_order(self, name):
        return False

    def get_rule_documentation_structure(self):
        res = [coog_string.doc_for_field(self, 'billing_behavior')]
        res = [coog_string.doc_for_field(self, 'billing_modes')]
        if self.rule:
            res.append(self.get_rule_rule_engine_documentation_structure())
        return res


class ProductBillingModeRelation(model.ConfigurationMixin, model.CoogView):
    'Product Billing Mode Relation'

    __name__ = 'offered.product-offered.billing_mode'

    billing_rule = fields.Many2One('offered.product.billing_rule', 'Rule',
        ondelete='CASCADE', required=True, select=True)
    billing_mode = fields.Many2One('offered.billing_mode',
        'Billing Mode', ondelete='RESTRICT', required=True, select=True)
    order = fields.Integer('Order')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        BillingRule = Pool().get('offered.product.billing_rule')
        Relation_table = cls.__table__()
        BillingRule_table = BillingRule.__table__()
        product_billing = TableHandler(cls, module_name)
        cursor = Transaction().connection.cursor()
        super(ProductBillingModeRelation, cls).__register__(
            module_name)
        if product_billing.column_exist('product'):
            cursor.execute(*Relation_table.update(
                columns=[Relation_table.billing_rule],
                values=[BillingRule_table.id],
                from_=[BillingRule_table],
                where=Relation_table.product == BillingRule_table.product
            ))
            product_billing.drop_column('product')


class BillingModePaymentTermRelation(model.ConfigurationMixin, model.CoogView):
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
        cursor = Transaction().connection.cursor()
        if (not TableHandler.table_exist(
                'offered_billing_mode-account_invoice_payment_term') and
                TableHandler.table_exist(
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


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', help='Account used to credit premium amount',
        depends=['company'], states={'required': True},
        domain=[
            ['OR',
                [('type.revenue', '=', True)],
                [('type.other', '=', True)]
            ],
            ('company', '=', Eval('company')),
            ],
        ondelete='RESTRICT')
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

    @classmethod
    def default_tax_rounding(cls):
        return Pool().get('account.configuration')(1).tax_rounding

    def get_tax_rounding(self, name):
        return self.default_tax_rounding()

    def get_account_for_billing(self, line):
        return self.account_for_billing

    def get_documentation_structure_for_premium_rule(self):
        doc = super(OptionDescription, self).\
            get_documentation_structure_for_premium_rule()
        doc['attributes'].extend([
            coog_string.doc_for_field(self, 'account_for_billing'),
            coog_string.doc_for_field(self, 'taxes_included_in_premium')
            ])
        return doc


class OptionDescriptionPremiumRule(metaclass=PoolMeta):
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
        new_frequency = contract._billing_information_at_date(
            date).billing_mode.frequency
        for line in lines:
            factor = self.convert_premium_frequency(line.frequency,
                new_frequency)
            if factor is None:
                continue
            line.frequency = new_frequency
            try:
                line.amount = Decimal.quantize(line.amount / factor,
                    line.amount)
            except InvalidOperation:
                line.amount = line.amount / factor
