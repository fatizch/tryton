from collections import defaultdict
import datetime
try:
    import simplejson as json
except ImportError:
    import json
from sql import Null, Window, Literal
from sql.conditionals import NullIf, Coalesce
from sql.aggregate import Max, Min

from trytond import backend
from trytond.tools import grouped_slice
from trytond.rpc import RPC
from trytond.cache import Cache
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, Bool, And
from trytond.protocols.jsonrpc import JSONDecoder
from trytond.pool import Pool
from trytond.model import dualmethod, Unique
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.modules.cog_utils import utils, model, fields, coop_date
from trytond.modules.cog_utils import coop_string, export
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.offered import offered
from trytond.error import UserError


CONTRACTSTATUSES = [
    ('quote', 'Quote'),
    ('active', 'Active'),
    ('hold', 'Hold'),
    ('void', 'Void'),
    ('terminated', 'Terminated'),
    ('declined', 'Declined'),
    ]
OPTIONSTATUS = CONTRACTSTATUSES + [
    ('refused', 'Refused'),
    ]
_STATES = {
    'readonly': Eval('status') != 'quote',
    }
_DEPENDS = ['status']
_CONTRACT_STATUS_STATES = {
    'readonly': Eval('contract_status') != 'quote',
    }
_CONTRACT_STATUS_DEPENDS = ['contract_status']
_STATUSES_WITH_SUBSTATUS = ['void', 'terminated', 'declined', 'hold']


__all__ = [
    'ActivationHistory',
    'Contract',
    'ContractOption',
    'ContractOptionVersion',
    'ContractExtraDataRevision',
    'ContractSelectEndDate',
    'ContractEnd',
    'ContractSelectStartDate',
    'ContractChangeStartDate',
    'ContractSelectHoldReason',
    'ContractHold',
    'ContractSubStatus',
    '_STATES',
    '_DEPENDS',
    '_CONTRACT_STATUS_STATES',
    '_CONTRACT_STATUS_DEPENDS',
    ]


class ActivationHistory(model.CoopSQL, model.CoopView):
    'Activation History'

    __name__ = 'contract.activation_history'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    contract = fields.Many2One('contract', 'Contract', required=True,
        ondelete='CASCADE', select=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date', domain=['OR',
            ('end_date', '=', None),
            ('start_date', '=', None),
            ('end_date', '>=', Eval('start_date', datetime.date.min))],
        depends=['start_date'])
    termination_reason = fields.Many2One('contract.sub_status',
        'Termination Reason', domain=[('status', '=', 'terminated')],
        ondelete='RESTRICT')
    active = fields.Boolean('Active')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.4 add active field
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        do_migrate = False
        history_table = TableHandler(cursor, cls)
        if not history_table.column_exist('active'):
            do_migrate = True
        super(ActivationHistory, cls).__register__(module_name)
        if not do_migrate:
            return
        cursor.execute("UPDATE contract_activation_history "
            "SET active = 'TRUE'")

    @classmethod
    def __setup__(cls):
        super(ActivationHistory, cls).__setup__()
        cls._order = [('contract', 'ASC'), ('start_date', 'DESC')]

    def get_func_key(self, name):
        return self.contract.quote_number

    @staticmethod
    def default_active():
        return True

    @classmethod
    def search_func_key(cls, name, clause):
        return [('contract.quote_number',) + tuple(clause[1:])]

    def clean_before_reactivate(self):
        self.termination_reason = None
        self.end_date = None

    def get_rec_name(self, name):
        Date = Pool().get('ir.date')
        return "[%s - %s]" % (
            Date.date_as_string(self.start_date) if self.start_date else '',
            Date.date_as_string(self.end_date) if self.end_date else '')


