import datetime
from collections import defaultdict
from decimal import Decimal

from dateutil.rrule import rrule, YEARLY, MONTHLY, DAILY
from dateutil.relativedelta import relativedelta
from sql import Column
from sql.aggregate import Max
from sql.conditionals import Coalesce

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, And, Len
from trytond import backend
from trytond.transaction import Transaction
from trytond.tools import reduce_ids
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.rpc import RPC

from trytond.modules.cog_utils import coop_date, utils, batchs, model

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractBillingInformation',
    'ContractInvoice',
    'CoveredElement',
    'ContractOption',
    'ExtraPremium',
    'Premium',
    'PremiumTax',
    'InvoiceContract',
    'InvoiceContractStart',
    'DisplayContractPremium',
    'DisplayContractPremiumDisplayer',
    'DisplayContractPremiumDisplayerPremiumLine',
    'CreateInvoiceContractBatch',
    'PostInvoiceContractBatch',
    ]

FREQUENCIES = [
    ('once_per_contract', 'Once Per Contract'),
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly'),
    ('half_yearly', 'Half-yearly'),
    ('yearly', 'Yearly'),
    ]

PREMIUM_FREQUENCIES = FREQUENCIES + [
    ('yearly_360', 'Yearly (360 days)'),
    ('yearly_365', 'Yearly (365 days)'),
    ('once_per_invoice', 'Once per Invoice'),
    ]


