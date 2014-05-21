import copy
import datetime
from sql import Literal
from sql.conditionals import NullIf, Coalesce
from sql.aggregate import Max, Min

from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, Bool
from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import PYSONEncoder

from trytond.modules.cog_utils import utils, model, fields, coop_date
from trytond.modules.cog_utils import MergedMixin
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.offered import offered
from trytond.modules.cog_utils import coop_string


CONTRACTSTATUSES = [
    ('', ''),
    ('quote', 'Quote'),
    ('active', 'Active'),
    ('hold', 'Hold'),
    ('terminated', 'Terminated'),
    ]

OPTIONSTATUS = CONTRACTSTATUSES + [
    ('refused', 'Refused'),
    ]

__all__ = [
    'ActivationHistory',
    'Contract',
    'ContractOption',
    'ContractAddress',
    'ContractSelectEndDate',
    'ContractEnd',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    'SynthesisMenuContrat',
    ]


class ActivationHistory(model.CoopSQL, model.CoopView):
    'Activation History'

    __name__ = 'contract.activation_history'

    contract = fields.Many2One('contract', 'Contract', required=True,
        ondelete='CASCADE')
    start_date = fields.Date('Start Date', required=True, domain=[If(
                Bool(Eval('end_date', None)),
                ('start_date', '<=', Eval('end_date')),
                ('start_date', '>=', datetime.date.min))])
    end_date = fields.Date('End Date', domain=['OR',
            ('end_date', '=', None),
            ('end_date', '>=', Eval('start_date', datetime.date.min))],
        depends=['start_date'])


_STATES = {
    'readonly': Eval('status') != 'quote',
    }
_DEPENDS = ['status']