class Contract(model.CoopSQL, model.CoopView, ModelCurrency):
    'Contract'

    __name__ = 'contract'
    _history = True
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, ondelete='RESTRICT', states=_STATES, depends=_DEPENDS)
    quote_number = fields.Char('Quote Number', readonly=True)
    contract_number = fields.Char('Contract Number', select=1,
        states={
            'required': Eval('status') == 'active',
            }, depends=_DEPENDS, readonly=True)
    extra_datas = fields.One2Many('contract.extra_data', 'contract',
        'Extra Data', delete_missing=True, states={
            'invisible': ~Eval('extra_datas'),
            'readonly': Eval('status') != 'quote',
            }, depends=['extra_datas', 'status'])
    product = fields.Many2One('offered.product', 'Product',
        ondelete='RESTRICT', required=True, domain=[
            If(~Eval('start_date', None),
                [],
                [
                    ['OR', ('end_date', '>=', Eval('start_date')),
                        ('end_date', '=', None)],
                    ['OR', ('start_date', '<=', Eval('start_date')),
                        ('start_date', '=', None)]]),
            ('company', '=', Eval('company')),
            ], states=_STATES, depends=['start_date', 'status', 'company'])
    options = fields.One2ManyDomain('contract.option', 'contract', 'Options',
        context={
            'start_date': Eval('start_date'),
            'product': Eval('product'),
            'all_extra_datas': Eval('extra_data_values')},
        domain=[
            ('coverage.products', '=', Eval('product')),
            ('status', '!=', 'declined'),
            ],
        states=_STATES, depends=['status', 'start_date', 'product',
            'extra_data_values'], target_not_required=True,
            order=[('coverage', 'ASC'), ('start_date', 'ASC')])
    declined_options = fields.One2ManyDomain('contract.option', 'contract',
        'Declined Options', states=_STATES, depends=['status'],
        domain=[('status', '=', 'declined')], target_not_required=True)
    activation_history = fields.One2Many('contract.activation_history',
        'contract', 'Activation History', order=[('start_date', 'ASC')],
        states=_STATES, depends=_DEPENDS, delete_missing=True)
    initial_start_date = fields.Function(
        fields.Date('Initial Start Date',
            states={
                'invisible': Eval('initial_start_date') == Eval('start_date'),
                }),
        'get_initial_start_date')
    start_date = fields.Function(
        fields.Date('Start Date', states={
                'readonly': Eval('status') != 'quote',
                'required': Eval('status') != 'void',
                }, depends=['status']),
        'getter_activation_history', 'setter_start_date',
        searcher='search_contract_date')
    end_date = fields.Function(
        fields.Date('End Date', states=_STATES, depends=_DEPENDS),
        'getter_activation_history', 'setter_end_date',
        searcher='search_contract_date')
    appliable_conditions_date = fields.Date('Appliable Conditions Date',
        states=_STATES, depends=_DEPENDS)
    start_management_date = fields.Date('Management Date', states=_STATES,
        depends=_DEPENDS)
    signature_date = fields.Date('Signature Date', states=_STATES,
        depends=_DEPENDS)
    status = fields.Selection(CONTRACTSTATUSES, 'Status', states=_STATES,
        depends=_DEPENDS, required=True)
    status_string = status.translated('status')
    subscriber = fields.Many2One('party.party', 'Subscriber',
        domain=[If(
                Eval('subscriber_kind') == 'person',
                [('is_person', '=', True)],
                []),
            If(
                Eval('subscriber_kind') == 'company',
                [('is_company', '=', True)],
                [])],
        states=_STATES, depends=['subscriber_kind', 'status'],
        ondelete='RESTRICT')
    parties = fields.Function(
        fields.Many2Many('party.party', None, None, 'Parties'),
        'get_parties', searcher='search_parties')
    current_policy_owner = fields.Function(
        fields.Many2One('party.party', 'Current Policy Owner'),
        'on_change_with_current_policy_owner')
    sub_status = fields.Many2One('contract.sub_status', 'Details on status',
        states={
            'readonly': Eval('status') != 'quote',
            'required': Bool(Eval('is_sub_status_required')),
            'invisible': ~Eval('is_sub_status_required')
            },
        domain=[('status', '=', Eval('status'))], ondelete='RESTRICT',
        depends=['status', 'is_sub_status_required'])
    is_sub_status_required = fields.Function(
        fields.Boolean('Is Sub Status Required', depends=['status']),
        'on_change_with_is_sub_status_required')
    extra_data_values = fields.Function(
        fields.Dict('extra_data', 'Extra Data'),
        'get_extra_data')
    extra_data_values_string = extra_data_values.translated(
        'extra_data_values')
    product_subscriber_kind = fields.Function(
        fields.Selection(offered.SUBSCRIBER_KIND, 'Product Subscriber Kind'),
        'get_product_subscriber_kind')
    termination_reason = fields.Function(
        fields.Many2One('contract.sub_status', 'Termination Reason',
            domain=[('status', '=', 'terminated')]),
        'getter_activation_history')
    subscriber_kind = fields.Function(
        fields.Selection(
            [x for x in offered.SUBSCRIBER_KIND if x != ('all', 'All')],
            'Subscriber Kind',
            states={
                'readonly': Eval('product_subscriber_kind') != 'all',
                'invisible': Eval('status') != 'quote',
                },
            depends=['status', 'product_subscriber_kind']),
        'on_change_with_subscriber_kind', 'setter_void')
    contacts = fields.One2Many('contract.contact', 'contract', 'Contacts',
        states=_STATES, depends=_DEPENDS, delete_missing=True)
    last_modification = fields.Function(fields.DateTime('Last Modification'),
        'get_last_modification')
    icon = fields.Function(fields.Char('Icon'), 'get_icon')
    color = fields.Function(fields.Char('Color'), 'get_color')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.rec_name.string = 'Number'
        cls.__rpc__.update({'ws_subscribe_contracts': RPC(readonly=False)})
        cls._buttons.update({
                'option_subscription': {},
                'button_change_start_date': {
                    'invisible': Eval('status') != 'quote'},
                'button_activate': {
                    'invisible': And(
                        Eval('status') != 'quote',
                        Eval('status') != 'hold'
                        )},
                'button_calculate': {
                    'invisible': True,
                    },
                'button_decline': {
                    'invisible': Eval('status') != 'quote'},
                'button_hold': {
                    'invisible': Eval('status') != 'active'},
                'button_reactivate': {
                    'invisible': Eval('status') != 'terminated'},
                'button_stop': {
                    'invisible': And(
                        Eval('status') != 'active',
                        Eval('status') != 'hold',
                        Eval('status') != 'quote',
                        )},
                })
        cls._error_messages.update({
                'inactive_product_at_date':
                'Product %s is inactive at date %s',
                'activation_period_overlaps': 'Activation Periods "%(first)s"'
                ' and "%(second)s" overlap.',
                'no_quote_sequence': 'No quote sequence defined',
                'start_date_multiple_activation_history': 'Cannot change '
                'start date, multiple activation period detected',
                'end_date_anterior_to_start_date': 'Cannot set end date '
                'anterior to start date',
                'missing_values': 'Cannot add functional key : both quote'
                'number and contract_number are missing from values',
                'invalid_format': 'Invalid file format',
                'cannot_reactivate_end_reached': 'Cannot reactivate contract, '
                'end reached',
                'cannot_reactivate_max_end_date': 'Cannot reactivate contract,'
                ' max end date reached',
                'cannot_reactivate_non_terminated': 'Cannot reactivate a not '
                'yet terminated contract',
                })
        cls._order.insert(0, ('last_modification', 'DESC'))

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.4 Drop contract.address
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        if TableHandler.table_exist(cursor, 'contract_address'):
            TableHandler.drop_table(cursor, 'contract.address',
                'contract_address')
        super(Contract, cls).__register__(module_name)

    @classmethod
    def view_attributes(cls):
        return super(Contract, cls).view_attributes() + [(
                '//group[@id="subscriber"]/group[@id="person"]',
                'states',
                {'invisible': Eval('subscriber_kind') != 'person'}
                ), (
                '//group[@id="subscriber"]/group[@id="company"]',
                'states',
                {'invisible': Eval('subscriber_kind') == 'person'}
                ), (
                '/form/notebook/page[@id="options"]',
                'states',
                {'invisible': ~Eval('options')}
                ), (
                '/form/group[@id="button_change_start_date"]',
                'states',
                {'invisible': True}
                ), (
                '/tree', 'colors', Eval('color', 'black')
                )]

    def get_color(self, name):
        if self.status in ['void', 'terminated']:
            return 'grey'
        return 'black'

    @staticmethod
    def order_last_modification(tables):
        table, _ = tables[None]
        return [Coalesce(table.write_date, table.create_date)]

    def get_func_key(self, name):
        return '%s|%s' % ((self.quote_number, self.contract_number))

    def get_initial_start_date(self, name):
        pool = Pool()
        History = pool.get('contract.activation_history')
        all_periods = History.search([('active', 'in', [True, False]),
                ('contract', '=', self.id)])
        all_periods.sort(key=lambda x: x.start_date)
        if all_periods:
            return all_periods[0].start_date

    def related_attachments_resources(self):
        return [str(self)]

    @classmethod
    def copy(cls, contracts, default=None):
        default = {} if default is None else default.copy()
        if not Transaction().context.get('copy_mode', None):
            # The Functional mode is by default through the UI, but could
            # be overriden through code
            skips = cls._export_skips() | cls.functional_skips_for_duplicate()
            for x in skips:
                default.setdefault(x, None)
            default.setdefault('status', cls.default_status())
            with Transaction().set_context(copy_mode='functional'):
                return super(Contract, cls).copy(contracts, default=default)
        return super(Contract, cls).copy(contracts, default=default)

    @classmethod
    def functional_skips_for_duplicate(cls):
        return set(['quote_number', 'contract_number', 'sub_status',
            'start_date', 'end_date'])

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                quote_number, contract_number = operands
                res = []
                if quote_number != 'None':
                    res.append(('quote_number', clause[1], quote_number))
                if contract_number != 'None':
                    res.append(('contract_number', clause[1], contract_number))
                return res
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('quote_number',) + tuple(clause[1:])],
                [('contract_number',) + tuple(clause[1:])],
                ]

    def get_date_used_for_contract_end_date(self):
        # This method should be overriden for example if there is a renewal
        # or a given date
        # by default a contract has no end date
        return None

    def calculate_activation_dates(self):
        if self.status == 'void':
            return
        dates = [self.get_date_used_for_contract_end_date()]
        dates.append(self.get_maximum_end_date())
        dates = [x for x in dates if x] or [None]
        self.end_date = min(dates)

    def notify_end_date_change(self, value):
        for option in self.options:
            option.notify_contract_end_date_change(value)
        self.options = self.options

    def notify_start_date_change(self, value):
        for option in self.options:
            option.notify_contract_start_date_change(value)
        self.options = self.options

    @classmethod
    def _calculate_methods(cls, product):
        return [('options', 'set_automatic_end_date'),
            ('contract', 'calculate_activation_dates'),
            ]

    @dualmethod
    def calculate(cls, contracts):
        for contract in contracts:
            contract.do_calculate()
        cls.save(contracts)

    def do_calculate(self):
        for model_type, method_name in self._calculate_methods(self.product):
            instances = self._get_calculate_targets(model_type)
            if not instances:
                continue
            method = getattr(instances[0].__class__, method_name)
            if not hasattr(method, 'im_self') or method.im_self:
                method(instances)
            else:
                for instance in instances:
                    method(instance)

    def _get_calculate_targets(self, model_type):
        if model_type == 'contract':
            return [self]
        elif model_type == 'contract_options':
            self.options = self.options
            return list(self.options)
        return []

    @classmethod
    @model.CoopView.button
    def button_calculate(cls, contracts):
        cls.calculate(contracts)

    @classmethod
    def update_contract_after_import(cls, contracts):
        for contract in contracts:
            contract.init_options()

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Product = pool.get('offered.product')
        product_ids = [x.get('product') for x in vlist]
        products = Product.search([('id', 'in', product_ids)])
        product_dict = dict([(x.id, x) for x in products])
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if (vals.get('status', '') == 'quote'
                    and not vals.get('quote_number')):
                sequence = product_dict[
                    vals.get('product')].quote_number_sequence
                if not sequence:
                    cls.raise_user_error('no_quote_sequence')
                vals['quote_number'] = Sequence.get_id(sequence.id)
        return super(Contract, cls).create(vlist)

    def get_icon(self, name=None):
        if self.status == 'active':
            return 'contract_green'
        return 'contract'

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company', None)

    @classmethod
    def default_extra_data(cls):
        return {}

    @staticmethod
    def default_status():
        return 'quote'

    @classmethod
    def default_subscriber_kind(cls):
        return 'person'

    @classmethod
    def getter_activation_history(cls, contracts, names):
        cursor = Transaction().cursor
        pool = Pool()
        ActivationHistory = pool.get('contract.activation_history')
        activation_history = ActivationHistory.__table__()
        column_end = NullIf(Coalesce(activation_history.end_date,
                datetime.date.max), datetime.date.max).as_('end_date')
        column_start = activation_history.start_date.as_('start_date')
        column_term_reason = activation_history.termination_reason.as_(
            'termination_reason')
        contract_window = Window([activation_history.contract])

        def convert(value):
            if value:
                if not isinstance(value, datetime.date):
                    return datetime.date(*map(int, value.split('-')))
                return value
            return value

        base_values = {x.id: None for x in contracts}
        values = {
            'start_date': base_values,
            'end_date': dict(base_values),
            'termination_reason': dict(base_values),
            }

        today = utils.today()
        max_date = datetime.date.max
        for contract_slice in grouped_slice(contracts):
            win_query = activation_history.select(
                activation_history.contract.as_('id'),
                column_start, column_end, column_term_reason, Min(
                    activation_history.start_date,
                    window=contract_window).as_('min_start'),
                Max(activation_history.start_date,
                    window=contract_window).as_('max_start'),
                where=(activation_history.contract.in_(
                    [x.id for x in contract_slice]) &
                    (activation_history.active == Literal(True))))
            query = win_query.select(win_query.id,
                win_query.start_date,
                win_query.end_date,
                win_query.termination_reason,
                where=(
                    # case 1: today is inside a period
                    ((win_query.start_date <= today) &
                        (Coalesce(win_query.end_date, max_date) >= today))
                    # case 2: today is after last period
                    | ((win_query.start_date <= today) &
                        (win_query.start_date == win_query.max_start))
                    # case 3: today is before first period
                    | ((win_query.start_date > today) &
                        (win_query.start_date == win_query.min_start))
                    ))

            cursor.execute(*query)

            for elem in cursor.dictfetchall():
                values['start_date'][elem['id']] = elem['start_date']
                values['end_date'][elem['id']] = elem['end_date']
                values['termination_reason'][elem['id']] = elem[
                    'termination_reason']

        if backend.name() == 'sqlite':
            for fname in ('start_date', 'end_date'):
                values[fname] = {x: convert(y)
                    for x, y in values[fname].iteritems()}
        return values

    @fields.depends('product', 'options', 'start_date', 'extra_datas',
        'appliable_conditions_date')
    def on_change_product(self):
        pool = Pool()
        ExtraData = pool.get('contract.extra_data')
        if self.product is None:
            self.subscriber_kind = 'person'
            self.extra_data_values = {}
            self.options = []
            self.options = self.options
            self.extra_datas = []
            self.extra_datas = self.extra_datas
            return

        options = list(self.options)
        available_coverages = self.get_coverages(self.product)
        if options:
            for elem in options:
                if elem.coverage not in available_coverages:
                    options.remove(elem)
                else:
                    available_coverages.remove(elem.coverage)
        Option = Pool().get('contract.option')
        for elem in available_coverages:
            if elem.subscription_behaviour == 'optional':
                continue
            options.append(Option.new_option_from_coverage(elem,
                    self.product, start_date=self.start_date))
        self.options = options
        extra_vals = {}
        if self.extra_datas:
            extra_vals = self.extra_datas[0].extra_data_values
        extra_data_value = self.product.get_extra_data_def(
                'contract', extra_vals, self.appliable_conditions_date)
        self.subscriber_kind = ('person' if self.product.subscriber_kind in
            ['all', 'person'] else 'company')
        extra_datas = []
        extra_datas.append(ExtraData(date=None,
                extra_data_values=extra_data_value))
        self.extra_datas = extra_datas
        self.extra_data_values = extra_data_value
        self.extra_data_values = self.extra_data_values
        self.product_subscriber_kind = self.product.subscriber_kind

    @fields.depends('extra_datas', 'start_date', 'options', 'product',
        'appliable_conditions_date')
    def on_change_extra_datas(self):
        pool = Pool()
        ExtraData = pool.get('contract.extra_data')

        if not self.product:
            self.extra_datas = []
            return

        if not self.extra_datas:
            self.extra_datas = [
                ExtraData(extra_data_values={}, date=None)]
        else:
            self.extra_datas = self.extra_datas

        data_values = self.product.get_extra_data_def('contract',
            self.extra_datas[-1].extra_data_values,
            self.appliable_conditions_date)

        self.extra_datas[-1].extra_data_values = data_values
        self.extra_data_values = data_values

    @fields.depends('start_date')
    def on_change_start_date(self):
        self.appliable_conditions_date = self.start_date

    @fields.depends('subscriber')
    def on_change_with_current_policy_owner(self, name=None):
        policy_owner = self.get_policy_owner(utils.today())
        return policy_owner.id if policy_owner else None

    @fields.depends('product')
    def on_change_with_subscriber_kind(self, name=None):
        if getattr(self, 'subscriber', None):
            if self.subscriber.is_person:
                return 'person'
            elif self.subscriber.is_company:
                return 'company'
        if not self.product:
            return 'person'
        if self.product.subscriber_kind in ['all', 'person']:
            return 'person'
        else:
            return self.product.subscriber_kind

    @classmethod
    def setter_start_date(cls, contracts, name, value):
        pool = Pool()
        ActivationHistory = pool.get('contract.activation_history')

        for contract_slice in grouped_slice(contracts):
            to_save = []
            for contract in contract_slice:
                to_save.append(contract)
                contract.notify_start_date_change(value)
                if not contract.activation_history:
                    contract.activation_history = [ActivationHistory(
                            contract=contract, start_date=value)]
                elif len(contract.activation_history) > 1:
                    cls.raise_user_error(
                        'start_date_multiple_activation_history')
                else:
                    existing = contract.activation_history[0]
                    if existing.start_date != value:
                        if existing.end_date and existing.end_date < value:
                            existing.end_date = None
                        existing.start_date = value
                        contract.activation_history = [existing]
            cls.save(to_save)

    @classmethod
    def setter_end_date(cls, contracts, name, value):
        pool = Pool()
        ActivationHistory = pool.get('contract.activation_history')
        for contract_slice in grouped_slice(contracts):
            to_save = []
            for contract in contract_slice:
                to_save.append(contract)
                if contract.status == 'void':
                    continue
                contract.notify_end_date_change(value)
                existing = contract.activation_history
                if not existing:
                    contract.activation_history = [ActivationHistory(
                            contract=contract, end_date=value)]
                else:
                    good_activation_history = [x for x in existing
                        if x.start_date <= (value or datetime.date.max)]
                    if not good_activation_history:
                        cls.raise_user_error(
                            'end_date_anterior_to_start_date')
                    if good_activation_history[-1].end_date != value:
                        good_activation_history[-1].end_date = value
                        contract.activation_history = good_activation_history
            cls.save(to_save)

    @classmethod
    def search_contract_date(cls, name, clause):
        pool = Pool()
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        ActivationHistory = pool.get('contract.activation_history')
        activation_history = ActivationHistory.__table__()

        if name == 'end_date':
            column = NullIf(Max(Coalesce(
                        activation_history.end_date, datetime.date.max)),
                datetime.date.max)
        elif name == 'start_date':
            column = Max(activation_history.start_date)

        query = activation_history.select(activation_history.contract,
            having=Operator(column, value),
            group_by=activation_history.contract,
            where=activation_history.active != Literal(False))

        return [('id', 'in', query)]

    @classmethod
    def search_parties(cls, name, clause):
        return [('subscriber.id',) + tuple(clause[1:])]

    @classmethod
    def validate(cls, contracts):
        super(Contract, cls).validate(contracts)
        for contract in contracts:
            contract.check_activation_dates()
        cls.check_option_end_dates(contracts)

    @classmethod
    def check_option_end_dates(cls, contracts):
        Pool().get('contract.option').check_end_date([option
                for contract in contracts
                for option in contract.options])

    def on_change_with_is_sub_status_required(self, name=None):
        return self.status in _STATUSES_WITH_SUBSTATUS

    @classmethod
    def get_revision_value(cls, contracts, names, ContractRevision):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Transaction().context.get('contract_revision_date',
            Date.today())
        return ContractRevision.get_values(contracts, names=names, date=date)

    def get_default_contacts(self, type_, at_date):
        '''
            This methods calculate defaults contacts
        '''
        pool = Pool()
        Contact = pool.get('contract.contact')
        ContactType = pool.get('contract.contact.type')
        if not self.subscriber:
            return []
        subscriber_type, = ContactType.search([('code', '=', 'subscriber')])
        return [Contact(
                type=subscriber_type,
                party=self.subscriber,
                address=utils.get_good_version_at_date(self.subscriber,
                    'addresses', at_date))]

    def get_contacts_of_type_at_date(self, type_, date=None):
        if not date:
            date = utils.today()
        contacts = [c for c in self.contacts
            if (c.type.code == type_ and (not date or (
                        date >= (c.date or datetime.date.min) and
                        date <= (c.end_date or datetime.date.max))))]
        if not contacts:
            contacts = self.get_default_contacts(type_, date)
        return contacts

    def check_activation_dates(self):
        previous_period = None
        for period in self.activation_history:
            if not previous_period:
                previous_period = period
                continue
            if not previous_period.end_date or (
                    period.start_date <= previous_period.end_date):
                self.raise_user_error('activation_period_overlaps', {
                        'first': period.rec_name,
                        'second': previous_period.rec_name,
                        })
            previous_period = period

    def get_maximum_end_date(self):
        dates = []
        for option in self.options:
            possible_end_dates = option.get_possible_end_date()
            if possible_end_dates:
                dates.append(max(possible_end_dates.values()))
            else:
                return None
        if dates:
            return max(dates)
        return None

    def set_appliable_conditions_date(self, new_date):
        self.appliable_conditions_date = new_date

    def get_rec_name(self, name):
        if self.status in ['quote', 'declined']:
            return self.quote_number
        else:
            return self.contract_number

    def get_synthesis_rec_name(self, name):
        Date = Pool().get('ir.date')
        dates = '[%s - %s]' % (
            Date.date_as_string(self.start_date) if self.start_date else '',
            Date.date_as_string(self.end_date) if self.end_date else '')
        product = '[%s]' % self.product.rec_name
        status = '[%s]' % coop_string.translate_value(self, 'status')
        number = self.contract_number or self.quote_number
        if self.status in ['void', 'declined']:
            return '%s %s %s' % (number, product, status)
        else:
            return '%s %s %s %s' % (number, product, status, dates)

    @classmethod
    def get_extra_data(cls, contracts, names):
        ContractExtraData = Pool().get('contract.extra_data')
        result = cls.get_revision_value(contracts, names,
            ContractExtraData)
        # Dict fields must be cast
        for k, v in result.get('extra_data_values', {}).iteritems():
            result['extra_data_values'][k] = json.loads(v or '{}',
                object_hook=JSONDecoder())
        return result

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR', [
                ('contract_number',) + tuple(clause[1:]),
                ('status', '!=', 'quote'),
                ], [
                ('quote_number',) + tuple(clause[1:]),
                ('status', 'in', ['quote', 'declined']),
                ],
            ]

    def init_contract(self, product, party, contract_dict=None):
        self.subscriber = party
        at_date = contract_dict.get('start_date', utils.today())
        self.init_from_product(product, at_date)
        self.on_change_extra_data()

    def before_activate(self):
        self.calculate()

    @classmethod
    def subscribe_contract(cls, product, party, contract_dict=None):
        'WIP : This method should be the basic API to have a contract.'
        pool = Pool()
        Contract = pool.get('contract')
        SubscribedOpt = pool.get('contract.option')
        at_date = contract_dict.get('start_date', utils.today())
        contract = Contract()
        contract.init_contract(product, party, contract_dict)
        contract.options = []
        for coverage in [x.coverage for x in product.ordered_coverages
                if x.coverage.is_service]:
            contract.options.append(SubscribedOpt.new_option_from_coverage(
                    coverage, product, at_date))
        contract.activate_contract()
        return contract

    @classmethod
    def _export_light(cls):
        return (super(Contract, cls)._export_light() |
            set(['product', 'company']))

    @classmethod
    def _export_skips(cls):
        return (super(Contract, cls)._export_skips() |
            set(['logs']))

    @classmethod
    def ws_subscribe_contracts(cls, contract_dict):
        'This method is a standard API for webservice use'
        return_values = {}
        for ext_id, objects in contract_dict.iteritems():
            new_message = []
            return_values[ext_id] = {'return': True, 'messages': new_message}
            try:
                for item in objects:
                    new_message += cls._ws_import_entity(item)
            except UserError as exc:
                Transaction().cursor.rollback()
                new_message.append({'error': exc.message})
                return {ext_id: {
                        'return': False,
                        'messages': new_message,
                        }}
        return return_values

    @classmethod
    def _ws_import_entity(cls, item):
        pool = Pool()
        Party = pool.get('party.party')
        return_values = []
        if item['__name__'] == 'party.party':
            entity = Party.import_json(item)
            return_values.append({
                    'party_code': entity.code
                    })
        elif item['__name__'] == 'contract':
            contract = cls.import_json(item)
            return_values.append({
                    'contract_number': contract.contract_number,
                    'quote_number': contract.quote_number,
                    'status': contract.status
                    })
            cls.update_contract_after_import([contract])
            contract.save()
            contract.calculate()
        else:
            cls.raise_user_error('invalid_format')
        return return_values

    def init_from_product(self, product, start_date=None, end_date=None):
        if not start_date:
            start_date = utils.today()
        if utils.is_effective_at_date(product, start_date):
            self.product = product
            start_date = (
                max(product.start_date, start_date)
                if start_date else product.start_date)
            end_date = (
                min(product.end_date, end_date)
                if end_date else product.end_date)
            if end_date:
                self.activation_history[0].end_date = coop_date.add_day(
                    end_date, -1)
            self.start_date, self.end_date = start_date, end_date
            self.status = 'quote'
            self.company = product.company
            self.init_extra_data()
        else:
            self.raise_user_error('inactive_product_at_date',
                (product.name, start_date))
        self.appliable_conditions_date = self.start_date

    def init_extra_data(self):
        if not (hasattr(self, 'extra_datas') and
                self.extra_datas):
            self.extra_datas = []
            self.extra_datas = self.extra_datas
        self.on_change_extra_datas()

    def get_extra_data_def(self):
        extra_data_defs = []
        if self.product:
            extra_data_defs.extend(self.product.get_extra_data_def(
                ['contract'], at_date=self.start_date))
        for option in self.options:
            extra_data_defs.extend(
                option.product.get_extra_data_def(['contract'],
                    at_date=option.start_date))
        return set(extra_data_defs)

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['contract'] = self
        cur_dict['appliable_conditions_date'] = self.appliable_conditions_date
        self.product.init_dict_for_rule_engine(cur_dict)
        cur_dict['subscriber'] = self.get_policy_owner()

    def get_new_contract_number(self):
        return self.product.get_result(
            'new_contract_number', {
                'appliable_conditions_date': self.appliable_conditions_date,
                'date': self.start_date,
                })[0]

    def after_activate(self):
        if not getattr(self, 'contract_number', None):
            self.contract_number = self.get_new_contract_number()
        # if contract was hold remove sub status reason
        self.sub_status = None
        self.save()

    def get_policy_owner(self, at_date=None):
        '''
        the owner of a contract could change over time, you should never use
        the direct link subscriber
        '''
        # TODO: to enhance
        if getattr(self, 'subscriber', None):
            return self.subscriber

    def activate_contract(self):
        pool = Pool()
        Event = pool.get('event')
        if not self.status or self.status == 'quote':
            event = 'activate_contract'
        elif self.status == 'hold':
            # when activating after suspend
            event = 'unhold_contract'
        else:
            event = 'reactivate_contract'
        self.before_activate()
        self.do_activate()
        self.after_activate()
        Event.notify_events([self], event)

    def do_activate(self):
        self.status = 'active'
        options = list(self.options)
        for option in options:
            option.status = 'active'
        self.options = options

    def decline_contract(self, reason):
        pool = Pool()
        Event = pool.get('event')
        self.status = 'declined'
        self.sub_status = reason
        self.save()
        Event.notify_events([self], 'decline_contract',
            description=reason.name)

    def clean_up_versions(self):
        pool = Pool()
        ActivationHistory = pool.get('contract.activation_history')
        ExtraData = pool.get('contract.extra_data')
        Option = pool.get('contract.option')

        if self.activation_history:
            activation_period_to_del = [x for x in self.activation_history[1:]]
            self.activation_history = [self.activation_history[0]]
            self.activation_history[0].start_date = self.start_date
            self.activation_history[0].end_date = None
            if activation_period_to_del:
                ActivationHistory.delete(activation_period_to_del)

        if self.extra_datas:
            extra_data_to_del = [x for x in self.extra_datas[:-1]]
            self.extra_datas = [self.extra_datas[-1]]
            self.extra_datas[0].date = None
            if extra_data_to_del:
                ExtraData.delete(extra_data_to_del)

        if self.options:
            to_write = []
            for option in self.options:
                option.clean_up_versions(self)
                to_write += [[option], option._save_values]
            if to_write:
                Option.write(*to_write)

    @classmethod
    def revert_to_project(cls, contracts):
        to_write = []
        for contract in contracts:
            contract.clean_up_versions()
            contract.status = 'quote'
            to_write += [[contract], contract._save_values]
        cls.write(*to_write)

    @classmethod
    def do_terminate(cls, contracts):
        if not contracts:
            return
        pool = Pool()
        Event = pool.get('event')
        sub_status_contracts = defaultdict(list)
        for contract in contracts:
            sub_status_contracts[contract.activation_history[-1].
                termination_reason].append(contract)
        to_write = []
        for sub_status, contracts in sub_status_contracts.iteritems():
            to_write += [contracts, {
                    'status': 'terminated',
                    'sub_status': sub_status,
                    }]
        cls.write(*to_write)
        Event.notify_events(contracts, 'terminate_contract')

    @classmethod
    def plan_termination_or_terminate(cls, contracts, caller=None):
        pool = Pool()
        Event = pool.get('event')
        to_terminate_now = [c for c in contracts if c.end_date < utils.today()]
        to_terminate_later = [c for c in contracts if
            c.end_date >= utils.today()]
        cls.do_terminate(to_terminate_now)
        # generate event only if termination is not processed
        Event.notify_events(to_terminate_later, 'plan_contract_termination')

    @classmethod
    def terminate(cls, contracts, at_date, termination_reason):
        if not contracts:
            return
        for contract in contracts:
            contract.end_date = at_date
            contract.activation_history[-1].termination_reason = \
                termination_reason
            contract.activation_history = list(contract.activation_history)
            contract.save()
        cls.plan_termination_or_terminate(contracts)

    @classmethod
    def void(cls, contracts, void_reason):
        pool = Pool()
        Event = pool.get('event')
        History = pool.get('contract.activation_history')
        cls.write(contracts, {
                'status': 'void',
                'sub_status': void_reason,
                })
        History.write(History.search([('contract', 'in',
                        [x.id for x in contracts])]), {'active': False})
        Event.notify_events(contracts, 'void_contract')

    @classmethod
    def hold(cls, contracts, hold_reason):
        pool = Pool()
        Event = pool.get('event')
        cls.write(contracts, {
                'status': 'hold',
                'sub_status': hold_reason,
                })
        Event.notify_events(contracts, 'hold_contract',
            '%s (%s)' % (hold_reason.name, hold_reason.code))

    @classmethod
    def clean_before_reactivate(cls, contracts):
        for contract in contracts:
            if contract.activation_history:
                contract.activation_history[-1].clean_before_reactivate()
                contract.activation_history = contract.activation_history
        for contract in contracts:
            contract.sub_status = None
            contract.status = 'active'

    @classmethod
    def reactivate(cls, contracts):
        cls.clean_before_reactivate(contracts)
        cls.save(contracts)
        for contract in contracts:
            contract.activate_contract()

    @classmethod
    def get_coverages(cls, product):
        return [x.coverage for x in product.ordered_coverages]

    def init_options(self):
        existing = dict(((x.coverage, x) for x in getattr(
                    self, 'options', [])))
        good_options = []
        OptionModel = Pool().get('contract.option')
        for coverage in self.get_coverages(self.product):
            good_opt = None
            if coverage in existing:
                good_opt = existing[coverage.code]
            elif coverage.subscription_behaviour == 'mandatory':
                good_opt = OptionModel.new_option_from_coverage(coverage,
                    self.product, self.start_date)
            if good_opt:
                good_opt.contract = self
                good_options.append(good_opt)
        self.options = good_options

    def get_currency(self):
        if hasattr(self, 'product') and self.product:
            return self.product.currency

    @classmethod
    def get_possible_contracts_from_party(cls, party, at_date):
        if not party:
            return []
        cursor = Transaction().cursor
        pool = Pool()
        contract = pool.get('contract').__table__()
        history = pool.get('contract.activation_history').__table__()

        query_table = contract.join(history, condition=(
                (contract.id == history.contract)
                & (contract.subscriber == party.id)
                & (contract.status == 'active')
                & (history.start_date <= at_date)
                & (
                    (history.end_date == Null)
                    | (history.end_date >= at_date))
                ))
        company_id = Transaction().context.get('company', None)
        cursor.execute(*query_table.select(contract.id,
                where=(contract.company == company_id) if company_id else
                None))
        return cls.browse([x['id'] for x in cursor.dictfetchall()])

    def get_contract_address(self, at_date=None, role='subscriber'):
        contacts = self.get_contacts_of_type_at_date(role, at_date)
        if contacts:
            assert len(contacts) == 1
            if contacts[0].address:
                return contacts[0].address
        return utils.get_good_version_at_date(self.subscriber, 'addresses',
            at_date)

    def get_appliable_logo(self, kind=''):
        if self.company:
            if self.company.party.logo:
                return self.company.party.logo
        return ''

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['subscriber', ('product', 'light'), 'extra_data_values',
            'options', 'start_date', 'end_date']

    def get_publishing_context(self, cur_context):
        Lang = Pool().get('ir.lang')
        result = super(Contract, self).get_publishing_context(cur_context)
        result['Subscriber'] = self.subscriber
        result['Product'] = self.product
        result['Contract'] = self
        result['Company'] = self.company
        result['Currency'] = self.currency

        def format_currency(value):
            return Lang.currency(Lang.search([
                        ('code', '=', cur_context['Lang'])])[0], value,
                self.currency, grouping=True, symbol=True)

        result['FAmount'] = format_currency
        return result

    def get_publishing_values(self):
        result = super(Contract, self).get_publishing_values()
        result['number'] = self.contract_number
        result['start_date'] = self.start_date
        result['end_date'] = self.end_date
        return result

    @classmethod
    @model.CoopView.button_action('contract.option_subscription_wizard')
    def option_subscription(cls, contracts):
        pass

    @classmethod
    @model.CoopView.button_action('contract.act_change_start_date')
    def button_change_start_date(cls, contracts):
        pass

    @classmethod
    @model.CoopView.button_action('contract.act_activate')
    def button_activate(cls, contracts):
        pass

    @classmethod
    @model.CoopView.button_action('contract.act_decline')
    def button_decline(cls, contracts):
        pass

    @classmethod
    @model.CoopView.button_action('contract.act_stop')
    def button_stop(cls, contracts):
        pass

    @classmethod
    @model.CoopView.button_action('contract.act_hold_contract')
    def button_hold(cls, contracts):
        pass

    @classmethod
    @model.CoopView.button_action('contract.act_reactivate')
    def button_reactivate(cls, contracts):
        pass

    def get_all_extra_data(self, at_date):
        res = self.product.get_all_extra_data(at_date)
        if not at_date:
            return res
        extra_data = utils.get_value_at_date(self.extra_datas, at_date)
        good_extra_data = extra_data.extra_data_values if extra_data else {}
        res.update(good_extra_data)
        return res

    def get_product_subscriber_kind(self, name):
        return self.product.subscriber_kind if self.product else ''

    def get_last_modification(self, name):
        return (self.write_date if self.write_date else self.create_date
            ).replace(microsecond=0)

    def get_parties(self, name):
        return [self.subscriber.id] if self.subscriber else []

    @fields.depends('subscriber_kind', 'subscriber')
    def on_change_subscriber_kind(self):
        if self.subscriber and (self.subscriber_kind == 'person'
                and not self.subscriber.is_person
                or self.subscriber_kind == 'company'
                and not self.subscriber.is_company):
            self.subscriber = None

    @classmethod
    def add_func_key(cls, values):
        if 'quote_number' in values and 'contract_number' in values:
            values['_func_key'] = '%s|%s' % (values['quote_number'],
                values['contract_number'])
        elif 'quote_number' not in values and 'contract_number' in values:
            values['_func_key'] = 'None|%s' % values['contract_number']
        elif 'quote_number' in values and 'contract_number' not in values:
            values['_func_key'] = '%s|None' % values['quote_number']
        else:
            values['_func_key'] = 'None'  # We are creating a new contract

    def get_reactivation_end_date(self):
        if self.status != 'terminated':
            self.append_functional_error('cannot_reactivate_non_terminated')
            return None
        if self.sub_status.code == 'reached_end_date':
            self.append_functional_error('cannot_reactivate_end_reached')
            return None
        # Get new end_date
        with Transaction().new_cursor() as transaction:
            try:
                contract = self.__class__(self.id)
                previous_end_date = contract.end_date
                contract.end_date = None
                contract.save()
                dates = [contract.get_date_used_for_contract_end_date()]
                dates.append(contract.get_maximum_end_date())
                new_end_date = min([x for x in dates if x] or [None])
            finally:
                transaction.cursor.rollback()
        if new_end_date is not None and new_end_date <= previous_end_date:
            self.append_functional_error('cannot_reactivate_max_end_date')
            return None
        return new_end_date