class Contract:
    __name__ = 'contract'
    invoices = fields.One2Many('contract.invoice', 'contract', 'Invoices')
    premiums = fields.One2Many('contract.premium', 'contract', 'Premiums')
    payment_term = fields.Function(fields.Many2One(
        'account.invoice.payment_term', 'Payment Term'),
        'get_billing_information')
    billing_mode = fields.Function(
        fields.Many2One('offered.billing_mode', 'Billing Mode'),
        'get_billing_information')
    billing_informations = fields.One2Many('contract.billing_information',
        'contract', 'Billing Information')
    last_invoice_start = fields.Function(
        fields.Date('Last Invoice Start Date'), 'get_last_invoice',
        searcher='search_last_invoice')
    last_invoice_end = fields.Function(
        fields.Date('Last Invoice End Date'), 'get_last_invoice',
        searcher='search_last_invoice')
    account_invoices = fields.Many2Many('contract.invoice', 'contract',
        'invoice', 'Invoices', order=[('start', 'ASC')], readonly=True)
    total_invoice_amount = fields.Function(
        fields.Numeric('Total Invoice Amount', digits=(16,
                Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_total_invoice_amount')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_calculate_prices': {},
                })

    @classmethod
    def get_billing_information(cls, contracts, names):
        pool = Pool()
        ContractBillingInformation = pool.get('contract.billing_information')
        return cls.get_revision_value(contracts,
            ContractBillingInformation)

    @classmethod
    def get_revision_value(cls, contracts, ContractRevision):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Transaction().context.get('contract_revision_date',
            Date.today())
        return ContractRevision.get_values(contracts, date=date)

    def get_total_invoice_amount(self, name):
        return sum([x.invoice.total_amount
                for x in self.invoices
                if x.invoice.state in ('paid', 'validated', 'posted')])

    @classmethod
    def get_last_invoice(cls, contracts, name):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Invoice = pool.get('account.invoice')
        cursor = Transaction().cursor
        table = cls.__table__()
        contract_invoice = ContractInvoice.__table__()
        invoice = Invoice.__table__()
        values = dict.fromkeys((c.id for c in contracts))
        column = name[len('last_invoice_'):]
        in_max = cursor.IN_MAX
        for i in range(0, len(contracts), in_max):
            sub_ids = [c.id for c in contracts[i:i + in_max]]
            where_id = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(contract_invoice, 'LEFT',
                    table.id == contract_invoice.contract
                    ).join(invoice, 'LEFT',
                    invoice.id == contract_invoice.invoice
                    ).select(table.id, Max(getattr(contract_invoice, column)),
                    where=where_id & (invoice.state != 'cancel'),
                    group_by=table.id))
            values.update(dict(cursor.fetchall()))
        return values

    @classmethod
    def search_last_invoice(cls, name, domain):
        pool = Pool()
        ContractInvoice = pool.get('contract.invoice')
        Invoice = pool.get('account.invoice')
        table = cls.__table__()
        contract_invoice = ContractInvoice.__table__()
        invoice = Invoice.__table__()

        column = name[len('last_invoice_'):]
        _, operator, value = domain
        Operator = fields.SQL_OPERATORS[operator]
        query = table.join(contract_invoice, 'LEFT',
            table.id == contract_invoice.contract
            ).join(invoice, 'LEFT',
                invoice.id == contract_invoice.contract
                ).select(table.id,
                    where=invoice.state != 'cancel',
                    group_by=table.id,
                    having=Operator(Max(getattr(contract_invoice, column)),
                        value))
        return [('id', 'in', query)]

    def _get_invoice_rrule(self, start):
        billing_informations = iter(self.billing_informations)
        billing_information = billing_informations.next()
        for next_billing_information in billing_informations:
            if next_billing_information.date > start:
                break
            billing_information = next_billing_information
        else:
            next_billing_information = None
        until = None
        if next_billing_information:
            until = next_billing_information.date
        res = billing_information.billing_mode.get_rrule(start, until)
        return (res[0], res[1], billing_information)

    def get_invoice_periods(self, up_to_date):
        if self.last_invoice_end:
            start = self.last_invoice_end + relativedelta(days=+1)
        else:
            start = self.start_date
        if up_to_date and start > up_to_date:
            return []
        periods = []
        while (up_to_date and start < up_to_date) or len(periods) < 1:
            rule, until, billing_information = self._get_invoice_rrule(start)
            for date in rule:
                if hasattr(date, 'date'):
                    date = date.date()
                if date == start:
                    continue
                end = date + relativedelta(days=-1)
                periods.append((start, min(end, self.end_date or
                            datetime.date.max), billing_information))
                start = date
                if (up_to_date and start >= up_to_date) or not up_to_date:
                    break
            if until and (up_to_date and until < up_to_date):
                if self.end_date and self.end_date < up_to_date:
                    if until > self.end_date:
                        until = self.end_date
                if start != until:
                    end = until + relativedelta(days=-1)
                    periods.append((start, end, billing_information))
                    start = until
        return periods

    def first_invoice(self):
        ContractInvoice = Pool().get('contract.invoice')
        ContractInvoice.delete(self.invoices)
        self.invoice([self], self.start_date)

    @classmethod
    def invoice(cls, contracts, up_to_date):
        'Invoice contracts up to the date'
        periods = defaultdict(list)
        for contract in contracts:
            if contract.status not in ('active', 'quote'):
                continue
            for period in contract.get_invoice_periods(min(up_to_date,
                        contract.end_date or datetime.date.max)):
                periods[period].append(contract)
        return cls.invoice_periods(periods)

    @classmethod
    def invoice_periods(cls, periods):
        'Invoice periods for contracts'
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractInvoice = pool.get('contract.invoice')
        Journal = pool.get('account.journal')
        journals = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        if journals:
            journal, = journals
        else:
            journal = None

        invoices = defaultdict(list)
        for period, contracts in periods.iteritems():
            for contract in contracts:
                invoice = contract.get_invoice(*period)
                if not invoice.journal:
                    invoice.journal = journal
                if (not invoice.invoice_address
                        and contract.subscriber.addresses):
                    #TODO : To enhance
                    invoice.invoice_address = contract.subscriber.addresses[0]
                invoice.lines = contract.get_invoice_lines(*period[0:2])
                invoices[period].append((contract, invoice))
        new_invoices = Invoice.create([i._save_values
                 for contract_invoices in invoices.itervalues()
                 for c, i in contract_invoices])
        Invoice.update_taxes(new_invoices)
        # Set the new ids
        old_invoices = (i for ci in invoices.itervalues() for c, i in ci)
        for invoice, new_invoice in zip(old_invoices, new_invoices):
            invoice.id = new_invoice.id
        contract_invoices_to_create = []
        for period, contract_invoices in invoices.iteritems():
            start, end, billing_information = period
            for contract, invoice in contract_invoices:
                contract_invoices_to_create.append(ContractInvoice(
                        contract=contract,
                        invoice=invoice,
                        start=start,
                        end=end))
        return ContractInvoice.create([c._save_values
                for c in contract_invoices_to_create])

    def get_invoice(self, start, end, billing_information):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        return Invoice(
            company=self.company,
            type='out_invoice',
            journal=None,
            party=self.subscriber,
            invoice_address=self.get_contract_address(),
            currency=self.get_currency(),
            account=self.subscriber.account_receivable,
            payment_term=billing_information.payment_term,
            state='validated',
            )

    def get_invoice_lines(self, start, end):
        lines = []
        for premium in self.premiums:
            lines.extend(premium.get_invoice_lines(start, end))
        for option in self.options:
            lines.extend(option.get_invoice_lines(start, end))
        for covered_element in self.covered_elements:
            lines.extend(covered_element.get_invoice_lines(start, end))
        return lines

    @classmethod
    @ModelView.button
    def button_calculate_prices(cls, contracts):
        for contract in contracts:
            contract.calculate_prices()

    def before_activate(self, contract_dict=None):
        super(Contract, self).before_activate(contract_dict)
        self.save()
        self.calculate_prices()

    def calculate_prices(self):
        prices, errs = self.calculate_prices_between_dates()
        if errs:
            return False, errs
        self.store_prices(prices)
        return True, ()

    def calculate_price_at_date(self, date):
        cur_dict = {
            'date': date,
            'appliable_conditions_date': self.appliable_conditions_date}
        self.init_dict_for_rule_engine(cur_dict)
        prices, errs = self.product.get_result('total_price', cur_dict)
        return (prices, errs)

    def calculate_prices_between_dates(self, start=None, end=None):
        if not start:
            start = self.start_date
        prices = {}
        errs = []
        dates = self.get_dates()
        dates = utils.limit_dates(dates, self.start_date)
        for cur_date in dates:
            price, err = self.calculate_price_at_date(cur_date)
            if price:
                prices[cur_date] = price
            errs += err
            if errs:
                return {}, errs
        return prices, errs

    def store_price(self, price, start_date, end_date):
        to_check_for_deletion = set()
        to_save = []
        Premium = Pool().get('contract.premium')
        new_premium = Premium.new_line(price, start_date, end_date)
        if new_premium:
            parent = new_premium.get_parent()
            if not end_date and not getattr(new_premium, 'end', None):
                new_premium.end = getattr(parent, 'end_date', None)
            if isinstance(parent.premiums, tuple):
                parent.premiums = list(parent.premiums)
            parent.premiums.append(new_premium)
            to_check_for_deletion.add(parent)
            to_save.append(new_premium)
        return to_save, to_check_for_deletion

    def store_prices(self, prices):
        if not prices:
            return
        Premium = Pool().get('contract.premium')
        dates = list(prices.iterkeys())
        dates.sort()
        to_check_for_deletion = set()
        to_save = []
        for date, price_list in prices.iteritems():
            date_pos = dates.index(date)
            if date_pos < len(dates) - 1:
                end_date = dates[date_pos + 1] + datetime.timedelta(days=-1)
            else:
                end_date = None
            for price in price_list:
                price_save, price_delete = self.store_price(price,
                    start_date=date, end_date=end_date)
                to_save += price_save
                to_check_for_deletion.update(price_delete)
        to_delete = set()
        for elem in to_check_for_deletion:
            existing = [x for x in getattr(elem, 'premiums', []) if x.id > 0]
            if not existing:
                continue
            to_delete.update(set(
                    x for x in existing if x.start >= dates[0]))
            for elem in existing:
                if (datetime.date.min or elem.start) < dates[0] <= (
                        elem.end or datetime.date.max):
                    elem.end = coop_date.add_day(dates[0], -1)
                    elem.save()
                    break
        if to_delete:
            Premium.delete(list(to_delete))
        if to_save:
            Premium.create([x._save_values for x in to_save])
        self.browse([self.id])[0].remove_premium_duplicates()
        # TODO : Remove this once premium changes are stored in the instances
        # and saved once globally
        for elem in to_check_for_deletion:
            elem.premiums = tuple(Premium.search([
                        (elem._fields['premiums'].field, '=', elem)]))

    def get_premium_list(self):
        result = list(self.premiums)
        for option in self.options:
            result.extend(option.get_premium_list())
        for covered_element in self.covered_elements:
            result.extend(covered_element.get_premium_list())
        return result

    def remove_premium_duplicates(self):
        Pool().get('contract.premium').remove_duplicates(
            self.get_premium_list())

    def init_from_product(self, product, start_date=None, end_date=None):
        pool = Pool()
        res, errs = super(Contract, self).init_from_product(product,
            start_date, end_date)
        BillingInformation = pool.get('contract.billing_information')
        if not product.billing_modes:
            return res, errs
        default_billing_mode = product.billing_modes[0]
        if default_billing_mode.direct_debit:
            days = default_billing_mode.get_allowed_direct_debit_days()
            direct_debit_day = days[0][0]
        else:
            direct_debit_day = 0
        self.billing_informations = [BillingInformation(start=self.start_date,
            billing_mode=default_billing_mode,
            payment_term=default_billing_mode.allowed_payment_terms[0],
            direct_debit_day=direct_debit_day)]
        return res, errs