class Contract(model.CoopSQL, model.CoopView, ModelCurrency):
    'Contract'

    __name__ = 'contract'
    _rec_name = 'contract_number'
    _history = True

    activation_history = fields.One2Many('contract.activation_history',
        'contract', 'Activation History', order=[('start_date', 'ASC')])
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
    contract_number = fields.Char('Contract Number', select=1,
        states={
            'required': Eval('status') == 'active',
            'readonly': Eval('status') != 'quote',
            }, depends=_DEPENDS)
    extra_data = fields.Dict('extra_data', 'Complementary Data', states={
            'invisible': ~Eval('extra_data'),
            'readonly': Eval('status') != 'quote',
            }, depends=['extra_data', 'status'])
    product = fields.Many2One('offered.product', 'Product',
        ondelete='RESTRICT', required=True, domain=[['OR',
                [('end_date', '>=', Eval('start_date'))],
                [('end_date', '=', None)],
                ], ['OR',
                [('start_date', '<=', Eval('start_date'))],
                [('start_date', '=', None)],
                ],
            ('company', '=', Eval('company')),
            ], depends=['start_date', 'status', 'company'])
    options = fields.One2Many('contract.option', 'contract', 'Options',
        context={
            'start_date': Eval('start_date'),
            'product': Eval('product'),
            'parties': Eval('parties'),
            'all_extra_datas': Eval('extra_data')},
        domain=[('coverage.products', '=', Eval('product'))],
        states=_STATES, depends=['parties', 'status', 'start_date', 'product',
            'extra_data'])
    start_management_date = fields.Date('Management Date', states=_STATES,
        depends=_DEPENDS)
    status = fields.Selection(CONTRACTSTATUSES, 'Status')
    subscriber = fields.Many2One('party.party', 'Subscriber',
        domain=[If(
                Eval('subscriber_kind') == 'person',
                ('is_person', '=', True),
                ('id', '>', 0)),
            If(
                Eval('subscriber_kind') == 'company',
                ('is_company', '=', True),
                ('id', '>', 0))],
        states=_STATES, depends=['subscriber_kind', 'status'],
        ondelete='RESTRICT')
    current_policy_owner = fields.Function(
        fields.Many2One('party.party', 'Current Policy Owner'),
        'on_change_with_current_policy_owner')
    end_date = fields.Function(
        fields.Date('End Date'),
        'getter_contract_date', searcher='search_contract_date')
    parties = fields.Function(
        fields.Many2Many('party.party', None, None, 'Parties'),
        'on_change_with_parties')
    product_kind = fields.Function(
        fields.Char('Product Kind'),
        'on_change_with_product_kind', searcher='search_product_kind')
    product_subscriber_kind = fields.Function(
        fields.Selection(offered.SUBSCRIBER_KIND, 'Product Subscriber Kind'),
        'get_product_subscriber_kind')
    start_date = fields.Function(
        fields.Date('Start Date'),
        'getter_contract_date', searcher='search_contract_date')
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
    contacts = fields.One2Many('contract.contact', 'contract', 'Contacts')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.__rpc__.update({'ws_subscribe_contract': RPC(readonly=False)})
        cls._buttons.update({'option_subscription': {}})
        cls._error_messages.update({
                'inactive_product_at_date':
                'Product %s is inactive at date %s',
                'activation_period_overlaps': 'Activation Periods "%(first)s"'
                ' and "%(second)s" overlap.',
                })

    def get_icon(self, name=None):
        if self.status == 'active':
            return 'contract_green'
        return 'contract'

    @classmethod
    def default_activation_history(cls):
        return [{
                'start_date': cls.default_start_date(),
                }]

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company', None)

    @classmethod
    def default_extra_data(cls):
        return {}

    @staticmethod
    def default_start_date():
        return utils.today()

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

        return dict([(id, value) for id, value in cursor.fetchall()])

    @fields.depends('product', 'options', 'start_date', 'extra_data',
        'appliable_conditions_date')
    def on_change_product(self):
        if self.product is None:
            return {
                'product_kind': '',
                'subscriber_kind': 'person',
                'options': {'remove': [x.id for x in self.options]},
                'extra_data': {},
                }
        available_coverages = self.get_coverages(self.product)
        to_remove = []
        if self.options:
            for elem in self.options:
                if elem.coverage not in available_coverages:
                    to_remove.append(elem.id)
                else:
                    available_coverages.remove(elem.coverage)
        Option = Pool().get('contract.option')
        to_add = []
        for elem in available_coverages:
            if elem.subscription_behaviour == 'optional':
                continue
            new_opt = Option.init_default_values_from_coverage(elem,
                self.product)
            to_add.append([-1, new_opt])
        result = {
            'product_kind': self.product.kind,
            'subscriber_kind': ('person' if self.product.subscriber_kind in
                ['all', 'person'] else 'company'),
            'extra_data': self.product.get_extra_data_def('contract',
                self.extra_data, self.appliable_conditions_date),
            'product_subscriber_kind': self.product.subscriber_kind,
            }
        if not to_add and not to_remove:
            return result
        result['options'] = {}
        if to_add:
            result['options']['add'] = to_add
        if to_remove:
            result['options']['remove'] = to_remove
        return result

    @fields.depends('extra_data', 'start_date', 'options', 'product',
        'appliable_conditions_date')
    def on_change_extra_data(self):
        if not self.product:
            return {'extra_data': {}}
        if not self.extra_data:
            self.extra_data = {}
        return {
            'extra_data': self.product.get_extra_data_def('contract',
                self.extra_data,
                self.appliable_conditions_date),
            }

    @fields.depends('start_date')
    def on_change_start_date(self):
        return {'appliable_conditions_date': self.start_date}

    @fields.depends('subscriber')
    def on_change_with_current_policy_owner(self, name=None):
        policy_owner = self.get_policy_owner(utils.today())
        return policy_owner.id if policy_owner else None

    @fields.depends('subscriber')
    def on_change_with_parties(self, name=None):
        if not self.subscriber:
            return []
        return [self.subscriber.id]

    @fields.depends('product')
    def on_change_with_product_kind(self, name=None):
        if not self.product:
            return ''
        return self.product.kind

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
    def search_product_kind(cls, name, clause):
        return [('product.kind', ) + tuple(clause[1:])]

    @classmethod
    def validate(cls, contract):
        super(Contract, cls).validate(contract)
        for contract in contract:
            contract.check_activation_dates()

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

    def set_end_date(self, end_date):
        # Allows to set the contract's end_date and cascading the change in the
        # contract's one2manys (options, history, etc...)
        self.end_date = end_date
        ActivationHistory = Pool().get('contract.activation_history')
        to_delete = []
        for idx, elem in enumerate(self.activation_history):
            if elem.start_date >= end_date:
                to_delete.append(idx)
                continue
            if elem.end_date and elem.end_date <= end_date:
                continue
            elem.end_date = end_date
        if isinstance(self.activation_history, tuple):
            self.activation_history = list(self.activation_history)
        for option in self.options:
            if option.end_date and option.end_date <= end_date:
                continue
            option.end_date = end_date
        if not to_delete:
            return
        ActivationHistory.delete([
            self.activation_history.pop(elem)
            for elem in to_delete])

    def get_rec_name(self, name):
        if self.product and self.current_policy_owner:
            if self.contract_number:
                return '%s (%s) - %s' % (self.contract_number,
                    self.product.get_rec_name(name),
                    self.current_policy_owner.get_rec_name(name))
            else:
                return 'Contract %s - %s' % (
                    self.product.get_rec_name(name),
                    self.current_policy_owner.get_rec_name(name))
        else:
            return super(Contract, self).get_rec_name(name)

    def get_synthesis_rec_name(self, name):
        if self.end_date:
            return '%s (%s)[%s - %s]' % (self.contract_number,
                self.product.rec_name,
                coop_string.date_as_string(self.start_date),
                coop_string.date_as_string(self.end_date))
        else:
            return '%s (%s)[%s ]' % (self.contract_number,
                self.product.rec_name,
                coop_string.date_as_string(self.start_date))

    @classmethod
    def search_global(cls, text):
        for id_, rec_name, icon in super(Contract, cls).search_global(text):
            icon = icon or 'contract'
            yield id_, rec_name, icon

    @classmethod
    def search_rec_name(cls, name, clause):
        contracts = cls.search([
            'OR',
            ('contract_number',) + tuple(clause[1:]),
            ('subscriber.name',) + tuple(clause[1:]),
        ])
        return [('id', 'in', [c.id for c in contracts])]

    def init_contract(self, product, party, contract_dict=None):
        self.subscriber = party
        at_date = contract_dict.get('start_date', utils.today())
        self.init_from_product(product, at_date)
        self.init_default_address()
        if not contract_dict or not 'extra_data' in contract_dict:
            return
        extra_data = self.on_change_extra_data()['extra_data']
        for key in extra_data.iterkeys():
            if key in contract_dict['extra_data']:
                self.extra_data[key] = contract_dict['extra_data'][key]

    def before_activate(self, contract_dict=None):
        pass

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
            sub_option = SubscribedOpt()
            sub_option.init_from_coverage(coverage, product, at_date)
            contract.options.append(sub_option)
        contract.before_activate(contract_dict)
        contract.activate_contract()
        contract.finalize_contract()
        contract.save()
        return contract

    @classmethod
    def ws_subscribe_contract(cls, contract_dict):
        'This method is a standard API for webservice use'
        pool = Pool()
        Party = pool.get('party.party')
        Product = pool.get('offered.product')
        sub_dict = contract_dict['subscriber']
        if not 'code' in sub_dict:
            party_res = Party.ws_create_person(sub_dict)
            if not party_res.get('return'):
                return {
                    'return': False,
                    'error_code': 'subscriber_creation_impossible',
                    'error_message': "Can't create subscriber record",
                }
            code = party_res['party_code']
        else:
            code = sub_dict['code']
        subscribers = Party.search([('code', '=', code)],
            limit=1, order=[])
        if not subscribers:
            return {
                'return': False,
                'error_code': 'unknown_subscriber',
                'error_message': 'No subscriber found for code %s' % code,
                }
        subscriber = subscribers[0]

        products = Product.search(
            [('code', '=', contract_dict['product']['code'])], limit=1,
            order=[])
        if not products:
            return {
                'return': False,
                'error_code': 'unknown_product',
                'error_message': 'No product available with code %s' % (
                    contract_dict['product']['code'],
                    ),
            }
        product = products[0]

        contract = cls.subscribe_contract(product, subscriber, contract_dict)
        contract.save()
        return {
            'return': True,
            'contract_number': contract.contract_number,
            }

    def init_from_product(self, product, start_date=None, end_date=None):
        ActivationHistory = Pool().get('contract.activation_history')
        if not start_date:
            start_date = utils.today()
        if utils.is_effective_at_date(product, start_date):
            self.product = product
            start_date = (
                max(product.start_date, start_date)
                if start_date else product.start_date)
            self.activation_history = [ActivationHistory(
                    start_date=start_date)]
            end_date = (
                min(product.end_date, end_date)
                if end_date else product.end_date)
            if end_date:
                self.activation_history[0].end_date = coop_date.add_day(
                    end_date, -1)
            self.start_date, self.end_date = start_date, end_date
            self.status = 'quote'
        else:
            self.raise_user_error('inactive_product_at_date',
                (product.name, start_date))
        self.appliable_conditions_date = self.start_date

    def init_extra_data(self):
        if not (hasattr(self, 'extra_data') and
                self.extra_data):
            self.extra_data = {}
        self.extra_data = self.on_change_extra_data()['extra_data']

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

    def get_dates(self):
        return self.product.get_dates(self)

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
        self.contract_number = self.get_new_contract_number()

    def get_policy_owner(self, at_date=None):
        '''
        the owner of a contract could change over time, you should never use
        the direct link subscriber
        '''
        # TODO: to enhance
        if getattr(self, 'subscriber', None):
            return self.subscriber

    def activate_contract(self):
        self.status = 'active'
        for option in self.options:
            option.status = 'active'
            option.save()

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
                good_opt = OptionModel()
                good_opt.init_from_coverage(coverage, self.product,
                    self.start_date)
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
                where=(contract.company == company_id) if company_id else None))
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
        addresses = self.subscriber.address_get(
            at_date=self.start_date)
        if addresses:
            cur_address = utils.instanciate_relation(self, 'addresses')
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
        return ['subscriber', ('product', 'light'), 'extra_data',
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

    def get_all_extra_data(self, at_date):
        res = self.product.get_all_extra_data(at_date)
        res.update(getattr(self, 'extra_data', {}))
        return res

    def update_contacts(self):
        pass

    def get_product_subscriber_kind(self, name):
        return self.product.subscriber_kind if self.product else ''

    @fields.depends('subscriber_kind', 'subscriber')
    def on_change_subscriber_kind(self):
        if self.subscriber and (self.subscriber_kind == 'person'
                and not self.subscriber.is_person
                or self.subscriber_kind == 'company'
                and not self.subscriber.is_company):
            return {'subscriber': None}
        else:
            return {}


class ContractOption(model.CoopSQL, model.CoopView, ModelCurrency):
    'Contract Option'

    __name__ = 'contract.option'
    _history = True

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='RESTRICT', states={
            'required': Eval('status') == 'active',
            'readonly': Eval('status') != 'quote',
            },
        depends=['status', 'start_date', 'end_date', 'product'])
    end_date = fields.Date('End Date')
    start_date = fields.Date('Start Date', required=True)
    status = fields.Selection(OPTIONSTATUS, 'Status')
    appliable_conditions_date = fields.Function(
        fields.Date('Appliable Conditions Date'),
        'on_change_with_appliable_conditions_date')
    contract_number = fields.Function(
        fields.Char('Contract Number'),
        'on_change_with_contract_number')
    coverage_family = fields.Function(
        fields.Char('Coverage Family'),
        'on_change_with_coverage_family')
    coverage_kind = fields.Function(
        fields.Char('Coverage Kind', states={'invisible': True}),
        'on_change_with_coverage_kind', searcher='search_coverage_kind')
    current_policy_owner = fields.Function(
        fields.Many2One('party.party', 'Current Policy Owner'),
        'on_change_with_current_policy_owner')
    parties = fields.Function(
        fields.Many2Many('party.party', None, None, 'Parties'),
        'on_change_with_parties')
    product = fields.Function(
        fields.Many2One('offered.product', 'Product'),
        'on_change_with_product')

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._error_messages.update({
                'inactive_coverage_at_date':
                'Coverage %s is inactive at date %s',
                })

    @classmethod
    def default_appliable_conditions_date(cls):
        contract_id = Transaction().context.get('contract', -1)
        if contract_id <= 0:
            return cls.default_start_date()
        return Pool().get('contract')(contract_id).appliable_conditions_date

    @classmethod
    def default_parties(cls):
        return Transaction().context.get('parties', [])

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
        return {
            'coverage_kind': self.on_change_with_coverage_kind(),
            'coverage_family': self.on_change_with_coverage_family(),
            }

    @fields.depends('contract', 'start_date')
    def on_change_with_appliable_conditions_date(self, name=None):
        start_date = Transaction().context.get('start_date', None)
        if start_date:
            return start_date
        return self.contract.appliable_conditions_date

    @fields.depends('contract')
    def on_change_with_contract_number(self, name=None):
        return self.contract.contract_number if self.contract else ''

    @fields.depends('coverage')
    def on_change_with_coverage_family(self, name=None):
        return self.coverage.family if self.coverage else ''

    @fields.depends('coverage')
    def on_change_with_coverage_kind(self, name=None):
        return self.coverage.kind if self.coverage else ''

    @fields.depends('contract')
    def on_change_with_current_policy_owner(self, name=None):
        if self.contract:
            return self.contract.current_policy_owner

    @fields.depends('contract')
    def on_change_with_parties(self, name=None):
        if not self.contract or self.contract.id <= 0:
            return Transaction().context.get('parties', [])
        return [x.id for x in self.contract.parties]

    @fields.depends('contract')
    def on_change_with_product(self, name=None):
        product = Transaction().context.get('product', None)
        if product:
            return product
        if self.contract and self.contract.product:
            return self.contract.product.id

    def get_rec_name(self, name):
        if self.coverage:
            return self.coverage.get_rec_name(name)
        return super(ContractOption, self).get_rec_name(name)

    def get_currency(self):
        if hasattr(self, 'coverage') and self.coverage:
            return self.coverage.currency

    @classmethod
    def search_coverage_kind(cls, name, clause):
        return [('coverage.kind', ) + tuple(clause[1:])]

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
    def init_default_values_from_coverage(cls, coverage, product,
            start_date=None, end_date=None):
        if not start_date:
            start_date = utils.today()
        if utils.is_effective_at_date(coverage, start_date):
            result = {}
            result['coverage'] = coverage.id
            result['status'] = 'active'
            result['start_date'] = start_date
            result['appliable_conditions_date'] = start_date
            return result
        else:
            cls.raise_user_error('inactive_coverage_at_date', (coverage.name,
                    start_date))

    def init_from_coverage(self, coverage, product, start_date=None,
            end_date=None):
        cur_dict = self.init_default_values_from_coverage(coverage, product,
            start_date, end_date)
        for key, val in cur_dict.iteritems():
            setattr(self, key, val)


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
            contract.set_end_date(self.select_date.end_date)
            contracts.append([contract])
            contracts.append(contract._save_values)
        Contract.write(*contracts)
        return 'end'