class ContractOption(model.CoopSQL, model.CoopView, model.ExpandTreeMixin,
        ModelCurrency):
    'Contract Option'

    __name__ = 'contract.option'
    _history = True
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        states={'invisible': ~Eval('contract')}, select=True)
    parent_contract = fields.Function(
        fields.Many2One('contract', 'Parent Contract'),
        'on_change_with_parent_contract', searcher='search_parent_contract')
    versions = fields.One2Many('contract.option.version', 'option', 'Versions',
        states={'readonly': Eval('contract_status') != 'quote'},
        depends=['contract_status'], delete_missing=True,
        order=[('start', 'ASC')])
    current_version = fields.Function(
        fields.Many2One('contract.option.version', 'Current Version'),
        'get_current_version')
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='RESTRICT', states={
            'required': Eval('contract_status') == 'active',
            'readonly': Eval('contract_status') != 'quote',
            },
        depends=['contract_status', 'start_date', 'end_date', 'product'])
    end_date = fields.Function(
        fields.Date('End Date', states=_CONTRACT_STATUS_STATES,
            depends=_CONTRACT_STATUS_DEPENDS),
        'get_end_date', setter='set_end_date')
    automatic_end_date = fields.Date('Automatic End Date', readonly=True)
    manual_end_date = fields.Date('Manual End Date', readonly=True)
    start_date = fields.Function(
        fields.Date('Start Date', states=_CONTRACT_STATUS_STATES,
            depends=_CONTRACT_STATUS_DEPENDS),
        'get_start_date', searcher="searcher_start_date")
    manual_start_date = fields.Date('Manual Start Date',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    status = fields.Selection(OPTIONSTATUS, 'Status',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    status_string = status.translated('status')
    sub_status = fields.Many2One('contract.sub_status',
        'Sub Status', states={'required': Bool(Eval('manual_end_date')),
            'readonly': Eval('contract_status') != 'quote',
            'invisible': ~Eval('sub_status')},
        depends=['manual_end_date', 'contract_status'],
        ondelete='RESTRICT')
    appliable_conditions_date = fields.Function(
        fields.Date('Appliable Conditions Date'),
        'on_change_with_appliable_conditions_date')
    contract_number = fields.Function(
        fields.Char('Contract Number'),
        'on_change_with_contract_number')
    coverage_family = fields.Function(
        fields.Char('Coverage Family'),
        'on_change_with_coverage_family')
    current_policy_owner = fields.Function(
        fields.Many2One('party.party', 'Current Policy Owner'),
        'on_change_with_current_policy_owner')
    product = fields.Function(
        fields.Many2One('offered.product', 'Product'),
        'on_change_with_product')
    contract_status = fields.Function(
        fields.Char('Contract Status'),
        'on_change_with_contract_status')
    full_name = fields.Function(
        fields.Char('Full Name'), 'get_full_name')
    initial_start_date = fields.Function(fields.Date('Initial Start Date'),
        'get_initial_start_date')
    current_extra_data = fields.Function(
        fields.Dict('extra_data', 'Current Extra Data', states={
                'readonly': Eval('contract_status') != 'quote',
                'invisible': ~Eval('current_extra_data')},
            depends=['current_extra_data', 'contract_status']),
        'get_current_version', setter='setter_void')
    current_extra_data_string = current_extra_data.translated(
        'current_extra_data')

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._error_messages.update({
                'inactive_coverage_at_date':
                'Coverage %s is inactive at date %s',
                'end_date_none': 'No end date defined',
                'end_date_anterior_to_start_date': 'End date should be '
                'posterior to start date: %s',
                'end_date_posterior_to_contract': 'End date should be '
                'anterior to end date of contract: %s',
                'end_date_posterior_to_automatic_end_date': 'End date should '
                'be anterior to option automatic end date : %s',
                })

    @classmethod
    def functional_skips_for_duplicate(cls):
        return set(['automatic_end_date'])

    @classmethod
    def _export_light(cls):
        return (super(ContractOption, cls)._export_light() |
            set(['coverage', 'product']))

    @classmethod
    def copy(cls, options, default=None):
        default = {} if default is None else default.copy()
        if Transaction().context.get('copy_mode', '') == 'functional':
            skips = cls._export_skips() | cls.functional_skips_for_duplicate()
            for x in skips:
                default.setdefault(x, None)
        return super(ContractOption, cls).copy(options, default=default)

    @classmethod
    def default_product(cls):
        return Transaction().context.get('product', None)

    @staticmethod
    def default_start_date():
        return utils.today()

    @classmethod
    def default_status(cls):
        return 'active'

    @classmethod
    def default_versions(cls):
        return [Pool().get('contract.option.version').get_default_version()]

    @fields.depends('appliable_conditions_date', 'coverage', 'coverage_family',
        'current_extra_data', 'product', 'start_date', 'versions')
    def on_change_coverage(self):
        self.coverage_family = self.on_change_with_coverage_family()
        current_version = self.update_current_version()
        self.current_extra_data = current_version.extra_data

    @fields.depends('current_extra_data', 'versions')
    def on_change_current_extra_data(self):
        current_version = self.get_version_at_date(utils.today())
        if not current_version:
            return
        current_version.extra_data = self.current_extra_data
        current_version.extra_data_as_string = \
            current_version.on_change_with_extra_data_as_string()
        self.versions = list(self.versions)

    @fields.depends('sub_status', 'manual_end_date')
    def on_change_with_sub_status(self, name=None):
        pool = Pool()
        SubStatus = pool.get('contract.sub_status')
        if not self.manual_end_date:
            return
        if not self.sub_status:
            return SubStatus.search([('xml_id', '=',
                        'contract.sub_status_terminated')])[0]
        return self.sub_status

    @fields.depends('contract', 'start_date')
    def on_change_with_appliable_conditions_date(self, name=None):
        start_date = Transaction().context.get('start_date', None)
        if start_date:
            return start_date
        if self.contract:
            return self.contract.appliable_conditions_date
        if self.start_date:
            return self.start_date

    @fields.depends('contract')
    def on_change_with_contract_number(self, name=None):
        return self.contract.contract_number if self.contract else ''

    @fields.depends('coverage')
    def on_change_with_coverage_family(self, name=None):
        return self.coverage.family if self.coverage else ''

    @fields.depends('contract')
    def on_change_with_current_policy_owner(self, name=None):
        if self.contract:
            return self.contract.current_policy_owner

    @fields.depends('contract')
    def on_change_with_product(self, name=None):
        product = Transaction().context.get('product', None)
        if product:
            return product
        if self.contract and self.contract.product:
            return self.contract.product.id

    @fields.depends('contract')
    def on_change_with_contract_status(self, name=None):
        return self.contract.status if self.contract else ''

    @fields.depends('contract')
    def on_change_with_parent_contract(self, name=None):
        if self.contract:
            return self.contract.id

    @classmethod
    def get_current_version(cls, options, names):
        field_map = cls.get_field_map()
        return utils.version_getter(options, names, 'contract.option.version',
            'option', utils.today(), field_map=field_map)

    @classmethod
    def get_field_map(cls):
        return {'id': 'current_version', 'extra_data': 'current_extra_data'}

    @classmethod
    def get_start_date(cls, options, names):
        values = {'start_date': {x.id: None for x in options}}
        for option in options:
            if option.status == 'void':
                continue
            ended_previously = False
            if option.manual_end_date or option.automatic_end_date:
                ending_date = min(option.manual_end_date or datetime.date.max,
                    option.automatic_end_date or datetime.date.max)
                if ending_date < (option.parent_contract.start_date or
                        datetime.date.min):
                    ended_previously = True
                    values['start_date'][option.id] = option.initial_start_date
            if not ended_previously:
                if option.parent_contract.start_date:
                    values['start_date'][option.id] = max(
                        option.manual_start_date or datetime.date.min,
                        option.parent_contract.start_date)
                else:
                    values['start_date'][option.id] = None
        return values

    def get_end_date(self, name):
        if self.status == 'void':
            return None
        dates = [x for x in self.get_possible_end_date().itervalues()]
        if self.parent_contract.end_date:
            dates.append(self.parent_contract.end_date)
        return min(dates) if dates else None

    def get_initial_start_date(self, name):
        if self.parent_contract.initial_start_date:
            return max(self.manual_start_date or datetime.date.min,
                self.parent_contract.initial_start_date)

    def get_full_name(self, name):
        return self.rec_name

    def get_rec_name(self, name):
        if self.coverage:
            return self.coverage.get_rec_name(name)
        return super(ContractOption, self).get_rec_name(name)

    def get_currency(self):
        if hasattr(self, 'coverage') and self.coverage:
            return self.coverage.currency

    def get_func_key(self, name):
        if self.contract:
            elems = [self.contract.quote_number,
                self.contract.contract_number, self.coverage.rec_name]
            return '|'.join(str(x) for x in elems)
        else:
            return 'None|None|' + self.coverage.rec_name

    @classmethod
    def set_end_date(cls, options, name, end_date):
        cls.write(options, {'manual_end_date': end_date})

    @classmethod
    def searcher_start_date(cls, name, clause):
        return ['OR',
            [('manual_start_date',) + tuple(clause[1:])],
            [
                ('contract.start_date',) + tuple(clause[1:]),
                ('manual_start_date', '=', None)
            ]
        ]

    @classmethod
    def search_parent_contract(cls, name, clause):
        return [('contract',) + tuple(clause[1:])]

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 3:
                quote_num, contract_num, coverage = operands
                res = []
                if quote_num != 'None':
                    res.append(('contract.quote_number', clause[1], quote_num))
                if contract_num != 'None':
                    res.append(('contract.contract_number', clause[1],
                            contract_num))
                res.append(('coverage.rec_name', clause[1], coverage))
                return res
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('contract.quote_number',) + tuple(clause[1:])],
                [('contract.contract_number',) + tuple(clause[1:])],
                [('coverage.rec_name',) + tuple(clause[1:])],
                ]

    @classmethod
    def order_coverage(cls, tables):
        coverage_order = tables.get('coverage_order_tables')
        if coverage_order is not None:
            return [coverage_order[None][0].order]

        pool = Pool()
        table, _ = tables[None]
        contract = tables.get('contract')
        if contract is None:
            contract = pool.get('contract').__table__()

        relation = pool.get('offered.product-option.description').__table__()

        query_table = contract.join(relation, condition=(
                contract.product == relation.product)).select(
                contract.id.as_('contract'), relation.coverage, relation.order)
        tables['coverage_order_tables'] = {
            None: (query_table,
                (query_table.contract == table.contract) &
                (query_table.coverage == table.coverage)
                )}

        return [query_table.order]

    @classmethod
    def order_start_date(cls, tables):
        table, _ = tables[None]
        return [Coalesce(table.manual_start_date, datetime.date.min)]

    def init_dict_for_rule_engine(self, args):
        args['option'] = self
        self.coverage.init_dict_for_rule_engine(args)
        self.contract.init_dict_for_rule_engine(args)

    def get_version_at_date(self, at_date):
        for version in sorted(self.versions,
                key=lambda x: x.start or datetime.date.min, reverse=True):
            if (version.start or datetime.date.min) <= at_date:
                return version
        raise KeyError

    def notify_contract_end_date_change(self, new_end_date):
        if (new_end_date and self.manual_end_date and
                self.manual_end_date > new_end_date):
            self.manual_end_date = None

    def notify_contract_start_date_change(self, new_start_date):
        if self.automatic_end_date and \
                self.automatic_end_date < new_start_date:
            self.automatic_end_date = None

    @classmethod
    def check_end_date(cls, options):
        Date = Pool().get('ir.date')
        for option in options:
            if option.status == 'void':
                continue
            end_date = option.manual_end_date
            if not end_date or not option.start_date:
                continue
            if end_date >= option.start_date:
                if not option.parent_contract:
                    continue
                if (not option.parent_contract.end_date
                        or end_date <= option.parent_contract.end_date):
                    if (end_date and option.automatic_end_date and
                            option.automatic_end_date < end_date):
                        cls.raise_user_error(
                            'end_date_posterior_to_automatic_end_date',
                            Date.date_as_string(option.automatic_end_date),
                            )
                else:
                    cls.raise_user_error('end_date_posterior_to_contract',
                        Date.date_as_string(
                            option.parent_contract.end_date))
            else:
                cls.raise_user_error('end_date_anterior_to_start_date',
                    Date.date_as_string(option.start_date))

    def clean_up_versions(self, contract):
        pass

    @classmethod
    def get_var_names_for_full_extract(cls):
        return [('coverage', 'light'), 'start_date', 'end_date']

    @classmethod
    def new_option_from_coverage(cls, coverage, product, start_date,
            end_date=None):
        assert(start_date)
        if utils.is_effective_at_date(coverage, start_date):
            new_option = cls()
            new_option.coverage = coverage.id
            new_option.product = product.id
            new_option.status = 'active'
            new_option.start_date = start_date
            new_option.appliable_conditions_date = start_date
            Version = Pool().get('contract.option.version')
            new_option.versions = [Version(**Version.get_default_version())]
            return new_option
        else:
            cls.raise_user_error('inactive_coverage_at_date', (coverage.name,
                    start_date))

    def get_possible_end_date(self):
        dates = {}
        if self.manual_end_date:
            dates['manual_date'] = self.manual_end_date
        if self.automatic_end_date:
            # If automatic end date is prior start date, we will have a date
            # before the start date, whisch is strange but not wrong
            dates['automatic_end_date'] = self.automatic_end_date
        return dates

    def set_automatic_end_date(self):
        self.automatic_end_date = self.calculate_automatic_end_date()
        if (self.manual_end_date and self.automatic_end_date and
                self.automatic_end_date <= self.manual_end_date):
            self.manual_end_date = None

    def calculate_automatic_end_date(self):
        exec_context = {'date': self.start_date}
        self.init_dict_for_rule_engine(exec_context)
        return self.coverage.calculate_end_date(exec_context)

    def update_current_version(self):
        Version = Pool().get('contract.option.version')
        if not self.versions:
            current_version = Version(**Version.get_default_version())
            self.versions = [current_version]
        else:
            current_version = self.get_version_at_date(utils.today())
        if not current_version:
            return None
        current_version.extra_data = self.recalculate_extra_data(
            current_version.extra_data)
        self.versions = list(self.versions)
        return current_version

    def recalculate_extra_data(self, extra_data):
        if not self.coverage or not self.product:
            return {}
        return self.product.get_extra_data_def('option', extra_data.copy(),
            self.appliable_conditions_date, coverage=self.coverage)

    def get_all_extra_data(self, at_date):
        current_version = self.get_version_at_date(at_date)
        res = current_version.extra_data if current_version else {}
        if self.contract:
            res.update(self.contract.get_all_extra_data(at_date))
        return res


