import datetime
try:
    import simplejson as json
except ImportError:
    import json
from sql.conditionals import NullIf, Coalesce
from sql.aggregate import Max, Min

from trytond import backend
from trytond.tools import grouped_slice
from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, Bool
from trytond.protocols.jsonrpc import JSONDecoder
from trytond.pool import Pool
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
_STATUSES_WITH_SUBSTATUS = ['void', 'terminated', 'declined']


__all__ = [
    'ActivationHistory',
    'Contract',
    'ContractOption',
    'ContractAddress',
    'ContractExtraDataRevision',
    'ContractSelectEndDate',
    'ContractEnd',
    'ContractSelectStartDate',
    'ContractChangeStartDate',
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
        ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date', domain=['OR',
            ('end_date', '=', None),
            ('start_date', '=', None),
            ('end_date', '>=', Eval('start_date', datetime.date.min))],
        depends=['start_date'])

    def get_func_key(self, name):
        return self.contract.quote_number

    @classmethod
    def search_func_key(cls, name, clause):
        return [('contract.quote_number',) + tuple(clause[1:])]


class Contract(model.CoopSQL, model.CoopView, ModelCurrency):
    'Contract'

    __name__ = 'contract'
    _history = True
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    activation_history = fields.One2Many('contract.activation_history',
        'contract', 'Activation History', order=[('start_date', 'ASC')],
        states=_STATES, depends=_DEPENDS)
    addresses = fields.One2Many('contract.address', 'contract',
        'Addresses', context={
            'policy_owner': Eval('current_policy_owner'),
            'start_date': Eval('start_date'),
            }, depends=['current_policy_owner', 'status'],
            states=_STATES)
    appliable_conditions_date = fields.Date('Appliable Conditions Date',
        states=_STATES, depends=_DEPENDS)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, ondelete='RESTRICT', states=_STATES, depends=_DEPENDS)
    quote_number = fields.Char('Quote Number', readonly=True)
    contract_number = fields.Char('Contract Number', select=1,
        states={
            'required': Eval('status') == 'active',
            }, depends=_DEPENDS, readonly=True)
    extra_datas = fields.One2Many('contract.extra_data', 'contract',
        'Extra Data', states={
            'invisible': ~Eval('extra_datas'),
            'readonly': Eval('status') != 'quote',
            }, depends=['extra_datas', 'status'])
    product = fields.Many2One('offered.product', 'Product',
        ondelete='RESTRICT', required=True, domain=[['OR',
                [('end_date', '>=', Eval('start_date'))],
                [('end_date', '=', None)],
                ], ['OR',
                [('start_date', '<=', Eval('start_date'))],
                [('start_date', '=', None)],
                ],
            ('company', '=', Eval('company')),
            ], states=_STATES, depends=['start_date', 'status', 'company'])
    options = fields.One2Many('contract.option', 'contract', 'Options',
        context={
            'start_date': Eval('start_date'),
            'product': Eval('product'),
            'all_extra_datas': Eval('extra_data_values')},
        domain=[('coverage.products', '=', Eval('product'))],
        states=_STATES, depends=['status', 'start_date', 'product',
            'extra_data_values'])
    start_management_date = fields.Date('Management Date', states=_STATES,
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
    end_date = fields.Function(
        fields.Date('End Date', states=_STATES, depends=_DEPENDS),
        'getter_contract_date', 'setter_end_date',
        searcher='search_contract_date')
    sub_status = fields.Many2One('contract.sub_status', 'Details on status',
        states={
            'required': Bool(Eval('is_sub_status_required')),
            'invisible': ~Eval('is_sub_status_required')
            },
        domain=[('status', '=', Eval('status'))],
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
    start_date = fields.Function(
        fields.Date('Start Date', states=_STATES, depends=_DEPENDS,
            required=True),
        'getter_contract_date', 'setter_start_date',
        searcher='search_contract_date')
    signature_date = fields.Date('Signature Date', states=_STATES,
        depends=_DEPENDS)
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
        states=_STATES, depends=_DEPENDS)
    last_modification = fields.Function(fields.DateTime('Last Modification'),
        'get_last_modification')

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
                    'invisible': Eval('status') != 'quote'},
                'button_decline': {
                    'invisible': Eval('status') != 'quote'},
                })
        cls._error_messages.update({
                'inactive_product_at_date':
                'Product %s is inactive at date %s',
                'activation_period_overlaps': 'Activation Periods "%(first)s"'
                ' and "%(second)s" overlap.',
                'no_quote_sequence': 'No quote sequence defined',
                'start_date_multiple_activation_history': 'Cannot change '
                'start date, multiple activation period detected',
                'missing_values': 'Cannot add functional key : both quote'
                'number and contract_number are missing from values',
                'invalid_format': 'Invalid file format',
                })
        cls._order.insert(0, ('last_modification', 'DESC'))

    @staticmethod
    def order_last_modification(tables):
        table, _ = tables[None]
        return [Coalesce(table.write_date, table.create_date)]

    def get_func_key(self, name):
        return '%s|%s' % ((self.quote_number, self.contract_number))

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

    def calculate_end_date(self):
        dates = [self.get_date_used_for_contract_end_date()]
        dates.append(self.get_maximum_end_date())
        dates = [x for x in dates if x] or [None]
        self.set_and_propagate_end_date(min(dates))

    def calculate(self):
        for option in self.options:
            option.calculate()
        self.calculate_end_date()

    @classmethod
    def update_contract_after_import(cls, contracts):
        for contract in contracts:
            contract.init_options()
            contract.init_default_address()

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
    def getter_contract_date(cls, contracts, name):
        cursor = Transaction().cursor
        pool = Pool()
        ActivationHistory = pool.get('contract.activation_history')
        activation_history = ActivationHistory.__table__()
        if name == 'end_date':
            column = NullIf(Max(Coalesce(
                        activation_history.end_date, datetime.date.max)),
                datetime.date.max).as_('end_date')
        elif name == 'start_date':
            column = Min(activation_history.start_date).as_('start_date')

        cursor.execute(*activation_history.select(
                activation_history.contract.as_('id'), column,
                where=(
                    activation_history.contract.in_(
                        [x.id for x in contracts])),
                group_by=activation_history.contract))

        values = dict([(id, value) for id, value in cursor.fetchall()])
        if backend.name() == 'sqlite':
            def convert(value):
                if value is not None:
                    return datetime.date(*map(int, value.split('-')))
            values = {i: convert(v) for i, v in values.iteritems()}
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
    def setter_start_date(cls, contract_ids, name, value):
        pool = Pool()
        ActivationHistory = pool.get('contract.activation_history')
        to_create, to_write = [], []
        for contract_slice in grouped_slice(contract_ids):
            for contract_id in contract_slice:
                existing = ActivationHistory.search([
                        ('contract', '=', contract_id)])
                if not existing:
                    to_create.append({
                            'contract': contract_id,
                            'start_date': value,
                            })
                elif len(existing) == 1:
                    if existing[0].start_date != value:
                        to_write += [[existing[0]], {'start_date': value}]
                else:
                    cls.raise_user_error(
                        'start_date_multiple_activation_history')
        if to_create:
            ActivationHistory.create(to_create)
        if to_write:
            ActivationHistory.write(*to_write)

    @classmethod
    def setter_end_date(cls, contracts, name, value):
        pool = Pool()
        ActivationHistory = pool.get('contract.activation_history')
        to_create, to_write, to_delete = [], [], []
        for contract_slice in grouped_slice(contracts):
            for contract in contract_slice:
                existing = ActivationHistory.search([
                        ('contract', '=', contract.id)])
                if not existing:
                    to_create.append({
                            'contract': contract.id,
                            'end_date': value,
                            })
                else:
                    for elem in reversed(existing):
                        if value and elem.start_date > value:
                            to_delete.append(elem)
                        elif elem.end_date != value:
                            to_write += [[elem], {'end_date': value}]
                        else:
                            break
        if to_delete:
            ActivationHistory.delete(to_delete)
        if to_create:
            ActivationHistory.create(to_create)
        if to_write:
            ActivationHistory.write(*to_write)

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
            group_by=activation_history.contract)

        return [('id', 'in', query)]

    @classmethod
    def search_parties(cls, name, clause):
        return [('subscriber.id',) + tuple(clause[1:])]

    @classmethod
    def validate(cls, contract):
        super(Contract, cls).validate(contract)
        for contract in contract:
            contract.check_activation_dates()

    def on_change_with_is_sub_status_required(self, name=None):
        return self.status in _STATUSES_WITH_SUBSTATUS

    @classmethod
    def get_revision_value(cls, contracts, names, ContractRevision):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Transaction().context.get('contract_revision_date',
            Date.today())
        return ContractRevision.get_values(contracts, names=names, date=date)

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

    def set_and_propagate_end_date(self, end_date):
        # Allows to set the contract's end_date and cascading the change in the
        # contract's one2manys (options, history, etc...)
        self.end_date = end_date
        options = list(self.options)
        for option in options:
            if option.end_date and option.end_date <= end_date:
                continue
            if not option.end_date:
                option.end_date = end_date
                # Need to force reload of contract end_date without saving
                option.parent_contract.end_date = end_date
        self.options = options

    def get_maximum_end_date(self):
        all_end_dates = [option.end_date for option in self.options]
        if all_end_dates:
            return max(all_end_dates)
        else:
            return None

    def set_start_date(self, start_date):
        self.start_date = start_date
        self.update_from_start_date()

    def update_from_start_date(self):
        for option in self.options:
            option.set_start_date(self.start_date)
            option.save()

    def set_appliable_conditions_date(self, new_date):
        self.appliable_conditions_date = new_date

    def get_rec_name(self, name):
        if self.status in ['quote', 'declined']:
            return self.quote_number
        else:
            return self.contract_number

    def get_synthesis_rec_name(self, name):
        Date = Pool().get('ir.date')
        if self.status in ['quote', 'declined']:
            return '%s (%s)[%s]' % (
                coop_string.translate_value(self, 'status'),
                self.product.rec_name,
                Date.date_as_string(self.start_date))
        elif self.end_date:
            return '%s (%s)[%s - %s]' % (self.contract_number,
                self.product.rec_name,
                Date.date_as_string(self.start_date),
                Date.date_as_string(self.end_date))
        else:
            return '%s (%s)[%s ]' % (self.contract_number,
                self.product.rec_name,
                Date.date_as_string(self.start_date))

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
    def search_global(cls, text):
        for id_, rec_name, icon in super(Contract, cls).search_global(text):
            icon = icon or 'contract'
            yield id_, rec_name, icon

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
        self.init_default_address()
        self.on_change_extra_data()

    def before_activate(self, contract_dict=None):
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
        contract.before_activate(contract_dict)
        contract.activate_contract()
        contract.finalize_contract()
        return contract

    @classmethod
    def _export_light(cls):
        return (super(Contract, cls)._export_light() |
            set(['product', 'company', 'addresses']))

    @classmethod
    def _export_skips(cls):
        return (super(Contract, cls)._export_skips() |
            set(['logs']))

    @classmethod
    def ws_subscribe_contracts(cls, contract_dict):
        'This method is a standard API for webservice use'
        pool = Pool()
        Party = pool.get('party.party')
        contracts = []
        messages = {}
        for ext_id, objects in contract_dict.iteritems():
            message = []
            messages[ext_id] = {'return': True, 'messages': message}
            try:
                for item in objects:
                    if item['__name__'] == 'party.party':
                        party = Party.import_json(item)
                        message.append({
                                'party_code': party.code
                                })
                    elif item['__name__'] == 'contract':
                        contract = cls.import_json(item)
                        contracts.append(contract)
                        message.append({
                                'contract_number': contract.contract_number,
                                'quote_number': contract.quote_number,
                                'status': contract.status
                                })
                        cls.update_contract_after_import([contract])
                    else:
                        cls.raise_user_error('invalid_format')
            except UserError as exc:
                return {ext_id: {
                        'return': False,
                        'error': exc.message,
                        }}
        return messages

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

    def finalize_contract(self):
        if not getattr(self, 'contract_number', None):
            self.contract_number = self.get_new_contract_number()
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
        self.status = 'active'
        options = list(self.options)
        for option in options:
            option.status = 'active'
        self.options = options
        Event.notify_events([self], 'activate')

    def decline_contract(self, reason):
        pool = Pool()
        Event = pool.get('event')
        self.status = 'declined'
        self.sub_status = reason
        self.save()
        Event.notify_events([self], 'decline', description=reason.name)

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
    def terminate(cls, contracts):
        pool = Pool()
        Event = pool.get('event')
        cls.write(contracts, {'status': 'terminated'})
        Event.notify_events(contracts, 'terminate')

    @classmethod
    def get_coverages(cls, product):
        return [x.coverage for x in product.ordered_coverages]

    def init_options(self):
        existing = dict(((x.coverage, x) for x in getattr(
                    self, 'options', [])))
        good_options = []
        to_delete = [elem for elem in existing.itervalues()]
        OptionModel = Pool().get('contract.option')
        for coverage in self.get_coverages(self.product):
            good_opt = None
            if coverage in existing:
                good_opt = existing[coverage.code]
                to_delete.remove(good_opt)
            elif coverage.subscription_behaviour == 'mandatory':
                good_opt = OptionModel.new_option_from_coverage(coverage,
                    self.product, self.start_date)
                good_opt.contract = self
            if good_opt:
                good_opt.save()
                good_options.append(good_opt)
        if to_delete:
            OptionModel.delete(to_delete)
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
                & (history.start_date <= at_date)
                & (
                    (history.end_date == None)
                    | (history.end_date >= at_date))
                ))
        company_id = Transaction().context.get('company', None)
        cursor.execute(*query_table.select(contract.id,
                where=(contract.company == company_id) if company_id else
                None))
        return cls.browse(cursor.fetchall())

    def get_contract_address(self, at_date=None):
        res = utils.get_good_versions_at_date(self, 'addresses', at_date)
        if res:
            return res[0].address

    def get_next_renewal_date(self):
        # TODO : Do not hardcode yearly here
        return coop_date.add_frequency('yearly', self.start_date)

    def init_default_address(self):
        if getattr(self, 'addresses', None):
            return True
        Address = Pool().get('contract.address')
        addresses = self.subscriber.address_get(at_date=self.start_date)
        if addresses:
            cur_address = Address()
            cur_address.address = addresses
            cur_address.start_date = self.start_date
            self.addresses = [cur_address]
        return True

    def get_appliable_logo(self, kind=''):
        if self.company:
            if self.company.party.logo:
                return self.company.party.logo
        return ''

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['subscriber', ('product', 'light'), 'extra_data_values',
            'options', 'covered_elements', 'start_date', 'end_date']

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

    def get_all_extra_data(self, at_date):
        res = self.product.get_all_extra_data(at_date)
        extra_data = utils.get_value_at_date(self.extra_datas, at_date)
        good_extra_data = extra_data.extra_data_values if extra_data else None
        res.update(good_extra_data)
        return res

    def update_contacts(self):
        pass

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


