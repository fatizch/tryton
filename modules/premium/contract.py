import datetime
from collections import defaultdict
from sql import Column
from sql.conditionals import Coalesce

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.rpc import RPC

from trytond.modules.cog_utils import model, fields, utils, coop_date
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.contract import _STATES, _DEPENDS

from offered import PREMIUM_FREQUENCY

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    'ContractFee',
    'Premium',
    'PremiumTax',
    ]


class Contract:
    __name__ = 'contract'

    all_premiums = fields.One2Many('contract.premium', 'main_contract',
        'All Premiums', readonly=True, order=[('start', 'ASC'),
            ('rated_entity', 'ASC')])
    fees = fields.One2Many('contract.fee', 'contract', 'Fees', states=_STATES,
        depends=_DEPENDS, delete_missing=True)
    premiums = fields.One2Many('contract.premium', 'contract', 'Premiums',
        delete_missing=True, target_not_required=True)
    show_premium = fields.Function(
        fields.Boolean('Show Premium'), 'get_show_premium')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_calculate_prices': {},
                'button_display_premium': {
                    'invisible': ~Eval('show_premium')},
                })

    @classmethod
    def _export_skips(cls):
        return super(Contract, cls)._export_skips() | {'all_premiums'}

    @classmethod
    @model.CoopView.button
    def button_calculate_prices(cls, contracts):
        cls.calculate_prices(contracts)

    @classmethod
    @model.CoopView.button_action('premium.act_premium_display')
    def button_display_premium(cls, contracts):
        pass

    def get_show_premium(self, name):
        return self.status == 'active'

    @classmethod
    def force_calculate_prices(cls, contracts):
        return cls.calculate_prices(contracts, start=datetime.date.min)

    @classmethod
    def delete_prices(cls, contracts, limit):
        limit = limit or datetime.date.min
        Premium = Pool().get('contract.premium')
        if limit > datetime.date.min:
            Premium.write(Premium.search([
                        ('end', '>=', limit),
                        ('start', '<', limit)]),
                {'end': limit + datetime.timedelta(days=-1)})
        Premium.delete(Premium.search([
                    ('main_contract', 'in', [x.id for x in contracts]),
                    ['OR',
                        ('start', '>=', limit),
                        ('main_contract.status', '=', 'void')],
                    ]))

    @classmethod
    def calculate_prices(cls, contracts, start=None, end=None):
        cls.save(contracts)
        final_prices = defaultdict(list)
        for contract in contracts:
            if contract.status == 'void':
                continue
            prices = contract.calculate_prices_between_dates(start, end)
            for date, price in prices.iteritems():
                final_prices[date].extend(price)
        cls.delete_prices(contracts, start)
        cls.store_prices(final_prices)
        return True, ()

    def calculate_prices_between_dates(self, start=None, end=None):
        if not start or start == datetime.date.min:
            start = self.start_date
        dates = utils.limit_dates(self.get_dates(), start)
        lines = self.product.calculate_premiums(self, dates)
        return lines

    @classmethod
    def store_prices(cls, prices):
        if not prices:
            return
        pool = Pool()
        Premium = pool.get('contract.premium')
        dates = list(prices.iterkeys())
        dates.sort()
        to_save = []
        parents_to_update = {}
        for date, price_list in prices.iteritems():
            date_pos = dates.index(date)
            if date_pos < len(dates) - 1:
                end_date = dates[date_pos + 1] + datetime.timedelta(days=-1)
            else:
                end_date = None
            for price in price_list:
                prices = cls.store_price(price, start_date=date,
                    end_date=end_date)
                to_save += prices
        for premium in to_save:
            if premium.parent in parents_to_update:
                parents_to_update[premium.parent]['save'].append(premium)
            else:
                parents_to_update[premium.parent] = {
                    'save': [premium],
                    'delete': [],
                    'keep': [],
                    'write': [],
                    }
        for elem in parents_to_update.iterkeys():
            existing = [x for x in getattr(elem, 'premiums', []) if x.id > 0]
            for premium in existing:
                if premium.start >= dates[0]:
                    parents_to_update[elem]['delete'].append(premium)
                elif (premium.start or datetime.date.min) < dates[0] <= (
                        premium.end or datetime.date.max):
                    premium.end = coop_date.add_day(dates[0], -1)
                    parents_to_update[elem]['write'].append(premium)
                else:
                    parents_to_update[elem]['keep'].append(premium)
            Premium.remove_duplicates(elem, parents_to_update[elem])

        for elem in parents_to_update.iterkeys():
            if not elem._values:
                continue
            elem.save()

    @classmethod
    def store_price(cls, price, start_date, end_date):
        Premium = Pool().get('contract.premium')
        new_premium = Premium.new_line(price, start_date, end_date)
        return [new_premium] if new_premium else []

    def appliable_fees(self):
        all_fees = list(self.product.fees)
        [all_fees.extend(option.fees) for option in self.product.coverages]
        return set(all_fees)

    def pre_calculate_fees(self):
        ContractFee = Pool().get('contract.fee')
        contract_fees = {x.fee: x for x in self.fees}
        current_fees = set(contract_fees.keys())
        required_fees = self.appliable_fees()

        to_delete = []
        for fee in current_fees - required_fees:
            to_delete.append(contract_fees.pop(fee))
        for fee in required_fees - current_fees:
            contract_fees[fee] = ContractFee.new_fee(fee)

        self.fees = sorted(contract_fees.values(), key=lambda x: x.fee)
        if to_delete:
            ContractFee.delete(to_delete)

    def get_dates(self):
        return self.product.get_dates(self)

    @classmethod
    def _calculate_methods(cls, product):
        return super(Contract, cls)._calculate_methods(product) + \
            ['pre_calculate_fees', 'calculate_prices']