class ContractOptionVersion(model.CoopSQL, model.CoopView):
    'Contract Option Version'

    __name__ = 'contract.option.version'

    option = fields.Many2One('contract.option', 'Option',
        required=True, ondelete='CASCADE', select=True)
    start = fields.Date('Start')
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={
            'invisible': ~Eval('extra_data'),
            },
        depends=['extra_data'])
    extra_data_as_string = fields.Function(
        fields.Char('Extra Data as String'),
        'on_change_with_extra_data_as_string')
    extra_data_string = extra_data.translated('extra_data')
    start_date = fields.Function(
        fields.Date('Start Date'),
        'on_change_with_start_date')

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Option = pool.get('contract.option')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        option = Option.__table__()
        version = cls.__table__()

        # Migration from 1.4 : Create default contract.option.version
        to_migrate = not TableHandler.table_exist(cursor, cls._table)

        super(ContractOptionVersion, cls).__register__(module)

        if to_migrate:
            version_h = TableHandler(cursor, cls, module)
            cursor.execute(*version.insert(
                    columns=[
                        version.create_date, version.create_uid,
                        version.write_date, version.write_uid,
                        version.extra_data, version.option, version.id],
                    values=option.select(
                        option.create_date, option.create_uid,
                        option.write_date, option.write_uid,
                        Literal('{}').as_('extra_data'),
                        option.id.as_('option'), option.id.as_('id'))))
            cursor.execute(*version.select(Max(version.id)))
            cursor.setnextid(version_h.table_name,
                cursor.fetchone()[0] or 0 + 1)

    @fields.depends('option', 'start', 'start_date')
    def on_change_option(self):
        self.start = self.on_change_with_start_date()

    @fields.depends('extra_data')
    def on_change_with_extra_data_as_string(self, name=None):
        if not self.extra_data:
            return ''
        return Pool().get('extra_data').get_extra_data_summary([self],
            'extra_data')[self.id]

    @fields.depends('option', 'start')
    def on_change_with_start_date(self, name=None):
        if not self.option:
            return self.start
        return self.start or self.option.start_date

    @classmethod
    def order_start(cls, tables):
        table, _ = tables[None]
        return [Coalesce(table.start, datetime.date.min)]

    @classmethod
    def get_default_version(cls):
        return {
            'start': None,
            'extra_data': {},
            }