class SynthesisMenuContrat(model.CoopSQL):
    'Party Synthesis Menu Contract'
    __name__ = 'party.synthesis.menu.contract'
    name = fields.Char('Contracts')
    subscriber = fields.Many2One('party.party', 'Subscriber')

    @staticmethod
    def table_query():
        pool = Pool()
        Contract = pool.get('contract')
        ContractSynthesis = pool.get('party.synthesis.menu.contract')
        party = pool.get('party.party').__table__()
        contract = Contract.__table__()
        query_table = party.join(contract, 'LEFT OUTER', condition=(
            party.id == contract.subscriber))
        return query_table.select(
            party.id,
            Max(contract.create_uid).as_('create_uid'),
            Max(contract.create_date).as_('create_date'),
            Max(contract.write_uid).as_('write_uid'),
            Max(contract.write_date).as_('write_date'),
            Literal(coop_string.translate_label(ContractSynthesis, 'name')).
            as_('name'), party.id.as_('subscriber'),
            # where=(contract.status != 'active'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'contract'


class SynthesisMenu(MergedMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def merged_models(cls):
        res = super(SynthesisMenu, cls).merged_models()
        res.extend([
            'party.synthesis.menu.contract',
            'contract',
            ])
        return res

    @classmethod
    def merged_field(cls, name, Model):
        merged_field = super(SynthesisMenu, cls).merged_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.contract':
            if name == 'parent':
                return Model._fields['subscriber']
        elif Model.__name__ == 'contract':
            if name == 'parent':
                merged_field = copy.deepcopy(Model._fields['subscriber'])
                merged_field.model_name = 'party.synthesis.menu.contract'
                return merged_field
            elif name == 'name':
                return Model._fields['contract_number']
        return merged_field


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    def get_action(self, record):
        Model = record.__class__
        if Model.__name__ != 'party.synthesis.menu.contract':
            return super(SynthesisMenuOpen, self).get_action(record)
        domain = PYSONEncoder().encode([('subscriber', '=', record.id)])
        actions = {
            'res_model': 'contract',
            'pyson_domain': domain,
            'views': [(None, 'tree'), (None, 'form')]
        }
        return actions