class ContractOption:
    __name__ = 'contract.option'

    premiums = fields.One2Many('contract.premium', 'option', 'Premiums',
        delete_missing=True, target_not_required=True)

    @classmethod
    def functional_skips_for_duplicate(cls):
        return (super(ContractOption, cls).functional_skips_for_duplicate() |
        set(['premiums']))


class ContractFee(model.CoopSQL, model.CoopView, ModelCurrency):
    'Contract Fee'

    __name__ = 'contract.fee'

    contract = fields.Many2One('contract', 'Contract', required=True,
        ondelete='CASCADE')
    fee = fields.Many2One('account.fee', 'Fee', required=True,
        ondelete='RESTRICT')
    premiums = fields.One2Many('contract.premium', 'fee', 'Premiums',
        delete_missing=True, target_not_required=True)
    overriden_amount = fields.Numeric('Amount', states={
            'readonly': ~Eval('fee_allow_override', False),
            'invisible': Eval('fee_type', '') != 'fixed'},
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits', 'fee_allow_override', 'fee_type'])
    overriden_rate = fields.Numeric('Rate', digits=(14, 4), states={
            'readonly': ~Eval('fee_allow_override', False),
            'invisible': Eval('fee_type', '') != 'percentage'},
        depends=['fee_allow_override', 'fee_type'])
    amount_as_string = fields.Function(
        fields.Char('Amount'),
        'on_change_with_amount_as_string')
    fee_allow_override = fields.Function(
        fields.Boolean('Override Allowed'),
        'get_fee_field')
    fee_type = fields.Function(
        fields.Selection([
                ('percentage', 'Percentage'),
                ('fixed', 'Fixed'),
                ], 'Type'),
        'get_fee_field')
    accept_fee = fields.Function(
        fields.Boolean('Accept Fee', states={
            'readonly': ~Eval('fee_allow_override', False)},
            depends=['fee_allow_override']),
        'on_change_with_accept_fee', 'set_accept_fee')

    @classmethod
    def default_accept_fee(cls):
        # Workaround for bug https://bugs.tryton.org/issue4524
        return True

    @classmethod
    def default_overriden_amount(cls):
        return 0

    @classmethod
    def default_overriden_rate(cls):
        return 0

    @classmethod
    def _export_light(cls):
        return super(ContractFee, cls)._export_light() | {'fee'}

    @fields.depends('fee')
    def on_change_fee(self):
        self.fee_type = self.fee.type if self.fee else None
        self.fee_allow_override = self.fee.allow_override if self.fee else \
            False
        self.overriden_rate = self.fee.rate if self.fee else None
        self.overriden_amount = self.fee.amount if self.fee else None
        self.accept_fee = True

    @fields.depends('fee', 'accept_fee')
    def on_change_accept_fee(self):
        if self.accept_fee:
            self.on_change_fee()
        else:
            self.overriden_amount = 0
            self.overriden_rate = 0

    @fields.depends('fee_type', 'currency', 'overriden_amount',
        'overriden_rate', 'accept_fee',)
    def on_change_with_amount_as_string(self, name=None):
        if self.fee_type == 'fixed':
            return ' %s %s' % (
                str(self.currency.round(self.overriden_amount)),
                self.currency_symbol)
        elif self.fee_type == 'rate':
            return ' %f %%' % str(100 * self.overriden_rate)
        return ''

    @fields.depends('fee_type', 'overriden_amount', 'overriden_rate')
    def on_change_with_accept_fee(self, name=None):
        return any([self.overriden_rate, self.overriden_amount])

    def get_currency(self):
        return self.contract.currency if self.contract else None

    def get_fee_field(self, name):
        if not self.fee:
            return None
        return getattr(self.fee, name[4:], None)

    def get_rec_name(self, name):
        return self.fee.rec_name if self.fee else ''

    @classmethod
    def set_accept_fee(cls, instances, name, value):
        if value:
            return
        cls.write(instances, {'overriden_amount': 0, 'overriden_rate': 0})

    @classmethod
    def new_fee(cls, fee_desc):
        new_fee = cls()
        new_fee.fee = fee_desc
        new_fee.on_change_fee()
        return new_fee

    def init_dict_for_rule_engine(self, base_dict):
        base_dict['contract_fee'] = self
        self.contract.init_dict_for_rule_engine(base_dict)


class Premium(model.CoopSQL, model.CoopView):
    'Premium'

    __name__ = 'contract.premium'
    contract = fields.Many2One('contract', 'Contract', select=True,
        ondelete='CASCADE')
    option = fields.Many2One('contract.option', 'Option', select=True,
        ondelete='CASCADE')
    fee = fields.Many2One('contract.fee', 'Fee', ondelete='CASCADE')
    rated_entity = fields.Reference('Rated Entity', 'get_rated_entities',
        required=True)
    start = fields.Date('Start')
    end = fields.Date('End')
    amount = fields.Numeric('Amount', required=True)
    frequency = fields.Selection(PREMIUM_FREQUENCY, 'Frequency', sort=False)
    frequency_string = frequency.translated('frequency')
    taxes = fields.Many2Many('contract.premium-account.tax',
        'premium', 'tax', 'Taxes',
        domain=[
            ('parent', '=', None),
            ['OR',
                ('group', '=', None),
                ('group.kind', 'in', ['sale', 'both']),
                ],
            ])
    main_contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_main_contract', searcher='search_main_contract')
    parent = fields.Function(
        fields.Reference('Parent', 'get_parent_models'),
        'get_parent')

    @classmethod
    def __setup__(cls):
        super(Premium, cls).__setup__()
        cls._order = [('rated_entity', 'ASC'), ('start', 'ASC')]
        cls.__rpc__.update({'get_parent_models': RPC()})

    @classmethod
    def _export_light(cls):
        return super(Premium, cls)._export_light() | {'rated_entity', 'taxes'}

    def get_main_contract(self, name=None):
        if self.contract:
            return self.contract.id
        elif self.option:
            return self.option.parent_contract.id
        elif self.fee:
            return self.fee.contract.id

    @classmethod
    def get_possible_parent_field(cls):
        return set(['contract', 'option', 'fee'])

    @classmethod
    def get_parent_models(cls):
        result = []
        for field_name in cls.get_possible_parent_field():
            field = cls._fields[field_name]
            result.append((field.model_name, field.string))
        return result

    @classmethod
    def get_parent(cls, premiums, name):
        cursor = Transaction().cursor
        premium_table = cls.__table__()
        models, columns = [], []
        for field_name in cls.get_possible_parent_field():
            field = cls._fields[field_name]
            models.append(field.model_name)
            columns.append(Column(premium_table, field_name))

        cursor.execute(*premium_table.select(premium_table.id, *columns,
                where=premium_table.id.in_([x.id for x in premiums])))

        result = {}
        for elem in cursor.fetchall():
            for model_name, value in zip(models, elem[1:]):
                if value:
                    result[elem[0]] = '%s,%i' % (model_name, value)
                    break
        return result

    @classmethod
    def _get_rated_entities(cls):
        'Return list of Model names for origin Reference'
        return [
            'offered.product',
            'offered.option.description',
            'account.fee',
            ]

    @classmethod
    def get_rated_entities(cls):
        Model = Pool().get('ir.model')
        models = cls._get_rated_entities()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    def get_rec_name(self, name):
        return self.parent.rec_name

    @classmethod
    def search_main_contract(cls, name, clause):
        # Assumes main_contract cannot be null (which, even though it is not
        # enforced in the model, is still a safe assumption)
        return ['OR',
            ('contract',) + tuple(clause[1:]),
            ('option.parent_contract',) + tuple(clause[1:]),
            ('fee.contract',) + tuple(clause[1:]),
            ]

    @staticmethod
    def order_start(tables):
        table, _ = tables[None]
        return [Coalesce(table.start, datetime.date.min)]

    @classmethod
    def new_line(cls, line, start_date, end_date):
        if not line.rated_instance:
            return None
        new_instance = cls()
        new_instance.set_parent_from_line(line)
        if not new_instance.parent:
            # TODO : Should raise an error
            return None
        new_instance.rated_entity = line.rated_entity
        new_instance.start = start_date
        if getattr(new_instance.parent, 'end_date', None) and (not end_date
                or new_instance.parent.end_date < end_date):
            new_instance.end = new_instance.parent.end_date
        else:
            new_instance.end = end_date
        new_instance.amount = line.amount
        new_instance.taxes = line.taxes
        new_instance.frequency = line.frequency
        return new_instance

    def set_parent_from_line(self, line):
        for elem in self.get_possible_parent_field():
            field = self._fields[elem]
            if field.model_name == line.rated_instance.__name__:
                setattr(self, elem, line.rated_instance)
                self.parent = line.rated_instance
                break

    def duplicate_sort_key(self):
        return utils.convert_to_reference(self.rated_entity), self.start

    @classmethod
    def remove_duplicates(cls, parent, actions):
        new_list = []
        for act_name in ['keep', 'write', 'save']:
            new_list += [(act_name, elem) for elem in actions[act_name]]

        new_list.sort(key=lambda x: x[1].duplicate_sort_key())
        final_list = []
        prev_action, prev_premium = None, None
        for elem in new_list:
            action, premium = elem
            if not prev_action:
                prev_action, prev_premium = action, premium
            elif prev_premium.same_value(premium):
                prev_premium.end = premium.end
            else:
                final_list.append(prev_premium)
                prev_action, prev_premium = action, premium

        # Do not forget the final element :)
        final_list.append(prev_premium)
        setattr(parent, 'premiums', final_list)

    def same_value(self, other):
        ident_fields = ('parent', 'amount', 'frequency', 'rated_entity',
            'account')
        for elem in ident_fields:
            if getattr(self, elem) != getattr(other, elem):
                return False
        if set(self.taxes) != set(other.taxes):
            return False
        return True


class PremiumTax(model.CoopSQL):
    'Premium - Tax'

    __name__ = 'contract.premium-account.tax'

    premium = fields.Many2One('contract.premium', 'Premium',
        ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
        required=True)