class ContractExtraDataRevision(model._RevisionMixin, model.CoopSQL,
        model.CoopView, export.ExportImportMixin):
    'Contract Extra Data'

    __name__ = 'contract.extra_data'
    _parent_name = 'contract'
    _func_key = 'date'

    contract = fields.Many2One('contract', 'Contract', required=True,
        select=True, ondelete='CASCADE')
    extra_data_values = fields.Dict('extra_data', 'Extra Data')
    extra_data_values_translated = extra_data_values.translated(
        'extra_data_values')
    extra_data_summary = fields.Function(
        fields.Text('Extra Data Summary'),
        'get_extra_data_summary')

    @staticmethod
    def revision_columns():
        return ['extra_data_values']

    @classmethod
    def get_reverse_field_name(cls):
        return 'extra_data'

    @classmethod
    def get_extra_data_summary(cls, extra_datas, name):
        return Pool().get('extra_data').get_extra_data_summary(extra_datas,
            'extra_data_values')

    @classmethod
    def add_func_key(cls, values):
        if 'date' in values:
            values['_func_key'] = values['date']
        else:
            values['_func_key'] = None


class ContractSelectEndDate(model.CoopView):
    'End date selector for contract'

    __name__ = 'contract.end.select_date'

    end_date = fields.Date('End date', required=True)
    termination_reason = fields.Many2One('contract.sub_status',
        'Termination Reason', domain=[('status', '=', 'terminated')],
        required=True)