class _ContractRevisionMixin(object):
    contract = fields.Many2One('contract', 'Contract', required=True,
        select=True, ondelete='CASCADE')
    date = fields.Date('Date')
    value = None

    @classmethod
    def __setup__(cls):
        super(_ContractRevisionMixin, cls).__setup__()
        cls._order.insert(0, ('date', 'ASC'))
        # TODO unique constraint on (contract, date) ?

    @staticmethod
    def order_date(tables):
        table, _ = tables[None]
        return [Coalesce(table.date, datetime.date.min)]

    @staticmethod
    def revision_columns():
        return ['value']

    @classmethod
    def get_values(cls, contracts, names=None, date=None, default=None):
        'Return a dictionary with the variable name as key,'
        'and a dictionnary as value. The dictionnary value contains'
        'contract id as key and variable value as value'

        cursor = Transaction().cursor
        table = cls.__table__()
        values = dict(((x, dict(((y.id, None) for y in contracts)))
                for x in ['contract', 'billing_mode'] +
                cls.revision_columns()))
        in_max = cursor.IN_MAX
        columns = [table.contract,
            table.id.as_('billing_mode')] + [
            Column(table, c) for c in cls.revision_columns()]
        for i in range(0, len(contracts), in_max):
            sub_ids = [c.id for c in contracts[i:i + in_max]]
            where_contract = reduce_ids(table.contract, sub_ids)
            subquery = table.select(
                table.contract,
                Max(Coalesce(table.date, datetime.date.min)).as_('date'),
                where=((table.date <= date) | (table.date == None))
                & where_contract,
                group_by=table.contract)
            cursor.execute(*table.join(subquery,
                    condition=(table.contract == subquery.contract)
                    & (Coalesce(table.date, datetime.date.min) ==
                        Coalesce(subquery.date, datetime.date.min))
                    ).select(*columns))
            for elem in cursor.dictfetchall():
                for field_name, value in elem.iteritems():
                    values[field_name][elem['contract']] = value
        return values