class ContractOption(model.CoopSQL, model.CoopView, model.ExpandTreeMixin,
            ModelCurrency):
    'Contract Option'

    __name__ = 'contract.option'
    _history = True
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    parent_contract = fields.Function(
        fields.Many2One('contract', 'Parent Contract'),
        'on_change_with_parent_contract', searcher='search_parent_contract')
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
    start_date = fields.Date('Start Date', required=True,
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    status = fields.Selection(OPTIONSTATUS, 'Status',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    status_string = status.translated('status')
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

    def get_func_key(self, name):
        if self.contract:
            elems = [self.contract.quote_number,
                self.contract.contract_number, self.coverage.rec_name]
            return '|'.join(str(x) for x in elems)
        else:
            return 'None|None|' + self.coverage.rec_name

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
    def _export_light(cls):
        return (super(ContractOption, cls)._export_light() |
            set(['coverage', 'product']))

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
    def copy(cls, options, default=None):
        default = {} if default is None else default.copy()
        if Transaction().context.get('copy_mode', '') == 'functional':
            skips = cls._export_skips() | cls.functional_skips_for_duplicate()
            for x in skips:
                default.setdefault(x, None)
        return super(ContractOption, cls).copy(options, default=default)

    @classmethod
    def functional_skips_for_duplicate(cls):
        return set(['automatic_end_date'])

    @classmethod
    def default_product(cls):
        return Transaction().context.get('product', None)

    @staticmethod
    def default_start_date():
        return utils.today()

    @classmethod
    def default_status(cls):
        return 'active'

    @fields.depends('coverage')
    def on_change_coverage(self):
        self.coverage_family = self.on_change_with_coverage_family()

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

    def get_rec_name(self, name):
        if self.coverage:
            return self.coverage.get_rec_name(name)
        return super(ContractOption, self).get_rec_name(name)

    def get_currency(self):
        if hasattr(self, 'coverage') and self.coverage:
            return self.coverage.currency

    def clean_up_versions(self, contract):
        pass

    def get_all_extra_data(self, at_date):
        res = self.coverage.get_all_extra_data(at_date)
        res.update(getattr(self, 'extra_data', {}))
        res.update(self.contract.get_all_extra_data(at_date))
        return res

    def init_dict_for_rule_engine(self, args):
        args['option'] = self
        self.coverage.init_dict_for_rule_engine(args)
        self.contract.init_dict_for_rule_engine(args)

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
            return new_option
        else:
            cls.raise_user_error('inactive_coverage_at_date', (coverage.name,
                    start_date))

    @classmethod
    def set_end_date(cls, options, name, end_date):
        Date = Pool().get('ir.date')
        to_write = []
        for option in options:
            if not end_date or end_date > option.start_date:
                if not option.parent_contract:
                    continue
                if end_date <= option.parent_contract.end_date:
                    if not end_date or (not option.automatic_end_date
                            or option.automatic_end_date >= end_date):
                        if end_date:
                            to_write.append(option)
                    else:
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
        if to_write:
            cls.write(to_write, {'manual_end_date': end_date})

    def get_possible_end_date(self):
        dates = {}
        if self.manual_end_date:
            dates['manual_date'] = self.manual_end_date
        if self.automatic_end_date:
            # If automatic end date is prior start date, we will have a date
            # before the start date, whisch is strange but not wrong
            dates['automatic_end_date'] = self.automatic_end_date
        if self.parent_contract and self.parent_contract.end_date:
            dates['contract_end_date'] = self.parent_contract.end_date
        return dates

    def get_end_date(self, name):
        dates = [x for x in self.get_possible_end_date().itervalues()]
        return min(dates) if dates else None

    def set_automatic_end_date(self):
        self.automatic_end_date = self.calculate_automatic_end_date()

    def calculate_automatic_end_date(self):
        exec_context = {'date': self.start_date}
        self.init_dict_for_rule_engine(exec_context)
        return self.coverage.calculate_end_date(exec_context)

    def set_start_date(self, new_start_date):
        if self.start_date and self.start_date < new_start_date:
            self.start_date = new_start_date

    def calculate(self):
        self.set_automatic_end_date()

    @classmethod
    def search_parent_contract(cls, name, clause):
        return [('contract',) + tuple(clause[1:])]


class ContractExtraDataRevision(model._RevisionMixin, model.CoopSQL,
        model.CoopView, export.ExportImportMixin):
    'Contract Extra Data'

    __name__ = 'contract.extra_data'
    _parent_name = 'contract'
    _func_key = 'date'

    contract = fields.Many2One('contract', 'Contract', required=True,
        select=True, ondelete='CASCADE')
    extra_data_values = fields.Dict('extra_data', 'Extra Data')
    extra_data_summary = fields.Function(
        fields.Char('Extra Data Summary'),
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


class ContractAddress(model.CoopSQL, model.CoopView):
    'Contract Address'

    __name__ = 'contract.address'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    address = fields.Many2One('party.address', 'Address', ondelete='RESTRICT',
        domain=[('party', '=', Eval('policy_owner'))],
        depends=['policy_owner'])
    policy_owner = fields.Function(
        fields.Many2One('party.party', 'Policy Owner',
            states={'invisible': True}),
        'on_change_with_policy_owner')

    @staticmethod
    def default_policy_owner():
        return Transaction().context.get('policy_owner')

    @staticmethod
    def default_start_date():
        return Transaction().context.get('start_date')

    @fields.depends('contract', 'start_date')
    def on_change_with_policy_owner(self, name=None):
        if self.contract and self.start_date:
            res = self.contract.get_policy_owner(self.start_date)
        else:
            res = self.default_policy_owner()
        if res:
            return res.id


class ContractSelectEndDate(model.CoopView):
    'End date selector for contract'

    __name__ = 'contract.end.select_date'

    end_date = fields.Date('End date', required=True)


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
        Contract = Pool().get('contract')
        contracts = []
        for contract in Contract.browse(
                Transaction().context.get('active_ids')):
            contract.set_and_propagate_end_date(self.select_date.end_date)
            contracts.append([contract])
            contracts.append(contract._save_values)
        Contract.write(*contracts)
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
        selected_contract.set_start_date(new_date)
        selected_contract.save()
        return 'end'


class ContractSubStatus(model.CoopSQL, model.CoopView):
    'Contract SubStatus'

    __name__ = 'contract.sub_status'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    status = fields.Selection(CONTRACTSTATUSES, 'Status', required=True)

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)