class ContractEnd(Wizard):
    'End Contract wizard'

    __name__ = 'contract.end'

    start_state = 'select_date'
    select_date = StateView('contract.end.select_date',
        'contract.contract_end_select_date_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next')])
    apply = StateTransition()

    def default_select_date(self, name):
        return {'end_date': utils.today()}

    def transition_apply(self):
        pool = Pool()
        Contract = pool.get('contract')
        ActivationHistory = pool.get('contract.activation_history')
        contracts = Contract.browse(Transaction().context.get('active_ids'))
        to_write = []
        for contract in contracts:
            contract.end_date = self.select_date.end_date
            to_write.append([contract])
            to_write.append(contract._save_values)
        Contract.write(*to_write)
        activation_histories = [contract.activation_history[-1]
            for contract in contracts]
        ActivationHistory.write(activation_histories, {
                'termination_reason': self.select_date.termination_reason})
        return 'end'


class ContractSelectHoldReason(model.CoopView):
    'End date selector for contract'

    __name__ = 'contract.hold.select_hold_status'

    hold_reason = fields.Many2One('contract.sub_status',
        'Hold Reason', domain=[('status', '=', 'hold')],
        required=True)


class ContractHold(Wizard):
    'Hold Contract wizard'

    __name__ = 'contract.hold'

    start_state = 'select_hold_status'
    select_hold_status = StateView('contract.hold.select_hold_status',
        'contract.contract_select_hold_status_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next')])
    apply = StateTransition()

    def transition_apply(self):
        pool = Pool()
        Contract = pool.get('contract')
        contracts = Contract.browse(Transaction().context.get('active_ids'))
        contracts_to_hold = [contract for contract in contracts
            if contract.status == 'active']
        if contracts_to_hold:
            Contract.hold(contracts_to_hold,
                self.select_hold_status.hold_reason)
        return 'end'