class ContractBillingInformation(_ContractRevisionMixin, model.CoopSQL,
        model.CoopView):
    'Contract Billing Information'
    __name__ = 'contract.billing_information'

    billing_mode = fields.Many2One('offered.billing_mode',
        'Billing Mode', required=True, ondelete='CASCADE',
        domain=[('products', '=',
            Eval('_parent_contract', {}).get('product'))],
        depends=['contract'])
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', ondelete='CASCADE', states={
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active')),
            'invisible': Len(Eval('possible_payment_terms', [])) < 2},
        domain=[('id', 'in', Eval('possible_payment_terms'))],
        depends=['possible_payment_terms'])
    direct_debit = fields.Function(
        fields.Boolean('Direct Debit Payment'), 'on_change_with_direct_debit')
    direct_debit_day_selector = fields.Function(
        fields.Selection('get_allowed_direct_debit_days',
            'Direct Debit Day', states={
                'invisible': ~Eval('direct_debit', False),
                'required': And(Eval('direct_debit', False),
                    (Eval('_parent_contract', {}).get('status', '') ==
                        'active'))},
            sort=False, depends=['direct_debit']),
            'get_direct_debit_day_selector', 'set_direct_debit_day_selector')
    direct_debit_day = fields.Integer('Direct Debit Day')
    direct_debit_account = fields.Many2One('bank.account',
        'Direct Debit Account',
        states={'invisible': ~Eval('direct_debit'),
            'required': And(Eval('direct_debit', False),
                (Eval('_parent_contract', {}).get('status', '') == 'active'))},
        domain=[('owners', '=',
            Eval('_parent_contract', {}).get('subscriber'))],
        depends=['direct_debit'])
    possible_payment_terms = fields.Function(fields.One2Many(
            'account.invoice.payment_term', None, 'Possible Payment Term'),
            'on_change_with_possible_payment_terms')

    @classmethod
    def __setup__(cls):
        super(ContractBillingInformation, cls).__setup__()
        cls.__rpc__.update({
                'get_allowed_direct_debit_days': RPC(instantiate=0)
                })

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.1: Billing change
        migrate = False
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        if (not TableHandler.table_exist(cursor,
                'contract_billing_information') and TableHandler.table_exist(
                    cursor, 'contract_invoice_frequency')):
            migrate = True

        super(ContractBillingInformation, cls).__register__(module_name)

        # Migration from 1.1: Billing change
        if migrate:
            cursor.execute('insert into '
                '"contract_billing_information" '
                '(id, create_uid, create_date, write_uid, write_date,'
                'billing_mode, contract, date, direct_debit_day, '
                'direct_debit_account) '
                'select f.id, f.create_uid, f.create_date, f.write_uid, '
                'f.write_date, f.value, f.contract, f.date, '
                'cast(c.direct_debit_day as integer), '
                'c.direct_debit_account from '
                'contract_invoice_frequency as f, '
                'contract as c where f.contract = c.id')

    @fields.depends('billing_mode')
    def get_allowed_direct_debit_days(self):
        if not self.billing_mode:
            return [('', '')]
        return self.billing_mode.get_allowed_direct_debit_days()

    def get_direct_debit_day_selector(self, name):
        if not self.direct_debit:
            return ''
        return str(self.direct_debit_day)

    @classmethod
    def set_direct_debit_day_selector(cls, ids, name, value):
        if not value:
            return
        cls.write(ids, {'direct_debit_day': int(value)})

    @fields.depends('billing_mode')
    def on_change_with_direct_debit(self, name=None):
        if self.billing_mode:
            return self.billing_mode.direct_debit

    @fields.depends('billing_mode')
    def on_change_with_possible_payment_terms(self, name=None):
        if not self.billing_mode:
            return []
        return [x.id for x in self.billing_mode.allowed_payment_terms]

    @fields.depends('billing_mode')
    def on_change_with_payment_term(self, name=None):
        if not self.billing_mode:
            return None
        return self.billing_mode.allowed_payment_terms[0].id\
            if self.billing_mode else None

    @fields.depends('direct_debit_day_selector')
    def on_change_direct_debit_day_selector(self):
        if not self.direct_debit_day_selector:
            return {'direct_debit_day': None}
        return {'direct_debit_day': int(self.direct_debit_day_selector)}

    @staticmethod
    def revision_columns():
        return ['billing_mode', 'payment_term', 'direct_debit_day',
            'direct_debit_account']


class ContractInvoice(ModelSQL, ModelView):
    'Contract Invoice'
    __name__ = 'contract.invoice'
    contract = fields.Many2One('contract', 'Contract', required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', required=True,
        ondelete='CASCADE')
    invoice_state = fields.Function(fields.Selection([
                ('draft', 'Draft'),
                ('validated', 'Validated'),
                ('posted', 'Posted'),
                ('paid', 'Paid'),
                ('cancel', 'Canceled'),
                ], 'Invoice State'), 'get_invoice_state',
        searcher='search_invoice_state')
    start = fields.Date('Start Date', required=True)
    end = fields.Date('End Date', required=True)

    @classmethod
    def __setup__(cls):
        super(ContractInvoice, cls).__setup__()
        cls._order.insert(0, ('start', 'DESC'))
        cls._buttons.update({
                'reinvoice': {
                    'invisible': Eval('invoice_state') == 'cancel',
                    },
                'cancel': {
                    'invisible': Eval('invoice_state') == 'cancel',
                    },
                })

    def get_invoice_state(self, name):
        return self.invoice.state

    @classmethod
    def search_invoice_state(cls, name, domain):
        return [('invoice.state',) + tuple(domain[1:])]

    @classmethod
    def validate(cls, contract_invoices):
        super(ContractInvoice, cls).validate(contract_invoices)
        for contract_invoice in contract_invoices:
            contract_invoice.check_dates()

    def check_dates(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        cursor = Transaction().cursor
        table = self.__table__()
        invoice = Invoice.__table__()
        cursor.execute(*table.join(invoice,
                condition=table.invoice == invoice.id
                ).select(table.id,
                where=(((table.start <= self.start)
                        & (table.end >= self.start))
                    | ((table.start <= self.end)
                        & (table.end >= self.end))
                    | ((table.start >= self.start)
                        & (table.end <= self.end)))
                    & (table.contract == self.id)
                    & (invoice.state != 'cancel')))

    @classmethod
    @ModelView.button
    def reinvoice(cls, contract_invoices):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Contract = pool.get('contract')
        invoices = []
        for contract_invoice in contract_invoices:
            assert contract_invoice.invoice_state != 'cancel'
            invoices.append(contract_invoice.invoice)
        Invoice.cancel(invoices)
        periods = defaultdict(list)
        for contract_invoice in contract_invoices:
            period = contract_invoice.start, contract_invoice.end
            periods[period].append(contract_invoice.contract)
        Contract.invoice_periods(periods)

    @classmethod
    @ModelView.button
    def cancel(cls, contract_invoices):
        pool = Pool()
        Reconciliation = pool.get('account.move.reconciliation')
        Invoice = pool.get('account.invoice')

        invoices = [c.invoice for c in contract_invoices]
        reconciliations = []
        for invoice in invoices:
            if invoice.move:
                for line in invoice.move.lines:
                    if line.reconciliation:
                        reconciliations.append(line.reconciliation)
        if reconciliations:
            Reconciliation.delete(reconciliations)
        Invoice.cancel(invoices)

    @classmethod
    def delete(cls, contract_invoices):
        Invoice = Pool().get('account.invoice')
        Invoice.delete([x.invoice for x in contract_invoices])
        super(ContractInvoice, cls).delete(contract_invoices)


class CoveredElement:
    __name__ = 'contract.covered_element'

    premiums = fields.One2Many('contract.premium', 'covered_element',
        'Premiums')

    def get_invoice_lines(self, start, end):
        lines = []
        for premium in self.premiums:
            lines.extend(premium.get_invoice_lines(start, end))
        for option in self.options:
            lines.extend(option.get_invoice_lines(start, end))
        return lines

    def get_premium_list(self):
        result = list(self.premiums)
        for option in self.options:
            result.extend(option.get_premium_list())
        return result


class ContractOption:
    __name__ = 'contract.option'

    premiums = fields.One2Many('contract.premium', 'option', 'Premiums')

    def get_invoice_lines(self, start, end):
        lines = []
        if ((self.start_date or datetime.date.min) <= end
                and start <= (self.end_date or datetime.date.max)):
            for premium in self.premiums:
                lines.extend(premium.get_invoice_lines(start, end))
            for extra_premium in self.extra_premiums:
                lines.extend(extra_premium.get_invoice_lines(start, end))
        return lines

    def get_premium_list(self):
        result = list(self.premiums)
        for extra_premium in self.extra_premiums:
            result.extend(extra_premium.get_premium_list())
        return result


class ExtraPremium:
    __name__ = 'contract.option.extra_premium'

    premiums = fields.One2Many('contract.premium', 'option', 'Premiums')

    def get_invoice_lines(self, start, end):
        lines = []
        if ((self.start_date or datetime.date.min) <= end
                and start <= (self.end_date or datetime.date.max)):
            for premium in self.premiums:
                lines.extend(premium.get_invoice_lines(start, end))
        return lines

    def get_premium_list(self):
        return list(self.premiums)


class Premium(ModelSQL, ModelView):
    'Premium'
    __name__ = 'contract.premium'
    contract = fields.Many2One('contract', 'Contract', select=True,
        ondelete='CASCADE')
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', select=True, ondelete='CASCADE')
    option = fields.Many2One('contract.option', 'Option', select=True,
        ondelete='CASCADE')
    extra_premium = fields.Many2One('contract.option.extra_premium',
        'Extra Premium', select=True, ondelete='CASCADE')
    rated_entity = fields.Reference('Rated Entity', 'get_rated_entities',
        required=True)
    start = fields.Date('Start')
    end = fields.Date('End')
    amount = fields.Numeric('Amount', required=True)
    frequency = fields.Selection(PREMIUM_FREQUENCIES, 'Frequency', sort=False)
    taxes = fields.Many2Many('contract.premium-account.tax',
        'premium', 'tax', 'Taxes',
        domain=[
            ('parent', '=', None),
            ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both']),
                ],
            ])
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ('kind', '=', 'revenue'),
            ])
    invoice_lines = fields.One2Many('account.invoice.line', 'origin',
        'Invoice Lines', readonly=True)
    main_contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_main_contract')

    @classmethod
    def __setup__(cls):
        super(Premium, cls).__setup__()
        cls._order = [('rated_entity', 'ASC'), ('start', 'ASC')]

    @classmethod
    def _get_rated_entities(cls):
        'Return list of Model names for origin Reference'
        return [
            'offered.product',
            'offered.option.description',
            'account.fee.description',
            ]

    @classmethod
    def get_rated_entities(cls):
        Model = Pool().get('ir.model')
        models = cls._get_rated_entities()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @classmethod
    def get_possible_parent_field(cls):
        return set(['contract', 'covered_element', 'option', 'extra_premium'])

    def get_parent(self):
        for elem in self.get_possible_parent_field():
            value = getattr(self, elem, None)
            if value:
                return value

    def get_main_contract(self, name=None):
        if self.contract:
            return self.contract.id
        if self.covered_element:
            return self.covered_element.main_contract.id
        if self.option:
            return self.option.parent_contract.id
        if self.extra_premium:
            return self.extra_premium.option.parent_contract.id

    def get_description(self):
        return '%s - %s' % (self.get_parent().rec_name,
            self.rated_entity.rec_name)

    def _get_rrule(self, start):
        if self.frequency in ('monthly', 'quarterly', 'half_yearly'):
            freq = MONTHLY
            interval = {
                'monthly': 1,
                'quarterly': 3,
                'half_yearly': 6,
                }.get(self.frequency)
        elif self.frequency == 'yearly':
            freq = YEARLY
            interval = 1
        elif self.frequency == 'yearly_360':
            freq = DAILY
            interval = 360
        elif self.frequency == 'yearly_365':
            freq = DAILY
            interval = 365
        elif self.frequency in ('once_per_contract'):
            return rrule(MONTHLY, dtstart=self.start, count=2)
        else:
            return
        return rrule(freq, interval=interval, dtstart=start)

    def get_amount(self, start, end):
        if self.frequency in ('once_per_invoice'):
            return self.amount
        rrule = self._get_rrule(start)
        start = datetime.datetime.combine(start, datetime.time())
        end = datetime.datetime.combine(end, datetime.time())
        occurences = rrule.between(start, end + datetime.timedelta(2))
        amount = len(occurences) * self.amount
        try:
            last_date = occurences[-1]
        except IndexError:
            last_date = start
        next_date = rrule.after(last_date)
        if self.frequency in ('once_per_contract'):
            if (last_date <= datetime.datetime.combine(self.start,
                    datetime.time()) <= next_date):
                return self.amount
            elif (start <= datetime.datetime.combine(self.start,
                    datetime.time())):
                return self.amount
            else:
                return 0
        if next_date and (next_date - end).days > 1:
            if (end - last_date).days != 0:
                ratio = (((end - last_date).days + 1.)
                    / ((next_date - last_date).days))
                amount += self.amount * Decimal(ratio)
        return amount

    def get_invoice_lines(self, start, end):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        if ((self.start or datetime.date.min) > end
                or (self.end or datetime.date.max) < start):
            return []
        start = (start if start > (self.start or datetime.date.min)
            else self.start)
        end = end if end < (self.end or datetime.date.max) else self.end
        amount = self.get_amount(start, end)
        if not amount:
            return []
        return [InvoiceLine(
                type='line',
                description=self.get_description(),
                origin=self,
                quantity=1,
                unit=None,
                unit_price=self.main_contract.company.currency.round(amount),
                taxes=self.taxes,
                invoice_type='out_invoice',
                account=self.account,
                coverage_start=start,
                coverage_end=end,
                )]

    def set_parent_from_line(self, line):
        for elem in self.get_possible_parent_field():
            field = self._fields[elem]
            if field.model_name == line['target'].__name__:
                setattr(self, elem, line['target'])
                break

    def calculate_rated_entity(self):
        # TODO : use the line rated_entity once it is implemented
        parent = self.get_parent()
        if parent.__name__ == 'contract':
            rated_entity = parent.product
        elif parent.__name__ == 'contract.option':
            rated_entity = parent.coverage
        elif parent.__name__ == 'contract.covered_element':
            rated_entity = parent.contract
        elif parent.__name__ == 'extra_premium':
            rated_entity = parent.option
        else:
            rated_entity = None
        return rated_entity

    @classmethod
    def new_line(cls, line, start_date, end_date):
        if 'target' not in line:
            return None
        new_instance = cls()
        new_instance.set_parent_from_line(line)
        parent = new_instance.get_parent()
        if not parent:
            # TODO : Should raise an error
            return None
        new_instance.rated_entity = line['rated_entity']
        # TODO : use the line account once it is implemented
        new_instance.account = new_instance.rated_entity.account_for_billing
        new_instance.start = start_date
        if getattr(parent, 'end_date', None) and (not end_date
                or parent.end_date < end_date):
            new_instance.end = parent.end_date
        else:
            new_instance.end = end_date
        new_instance.amount = line['amount']
        if line['taxes']:
            new_instance.taxes = line['taxes']
        new_instance.frequency = line['frequency']
        return new_instance

    @classmethod
    def remove_duplicates(cls, elems):
        to_del = []
        to_write = set()
        prev = None
        for elem in elems:
            if not prev:
                prev = elem
                continue
            if prev.rated_entity != elem.rated_entity:
                prev = elem
                continue
            if prev.same_value(elem):
                prev.end = elem.end
                to_del.append(elem)
                to_write.add(prev)
                continue
            prev = elem
        if to_del:
            cls.delete(to_del)
        if to_write:
            values = []
            for elem in to_write:
                values.extend([[elem], elem._save_values])
            cls.write(*values)

    def same_value(self, other):
        ident_fields = ('amount', 'frequency', 'rated_entity', 'account')
        for elem in ident_fields:
            if getattr(self, elem) != getattr(other, elem):
                return False
        if self.get_parent() != other.get_parent():
            return False
        if set(self.taxes) != set(other.taxes):
            return False
        return True

    def get_rec_name(self, name):
        return '(%s - %s) %s' % (self.start, self.end or '', self.amount)