class ContractSelectStartDate(model.CoopView):
    'Start date selector for contract'

    __name__ = 'contract.select_start_date'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    former_start_date = fields.Date('Former Start Date', readonly=True)
    new_start_date = fields.Date('New start date', required=True)
    former_appliable_conditions_date = fields.Date(
        'Former appliable conditions date', readonly=True)
    new_appliable_conditions_date = fields.Date(
        'New appliable conditions date', required=True)

    @fields.depends('new_start_date')
    def on_change_new_start_date(self):
        self.new_appliable_conditions_date = self.new_start_date


class ContractChangeStartDate(Wizard):
    'Change Start Date Wizard'

    __name__ = 'contract.change_start_date'

    start_state = 'change_date'
    change_date = StateView(
        'contract.select_start_date',
        'contract.select_start_date_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next', default=True),
            ])
    apply = StateTransition()

    def default_change_date(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        active_id = Transaction().context.get('active_id')
        selected_contract = Contract(active_id)
        return {
            'contract': selected_contract.id,
            'former_start_date': selected_contract.start_date,
            'former_appliable_conditions_date':
            selected_contract.appliable_conditions_date,
            }

    def transition_apply(self):
        new_date = self.change_date.new_start_date
        pool = Pool()
        Contract = pool.get('contract')
        active_id = Transaction().context.get('active_id')
        selected_contract = Contract(active_id)
        selected_contract.set_appliable_conditions_date(
                self.change_date.new_appliable_conditions_date
                )
        selected_contract.start_date = new_date
        selected_contract.save()
        return 'end'


class ContractSubStatus(model.CoopSQL, model.CoopView):
    'Contract SubStatus'

    __name__ = 'contract.sub_status'
    _func_key = 'code'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    status = fields.Selection(CONTRACTSTATUSES, 'Status', required=True)
    _get_sub_status_cache = Cache('get_sub_status')

    @classmethod
    def create(cls, vlist):
        created = super(ContractSubStatus, cls).create(vlist)
        cls._get_sub_status_cache.clear()
        return created

    @classmethod
    def delete(cls, ids):
        super(ContractSubStatus, cls).delete(ids)
        cls._get_sub_status_cache.clear()

    @classmethod
    def write(cls, *args):
        super(ContractSubStatus, cls).write(*args)
        cls._get_sub_status_cache.clear()

    @classmethod
    def __setup__(cls):
        super(ContractSubStatus, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    @classmethod
    def get_sub_status(cls, code):
        sub_status_id = cls._get_sub_status_cache.get(code, default=-1)
        if sub_status_id != -1:
            return cls(sub_status_id)
        instance = cls.search([('code', '=', code)])[0]
        cls._get_sub_status_cache.set(code, instance.id)
        return instance