class PremiumTax(ModelSQL):
    'Premium - Tax'
    __name__ = 'contract.premium-account.tax'
    premium = fields.Many2One('contract.premium', 'Premium',
        ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
        required=True)


class InvoiceContractStart(ModelView):
    'Invoice Contract'
    __name__ = 'contract.invoice.start'
    up_to_date = fields.Date('Up To Date', required=True)


class InvoiceContract(Wizard):
    'Invoice Contract'
    __name__ = 'contract.invoice'
    start = StateView('contract.invoice.start',
        'contract_insurance_invoice.invoice_start_view_form', [
            Button('Cancel', 'end', icon='tryton-cancel'),
            Button('Ok', 'invoice', icon='tryton-ok', default=True),
            ])
    invoice = StateTransition()

    def transition_invoice(self):
        pool = Pool()
        Contract = pool.get('contract')
        contracts = Contract.browse(Transaction().context['active_ids'])
        Contract.invoice(contracts, self.start.up_to_date)
        return 'end'


class DisplayContractPremium(Wizard):
    'Display Contrat Premium'

    __name__ = 'contract.premium.display'

    start_state = 'display'
    display = StateView('contract.premium.display.premiums',
        'contract_insurance_invoice.display_premiums_view_form', [
            Button('Calculate Prices', 'calculate_prices', 'tryton-refresh'),
            Button('Exit', 'end', 'tryton-cancel', default=True)])
    calculate_prices = StateTransition()

    @classmethod
    def __setup__(cls):
        super(DisplayContractPremium, cls).__setup__()
        cls._error_messages.update({
                'no_contract_found': 'No contract found in context',
                })

    @classmethod
    def get_children_fields(cls):
        return {
            'contract': ['options', 'covered_elements'],
            'contract.covered_element': ['options'],
            'contract.option': ['extra_premiums'],
            }

    @classmethod
    def new_line(cls, line=None):
        return {
            'name': '%s - %s' % (line.start, line.end or '') if line else '',
            'premium': line.id if line else 0,
            'premiums': [line.id] if line else [],
            'amount': line.amount if line else 0,
            'childs': [],
            }

    def add_lines(self, source, parent):
        for field_name in self.get_children_fields().get(source.__name__, ()):
            values = getattr(source, field_name, None)
            if not values:
                continue
            for elem in values:
                base_line = self.new_line()
                base_line['name'] = elem.rec_name
                self.add_lines(elem, base_line)
                parent['childs'].append(base_line)
                parent['amount'] += base_line['amount']
        if source.premiums:
            premium_root = self.new_line()
            premium_root['name'] = 'Premium'
            for elem in source.premiums:
                premium_line = self.new_line(line=elem)
                if elem.start <= utils.today() <= (
                        elem.end or datetime.date.max):
                    premium_root['amount'] += elem.amount
                premium_root['childs'].append(premium_line)
            parent['childs'].append(premium_root)
            parent['amount'] += premium_root['amount']
        return parent

    def default_display(self, name):
        try:
            contracts = Pool().get('contract').browse(
                Transaction().context.get('active_ids'))
        except:
            self.raise_user_error('no_contract_found')
        lines = []
        for contract in contracts:
            contract_line = self.new_line()
            contract_line['name'] = contract.rec_name
            self.add_lines(contract, contract_line)
            lines.append(contract_line)
        return {'premiums': lines}

    def transition_calculate_prices(self):
        Contract = Pool().get('contract')
        Contract.button_calculate_prices(Contract.browse(
                Transaction().context.get('active_ids', [])))
        return 'display'


class DisplayContractPremiumDisplayer(model.CoopView):
    'Display Contract Premium Displayer'

    __name__ = 'contract.premium.display.premiums'

    premiums = fields.One2Many('contract.premium.display.premiums.line',
        None, 'Premiums', readonly=True)


class DisplayContractPremiumDisplayerPremiumLine(model.CoopView):
    'Display Contract Premium Displayer Prmeium Line'

    __name__ = 'contract.premium.display.premiums.line'

    amount = fields.Numeric('Amount Today')
    childs = fields.One2Many('contract.premium.display.premiums.line', None,
        'Childs')
    premiums = fields.One2Many('contract.premium', None, 'Premium')
    premium = fields.Many2One('contract.premium', 'Premium')
    name = fields.Char('Name')


class CreateInvoiceContractBatch(batchs.BatchRoot):
    'Contract Invoice Creation Batch'

    __name__ = 'contract.invoice.create'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def get_batch_name(cls):
        return 'Contract invoice creation'

    @classmethod
    def get_batch_stepping_mode(cls):
        return 'divide'

    @classmethod
    def get_batch_step(cls):
        return 4

    @classmethod
    def select_ids(cls):
        cursor = Transaction().cursor
        pool = Pool()

        contract = pool.get('contract').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()

        query_table = contract.join(contract_invoice, 'LEFT', condition=(
                contract.id == contract_invoice.contract))

        cursor.execute(*query_table.select(contract.id, group_by=contract.id,
                where=(contract.status == 'active'),
                having=(
                    (Max(contract_invoice.end) < utils.today())
                    | (Max(contract_invoice.end) == None))))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, logger):
        Pool().get('contract').invoice(objects, utils.today())


class PostInvoiceContractBatch(batchs.BatchRoot):
    'Post Contract Invoice Batch'

    __name__ = 'contract.invoice.post'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.invoice'

    @classmethod
    def get_batch_name(cls):
        return 'Contract invoice posting'

    @classmethod
    def get_batch_stepping_mode(cls):
        return 'divide'

    @classmethod
    def get_batch_step(cls):
        return 4

    @classmethod
    def select_ids(cls):
        cursor = Transaction().cursor
        pool = Pool()

        account_invoice = pool.get('account.invoice').__table__()
        contract_invoice = pool.get('contract.invoice').__table__()

        query_table = contract_invoice.join(account_invoice, 'LEFT',
            condition=(account_invoice.id == contract_invoice.invoice))

        cursor.execute(*query_table.select(account_invoice.id,
                where=((contract_invoice.start <= utils.today())
                    & (account_invoice.state == 'validated'))))

        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, logger):
        Pool().get('account.invoice').post(objects)
