# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from itertools import groupby
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from sql import Null, Window, Literal
from sql.conditionals import Coalesce, Case
from sql.aggregate import Max, Min, Count

from trytond import backend
from trytond.i18n import gettext
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice
from trytond.pyson import Eval, If, Or, Bool, Len
from trytond.transaction import Transaction
from trytond.model import ModelView
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import model, fields
from trytond.modules.coog_core import utils, coog_date
from trytond.modules.coog_core import coog_string
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.contract import _CONTRACT_STATUS_STATES
from trytond.modules.contract import _CONTRACT_STATUS_DEPENDS
from trytond.modules.report_engine import Printable
from trytond.modules.offered.extra_data import with_extra_data


IS_PARTY = Eval('item_kind').in_(['person', 'company', 'party'])
IS_READ_ONLY = Bool(Eval('contract_status')) & (
    Eval('contract_status') != 'quote')
COVERED_READ_ONLY = IS_READ_ONLY & ~Eval('parent')
COVERED_STATUS_DEPENDS = _CONTRACT_STATUS_DEPENDS + ['parent']

POSSIBLE_EXTRA_PREMIUM_RULES = [
    ('flat', 'Montant Fixe'),
    ('rate', 'Pourcentage'),
    ]

__all__ = [
    'Contract',
    'ContractOption',
    'ContractOptionVersion',
    'CoveredElement',
    'CoveredElementVersion',
    'CoveredElementPartyRelation',
    'ExtraPremium',
    'OptionExclusionKindRelation',
    ]


class Contract(Printable):
    __name__ = 'contract'

    covered_elements = fields.One2ManyDomain('contract.covered_element',
        'contract', 'Covered Elements',
        domain=[
            ('item_desc', 'in', Eval('possible_item_desc', [])),
            ('parent', '=', None)],
        states={
            'readonly': Eval('status') != 'quote',
            'invisible': Len(Eval('possible_item_desc', [])) <= 0,
            },
        depends=['status', 'id', 'product', 'start_date', 'extra_data_values',
            'possible_item_desc'], target_not_required=True)
    possible_item_desc = fields.Function(
        fields.Many2Many('offered.item.description', None, None,
            'Possible Item Desc', states={'invisible': True}),
        'on_change_with_possible_item_desc')
    covered_element_options = fields.Function(fields.Many2Many(
            'contract.option', None, None, 'Covered Element Options'),
        'get_covered_element_options')
    initial_number_of_sub_covered_elements = fields.Function(
        fields.Integer('Initial Number of sub covered elements'),
        'get_initial_number_of_sub_covered_elements')
    multi_mixed_view = covered_elements

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'manage_extra_premium': {},
                'create_extra_premium': {},
                'generic_send_letter': {},
                'propagate_exclusions': {},
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        # Migration from 1.6: Drop last_renewed
        table = TableHandler(cls, module_name)
        if table.column_exist('last_renewed'):
            table.drop_column('last_renewed')
        # Migration from 1.8: Drop Expenses
        if TableHandler.table_exist('expense'):
            TableHandler.drop_table('expense', 'expense')
            TableHandler.drop_table('expense.kind', 'expense_kind')

        super(Contract, cls).__register__(module_name)

    def _get_calculate_targets(self, model_type):
        if model_type == 'covered_elements':
            self.covered_elements = self.covered_elements
            return list(self.covered_elements)
        instances = super(Contract, self)._get_calculate_targets(model_type)
        if model_type in ('options', 'covered_element_options'):
            self.covered_elements = self.covered_elements
            for covered_element in self.covered_elements:
                instances += [option for option in covered_element.options
                    if option.status in ('active', 'quote')]
                covered_element.options = covered_element.options
        return instances

    def get_all_options(self):
        return (super(Contract, self).get_all_options()
            + self.covered_element_options)

    @fields.depends('product')
    def on_change_product(self):
        super(Contract, self).on_change_product()
        if self.product:
            self.possible_item_desc = list(self.product.item_descriptors)

    @fields.depends('product')
    def on_change_with_possible_item_desc(self, name=None):
        if not self.product:
            return []
        return [x.id for x in self.product.item_descriptors]

    @classmethod
    def get_covered_element_options(cls, contracts, name):
        pool = Pool()
        covered_element = pool.get('contract.covered_element').__table__()
        option = pool.get('contract.option').__table__()
        cursor = Transaction().connection.cursor()

        res = {x.id: [] for x in contracts}
        query_table = option.join(covered_element,
            condition=option.covered_element == covered_element.id)
        where_clause = option.status != 'declined'
        for contract_slice in grouped_slice(contracts):
            id_clause = covered_element.contract.in_(
                [x.id for x in contract_slice])
            cursor.execute(*query_table.select(
                    covered_element.contract, option.id,
                    where=where_clause & id_clause))

            for contract, option in cursor.fetchall():
                res[contract].append(option)
        return res

    @classmethod
    def get_initial_number_of_sub_covered_elements(cls, contracts, name):
        if backend.name() == 'sqlite':
            result = {x.id: 0 for x in contracts}
            for contract in contracts:
                subs = [x for x in contract.covered_elements if x.parent
                    and (x.manual_start_date or datetime.date.min) <
                    contract.initial_start_date]
                result[contract.id] = len(subs)
            return result
        pool = Pool()

        activation_history = pool.get('contract.activation_history').__table__()
        CoveredElement = pool.get('contract.covered_element')
        covered_element = CoveredElement.__table__()
        sub_covered_element = CoveredElement.__table__()

        cursor = Transaction().connection.cursor()
        win_query = activation_history.select(
            activation_history.contract.as_('id'),
            activation_history.start_date,
            Min(activation_history.start_date, window=Window(
                    [activation_history.contract])).as_('min_start'),
            where=activation_history.active
            )
        query = win_query.join(covered_element,
            condition=covered_element.contract == win_query.id
            ).join(sub_covered_element,
                condition=covered_element.id == sub_covered_element.parent)
        cursor.execute(*query.select(win_query.id,
                Count(sub_covered_element.id),
                where=(win_query.start_date == win_query.min_start) &
                win_query.id.in_([x.id for x in contracts]) &
                (sub_covered_element.contract == Null) &
                (Coalesce(sub_covered_element.manual_start_date,
                        datetime.date.min) <= win_query.start_date),
                group_by=[win_query.id]))
        result = {x.id: 0 for x in contracts}
        for contract_id, sub_element_count in cursor.fetchall():
            result[contract_id] = sub_element_count
        return result

    def update_for_termination(self):
        super(Contract, self).update_for_termination()
        sub_status = self.sub_status
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                if option.status in ('active', 'hold'):
                    option.status = 'terminated'
                    option.sub_status = sub_status
                elif option.status == 'quote':
                    option.status = 'declined'
            covered_element.options = covered_element.options
        self.covered_elements = self.covered_elements

    def clean_up_versions(self):
        super(Contract, self).clean_up_versions()

        CoveredElement = Pool().get('contract.covered_element')
        if self.covered_elements:
            to_write = []
            for covered_element in self.covered_elements:
                covered_element.clean_up_versions(self)
                to_write += [[covered_element], covered_element._save_values]
            if to_write:
                CoveredElement.write(*to_write)

    def check_at_least_one_covered(self):
        for covered in self.covered_elements:
            if not covered.check_at_least_one_covered():
                self.append_functional_error(
                    ValidationError(gettext(
                            'contract_insurance.msg_need_option',
                            covered=covered.get_rec_name(''))))

    def notify_end_date_change(self, value):
        super(Contract, self).notify_end_date_change(value)
        for element in self.covered_elements:
            for option in element.options:
                option.notify_contract_end_date_change(value)
            element.options = element.options
            element.notify_contract_end_date_change(value)
        self.covered_elements = self.covered_elements

    def notify_start_date_change(self, value):
        super(Contract, self).notify_start_date_change(value)
        for element in self.covered_elements:
            for option in element.options:
                option.notify_contract_start_date_change(value)
            element.options = element.options
        self.covered_elements = self.covered_elements

    def check_options_dates(self):
        super(Contract, self).check_options_dates()
        Pool().get('contract.option').check_dates([option
                for option in self.covered_element_options])

    @classmethod
    def get_coverages(cls, product):
        if not product:
            return []
        return [x for x in product.coverages if x.is_service]

    def init_covered_elements(self):
        for elem in self.covered_elements:
            elem.init_options(self.product, self.start_date)
        self.covered_elements = list(self.covered_elements)

    @classmethod
    def search_contract(cls, product, subscriber, at_date):
        return cls.search([
                ('product', '=', product),
                ('subscriber', '=', subscriber),
                ('start_date', '<=', at_date)])

    def check_contract_extra_data(self):
        ExtraData = Pool().get('extra_data')
        for extra_data in self.extra_datas:
            ExtraData.check_extra_data(extra_data, 'extra_data_values')

    def check_contract_option_extra_data(self):
        ExtraData = Pool().get('extra_data')
        for option in self.options:
            ExtraData.check_extra_data(option.current_version, 'extra_data')

    def check_covered_element_extra_data(self):
        ExtraData = Pool().get('extra_data')
        for covered_element in self.covered_elements:
            ExtraData.check_extra_data(covered_element.current_version,
                'extra_data')

    def check_covered_element_option_extra_data(self):
        ExtraData = Pool().get('extra_data')
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                ExtraData.check_extra_data(option.current_version,
                    'extra_data')

    @classmethod
    def update_contract_after_import(cls, contracts):
        super(Contract, cls).update_contract_after_import(contracts)
        for contract in contracts:
            contract.init_covered_elements()
        cls.save(contracts)

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_extra_premium')
    def manage_extra_premium(cls, instances):
        pass

    @classmethod
    @ModelView.button_action('contract_insurance.act_create_extra_premium')
    def create_extra_premium(cls, instances):
        pass

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_exclusion')
    def propagate_exclusions(cls, instances):
        pass

    def get_publishing_context(self, cur_context):
        result = super(Contract, self).get_publishing_context(cur_context)
        at_date = cur_context.get('Date', None)
        result['Insurers'] = [x.coverage.get_insurer(at_date).party
            for x in self.options if x.coverage.get_insurer(at_date)]
        return result

    def get_option_for_coverage_at_date(self, coverage):
        for option in self.options:
            if option.coverage == coverage:
                return option
        return None

    def get_contact(self):
        return self.subscriber

    def get_main_contact(self):
        return self.get_policy_owner()

    def get_sender(self):
        return self.company.party

    def get_doc_template_kind(self):
        kinds = ['contract']
        if self.status == 'quote':
            kinds.append('quote_contract')
        elif self.status == 'active':
            kinds.append('active_contract')
        return kinds

    def get_template_holders_sub_domains(self):
        return super(Contract, self).get_template_holders_sub_domains() + [
            [('products', '=', self.product.id)]]

    def get_maximum_end_date(self):
        date = super(Contract, self).get_maximum_end_date()
        dates = [date] if date else []
        for element in self.covered_elements:
            for option in element.options:
                possible_end_dates = option.get_possible_end_date()
                if possible_end_dates:
                    dates.append(min(possible_end_dates.values()))
                else:
                    return None
        if dates:
            return max(dates)
        else:
            return None

    def set_extra_data_value(self, key, value):
        super(Contract, self).set_extra_data_value(key, value)
        for covered in self.covered_elements:
            covered.set_extra_data_value(key, value)
        self.covered_elements = self.covered_elements

    def get_parties(self, name):
        parties = super(Contract, self).get_parties(name)
        parties += [x.party.id for x in self.covered_elements if x.party]
        return list(set(parties))

    def do_activate(self):
        super(Contract, self).do_activate()
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                option.activate()
            covered_element.options = list(covered_element.options)
        self.covered_elements = list(self.covered_elements)

    def init_contract(self, product, party, contract_dict=None):
        CoveredElement = Pool().get('contract.covered_element')
        super(Contract, self).init_contract(product, party, contract_dict)
        if not contract_dict:
            return
        if 'covered_elements' not in contract_dict:
            return
        item_descs = product.item_descriptors
        if len(item_descs) != 1:
            return
        item_desc = item_descs[0]
        self.covered_elements = []
        for cov_dict in contract_dict['covered_elements']:
            covered_element = CoveredElement()
            covered_element.contract = self
            covered_element.init_covered_element(product, item_desc, cov_dict)
            self.covered_elements.append(covered_element)

    @classmethod
    def _export_skips(cls):
        return super(Contract, cls)._export_skips() | set(['multi_mixed_view'])

    @classmethod
    def search_parties(cls, name, clause):
        return ['OR',
            super(Contract, cls).search_parties(name, clause),
            ('covered_elements.party.id',) + tuple(clause[1:]),
            ]

    def get_covered_elements_at_date(self, at_date=None):
        if not at_date:
            at_date = utils.today()
        return [covered for covered in self.covered_elements
            if covered.is_covered_at_date(at_date)]

    def decline_options(self, reason):
        super(Contract, self).decline_options(reason)
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                option.decline_option(reason)
            covered_element.options = covered_element.options
        self.covered_elements = self.covered_elements

    def get_report_style_content(self, at_date, template):
        if self.product:
            return self.product.get_report_style_content(at_date, template,
                self)

    def get_gdpr_data(self):
        res = super(Contract, self).get_gdpr_data()
        Party = Pool().get('party.party')
        res[Party._label_gdpr(self, 'covered_elements')] = [
            coog_string.translate_value(covered.party, 'full_name')
            for covered in self.covered_elements if covered.party]
        return res

    @classmethod
    def void(cls, contracts, void_reason):
        pool = Pool()
        Option = pool.get('contract.option')
        options = []
        for contract in contracts:
            for covered_element in contract.covered_elements:
                for option in covered_element.options:
                    options.append(option)

        Option.write(options, {'status': 'void'})
        super().void(contracts, void_reason)

    def get_summary_content(self, label, at_date=None, lang=None, path=None):
        res = super(Contract, self).get_summary_content(label, at_date, lang)
        if self.covered_elements and self.status == 'quote':
            res[1].append(coog_string.get_field_summary(self,
                'covered_elements', False, at_date, lang))
        return res

    def get_age_calculation_rule(self):
        # return 'at_end_of_month', None
        # return 'at_given_day_of_year', datetime.date(2000, 1, 1)
        return 'real', None

    def calculate_age(self, birth_date, at_date):
        kind, date_ref = self.get_age_calculation_rule()
        if kind == 'at_end_of_month':
            birthday_month_after = birth_date + relativedelta(months=1)
            year, month, _ = birthday_month_after.timetuple()[0:3]
            birth_date = datetime.date(year, month, 1)
        elif kind == 'at_given_day_of_year':
            birth_date = datetime.date(birth_date.year, date_ref.month,
                date_ref.day)
        return relativedelta(at_date, birth_date).years

    def check_covered_elements(self):
        for covered_element in self.covered_elements:
            covered_element.item_desc.check_covered_element(covered_element)

    def before_activate(self):
        self.check_covered_elements()
        super().before_activate()


class ContractOption(Printable):
    __name__ = 'contract.option'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', ondelete='CASCADE', select=True,
        states={
            'readonly': Eval('contract_status') != 'quote',
            'invisible': ~Eval('covered_element'),
            }, depends=_CONTRACT_STATUS_DEPENDS)
    exclusions = fields.One2Many('contract.option.exclusion',
        'option', 'Exclusions', delete_missing=True,
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    extra_premiums = fields.One2Many('contract.option.extra_premium',
        'option', 'Extra Premiums',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS,
        delete_missing=True)
    extra_premium_discounts = fields.One2ManyDomain(
        'contract.option.extra_premium', 'option', 'Discounts',
        domain=[('motive.is_discount', '=', True)],
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS,
        delete_missing=True)
    extra_premium_increases = fields.One2ManyDomain(
        'contract.option.extra_premium', 'option', 'Increases',
        domain=[('motive.is_discount', '=', False)],
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS,
        delete_missing=True)
    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')
    parent_option = fields.Function(
        fields.Many2One('contract.option', 'Parent Covered Data'),
        'on_change_with_parent_option')
    item_desc = fields.Function(
        fields.Many2One('offered.item.description', 'Item Description'),
        'on_change_with_item_desc')
    extra_premiums_allowed = fields.Function(
        fields.Boolean('Extra premium allowed'),
        'getter_extra_premiums_allowed')
    exclusions_allowed = fields.Function(
        fields.Boolean('Exclusions allowed'),
        'getter_exclusions_allowed')

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('check_option_parent_field', utils.multi_column_required(
                    table, ['contract', 'covered_element']),
                'An option must have either a contract or a covered element'),
            ]
        cls._buttons.update({
                'propagate_extra_premiums': _CONTRACT_STATUS_STATES,
                'propagate_exclusions': _CONTRACT_STATUS_STATES,
                })
        for fname in ['extra_premiums', 'extra_premium_discounts',
                'extra_premium_increases']:
            cur_state = getattr(cls, fname).states.get('invisible', False)
            getattr(cls, fname).states['invisible'] = cur_state | ~Eval(
                'extra_premiums_allowed')
            getattr(cls, fname).depends.append('extra_premiums_allowed')
        cls.exclusions.states['invisible'] = cls.exclusions.states.get(
            'invisible', False) | ~Eval('exclusions_allowed')
        cls.exclusions.depends.append('exclusions_allowed')

    @classmethod
    def validate(cls, options):
        super(ContractOption, cls).validate(options)

        covereds = Pool().get('contract.covered_element').browse(
            list({x.covered_element.id for x in options if x.covered_element}))

        with model.error_manager():
            for covered in covereds:
                cls.check_overlap(covered.options, covered.rec_name)
                covered.check_options_dates()

    def get_full_name(self, name):
        return super(ContractOption, self).get_full_name(name)

    def get_initial_start_date(self, name):
        if (not self.manual_start_date and self.covered_element
                and self.covered_element.manual_start_date):
            return self.covered_element.manual_start_date
        return super(ContractOption, self).get_initial_start_date(name)

    @classmethod
    def get_start_date(cls, options, names):
        res = super(ContractOption, cls).get_start_date(options, names)
        for option in options:
            if (res['start_date'][option.id] and option.covered_element
                    and option.covered_element.manual_start_date):
                res['start_date'][option.id] = max(
                    option.covered_element.manual_start_date,
                    res['start_date'][option.id])
        return res

    @classmethod
    def _export_skips(cls):
        return super(ContractOption, cls)._export_skips() | {'exclusions',
            'extra_premium_discounts', 'extra_premium_increases'}

    @fields.depends('item_desc')
    def on_change_coverage(self):
        super(ContractOption, self).on_change_coverage()
        self.exclusions_allowed = (self.coverage and
            self.coverage.with_exclusions)
        self.extra_premiums_allowed = (self.coverage and
            self.coverage.with_extra_premiums)

    @fields.depends('covered_element', 'item_desc')
    def on_change_covered_element(self):
        if not self.covered_element:
            self.item_desc = None
        else:
            self.item_desc = self.covered_element.item_desc

    @fields.depends('covered_element', 'start_date')
    def on_change_with_appliable_conditions_date(self, name=None):
        if not self.covered_element:
            return super(ContractOption,
                self).on_change_with_appliable_conditions_date()
        contract = getattr(self.covered_element, 'contract', None)
        return (contract.appliable_conditions_date if
            contract else self.start_date)

    def on_change_with_icon(self, name=None):
        if getattr(self, 'status', '') in ('terminated', 'void'):
            return 'umbrella-grey-cancel'
        elif getattr(self, 'status', '') == 'active':
            return 'umbrella-green'
        return 'umbrella-black'

    @fields.depends('covered_element')
    def on_change_with_item_desc(self, name=None):
        if self.covered_element:
            return self.covered_element.item_desc.id
        else:
            return None

    @fields.depends('covered_element', 'coverage')
    def on_change_with_parent_option(self, name=None):
        if not self.covered_element or not self.covered_element.parent:
            return None
        for option in self.covered_element.parent.options:
            if option.coverage == self.coverage:
                return option.id

    @fields.depends('covered_element')
    def on_change_with_product(self, name=None):
        if self.covered_element and self.covered_element.contract:
            return self.covered_element.contract.product.id
        return super(ContractOption, self).on_change_with_product(name)

    @fields.depends('parent_contract')
    def on_change_with_contract_status(self, name=None):
        return self.parent_contract.status if self.parent_contract else ''

    def getter_exclusions_allowed(self, name):
        if not self.coverage:
            return False
        return self.coverage.with_exclusions

    def getter_extra_premiums_allowed(self, name):
        if not self.coverage:
            return False
        return self.coverage.with_extra_premiums

    @classmethod
    def getter_parent_contract(cls, instances, name):
        pool = Pool()
        CoveredElement = pool.get('contract.covered_element')
        option = cls.__table__()
        covered = CoveredElement.__table__()

        options_without_covered, options_with_covered = [], []
        for instance in instances:
            if instance.covered_element:
                options_with_covered.append(instance)
            else:
                options_without_covered.append(instance)

        result = {x.id: None for x in instances}
        result.update(super(ContractOption, cls).getter_parent_contract(
                options_without_covered, name))

        cursor = Transaction().connection.cursor()
        query = option.join(covered,
            condition=option.covered_element == covered.id
            )

        for cur_slice in grouped_slice(options_with_covered):
            cursor.execute(*query.select(option.id, covered.contract,
                    where=option.id.in_([x.id for x in cur_slice])
                    ))

            for option_id, contract in cursor.fetchall():
                result[option_id] = contract

        return result

    @classmethod
    def search_parent_contract(cls, name, clause):
        domain = super(ContractOption, cls).search_parent_contract(
            name, clause)
        columns = clause[0].split('.')
        if len(columns) == 1:
            new_clause = [('covered_element.contract',) + tuple(clause[1:])]
        else:
            columns_to_add = '.'.join(columns[1:])
            new_clause = [('covered_element.contract.' + columns_to_add,) +
                tuple(clause[1:])]
        return ['OR', domain, new_clause]

    @classmethod
    def searcher_start_date(cls, name, clause):
        return ['OR',
            [('manual_start_date',) + tuple(clause[1:])],
            [
                ('manual_start_date', '=', None),
                ('contract', '!=', None),
                ('contract.start_date',) + tuple(clause[1:]),
            ],
            [
                ('manual_start_date', '=', None),
                ('covered_element', '!=', None),
                ['OR',
                    [('covered_element.contract.start_date',)
                    + tuple(clause[1:])],
                    [('covered_element.manual_start_date',) + tuple(clause[1:])]
                ],
            ],
        ]

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_extra_premium')
    def propagate_extra_premiums(cls, options):
        pass

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_exclusion')
    def propagate_exclusions(cls, options):
        pass

    @classmethod
    def new_option_from_coverage(cls, coverage, product, start_date, **kwargs):
        new_option = super(ContractOption, cls).new_option_from_coverage(
            coverage, product, start_date, **kwargs)
        new_option.item_desc = kwargs.get('item_desc', None)
        new_option.on_change_coverage()
        return new_option

    def init_from_covered_element(self, covered_element):
        self.covered_element = covered_element

    def get_currency(self):
        if self.covered_element:
            return self.covered_element.currency
        return super(ContractOption, self).get_currency()

    def get_covered_element(self, from_name=None, party=None):
        # TODO : move to claim ?
        if self.covered_element:
            return self.covered_element.get_covered_element(from_name, party)

    def get_option(self, from_name=None, party=None):
        # TODO : move to claim / remove
        covered_element = self.get_covered_element(from_name, party)
        if not covered_element:
            return
        for option in covered_element.option:
            if option.option == self.option:
                return option

    def _expand_tree(self, name):
        return True

    def init_dict_for_rule_engine(self, args):
        args['option'] = self
        covered_element = getattr(self, 'covered_element', None)
        if covered_element is None:
            return super(ContractOption, self).init_dict_for_rule_engine(args)
        covered_element.init_dict_for_rule_engine(args)
        self.coverage.init_dict_for_rule_engine(args)

    def get_publishing_values(self):
        result = super(ContractOption, self).get_publishing_values()
        result['offered'] = self.coverage
        return result

    def notify_contract_end_date_change(self, new_end_date):
        super(ContractOption, self).notify_contract_end_date_change(
            new_end_date)
        for extra_prem in self.extra_premiums:
            extra_prem.notify_contract_end_date_change(new_end_date)
        self.extra_premiums = self.extra_premiums

    def notify_contract_start_date_change(self, new_start_date):
        super(ContractOption, self).notify_contract_start_date_change(
            new_start_date)
        for extra_prem in self.extra_premiums:
            extra_prem.notify_contract_start_date_change(new_start_date)
        self.extra_premiums = self.extra_premiums

    def get_contact(self):
        return self.covered_element.party or self.contract.get_contact()

    def get_object_for_contact(self):
        return self.covered_element.party or self.contract.get_contact()

    def get_sender(self):
        return self.covered_element.party or self.contract.get_contact()

    @classmethod
    def check_dates(cls, options):
        Date = Pool().get('ir.date')
        super(ContractOption, cls).check_dates(options)
        for option in options:
            if (option.covered_element and
                    option.covered_element.manual_start_date and
                    option.manual_start_date and
                    option.covered_element.manual_start_date >
                    option.manual_start_date):
                raise ValidationError(gettext(
                        'contract_insurance'
                        '.msg_option_start_anterior_to_covered_start',
                        manual_start_date=Date.date_as_string(
                            option.manual_start_date),
                        covered_start_date=Date.date_as_string(
                            option.covered_element.manual_start_date),
                        option=option.rec_name,
                        contract=option.parent_contract.rec_name))

    def get_sister_option(self, coverage_code):
        options = []
        if self.covered_element:
            options = self.covered_element.options
        elif self.contract:
            options = self.contract.options
        for option in options:
            if option.coverage.code == coverage_code:
                return option


class ContractOptionVersion(metaclass=PoolMeta):
    __name__ = 'contract.option.version'

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        Option = pool.get('contract.option')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        option = Option.__table__()
        version = cls.__table__()

        super(ContractOptionVersion, cls).__register__(module)

        # Migration from 1.4 : Move contract.option->extra_data in
        # contract.option.version->extra_data
        option_h = TableHandler(Option, module)
        if option_h.column_exist('extra_data'):
            update_data = option.select(option.id.as_('option'),
                Coalesce(option.extra_data, '{}').as_('extra_data'))
            cursor.execute(*version.update(
                    columns=[version.extra_data],
                    values=[update_data.extra_data],
                    from_=[update_data],
                    where=update_data.option == version.option))
            option_h.drop_column('extra_data')


class CoveredElement(Printable,
        model.with_local_mptt('contract'),
        model.CoogView,
        with_extra_data(['covered_element'], schema='item_desc',
            field_name='current_extra_data', field_string='Current Extra Data',
            getter_name='get_current_version', setter_name='setter_void'),
        model.ExpandTreeMixin, ModelCurrency):
    'Covered Element'
    '''
        Covered elements represents anything which is covered by at least one
        option of the contract.
        It has a list of covered datas which describes which options covers
        element and in which conditions.
        It could contains recursively sub covered element (fleet or population)
    '''

    __name__ = 'contract.covered_element'
    _func_key = 'party_code'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        states={'invisible': ~Eval('contract')}, depends=['contract'],
        select=True)
    contract_status = fields.Function(
        fields.Char('Contract Status'),
        'on_change_with_contract_status')
    versions = fields.One2Many('contract.covered_element.version',
        'covered_element', 'Versions', delete_missing=True,
        order=[('start', 'ASC')], states={'readonly': COVERED_READ_ONLY},
        depends=COVERED_STATUS_DEPENDS)
    covered_relations = fields.Many2Many('contract.covered_element-party',
        'covered_element', 'party_relation', 'Covered Relations', domain=[
            'OR',
            [('from_party', '=', Eval('party'))],
            [('to_party', '=', Eval('party'))],
            ],
        states={
            'invisible': ~IS_PARTY,
            'readonly': IS_READ_ONLY,
            }, depends=['party', 'contract_status', 'item_kind'])
    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='RESTRICT', required=True, states={
            'readonly': COVERED_READ_ONLY},
        depends=COVERED_STATUS_DEPENDS)
    show_name = fields.Function(fields.Boolean('Show Name'),
        'on_change_with_show_name')
    name = fields.Char('Name', states={
            'invisible': ~Eval('show_name'),
            'readonly': COVERED_READ_ONLY,
            },
        depends=['party', 'item_kind', 'contract_status', 'parent',
            'show_name'])
    options = fields.One2ManyDomain('contract.option', 'covered_element',
        'Options', domain=[
            ('coverage.products', '=', Eval('product')),
            ('coverage.item_desc', '=', Eval('item_desc')),
            ('status', '!=', 'declined'),
            ], states={'readonly': COVERED_READ_ONLY},
        depends=['item_desc', 'product', 'contract_status', 'parent'],
        target_not_required=True,
        order=[('coverage.sequence', 'ASC NULLS LAST'), ('start_date', 'ASC')])
    declined_options = fields.One2ManyDomain('contract.option',
        'covered_element', 'Declined Options',
        domain=[('status', '=', 'declined')], target_not_required=True,
        order=[('coverage.sequence', 'ASC NULLS LAST'), ('start_date', 'ASC')],
        readonly=True)
    all_options = fields.One2Many('contract.option', 'covered_element',
        'Options', target_not_required=True, delete_missing=True,
        order=[('coverage.sequence', 'ASC NULLS LAST'), ('start_date', 'ASC')],
        readonly=True)
    parent = fields.Many2One('contract.covered_element', 'Parent',
        domain=[('contract', '=', Eval('contract'))],
        depends=['contract'], ondelete='CASCADE', select=True)
    party = fields.Many2One('party.party', 'Actor', domain=[
            If(
                Eval('item_kind') == 'person',
                ('is_person', '=', True),
                ()),
            If(
                Eval('item_kind') == 'company',
                ('is_person', '=', False),
                ())],
        states={
            'invisible': ~IS_PARTY,
            'required': IS_PARTY,
            'readonly': COVERED_READ_ONLY,
            }, ondelete='RESTRICT',
        depends=['item_kind', 'contract_status', 'parent'], select=True)
    sub_covered_elements = fields.One2Many('contract.covered_element',
        'parent', 'Sub Covered Elements',
        states={
            'invisible': ~Eval('has_sub_covered_elements'),
            },
        depends=['has_sub_covered_elements'],
        target_not_required=True)
    has_sub_covered_elements = fields.Function(
        fields.Boolean('Has sub-covered elements'),
        'getter_has_sub_covered_elements')
    start_date = fields.Function(
        fields.Date('Start Date'),
        'get_start_date')
    manual_start_date = fields.Date('Start Date', states={
            'invisible': ~Eval('parent'),
            'required': Bool(Eval('parent', False)),
            'readonly': COVERED_READ_ONLY,
            }, depends=['parent', 'contract_status'])
    manual_end_date = fields.Date('Manual End Date', states={
            'invisible': ~Eval('parent'),
            'readonly': COVERED_READ_ONLY,
            }, depends=['parent', 'contract_status'])
    end_date = fields.Function(
        fields.Date('End Date', states={'invisible': ~Eval('parent')},
            depends=['parent']),
        'getter_end_date')
    end_reason = fields.Many2One('covered_element.end_reason', 'End Reason',
        ondelete='RESTRICT', domain=[If(~Eval('parent'), [],
            [('item_descs', '=', Eval('item_desc'))])], states={
            'invisible': ~Eval('manual_end_date'),
            'required': Bool(Eval('manual_end_date', False)),
            'readonly': COVERED_READ_ONLY,
            }, depends=['item_desc', 'manual_end_date', 'parent',
                'contract_status'])
    current_version = fields.Function(
        fields.Many2One('contract.covered_element.version', 'Current Version'),
        'get_current_version')
    covered_name = fields.Function(
        fields.Char('Name'),
        'on_change_with_covered_name')
    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')
    is_person = fields.Function(
        fields.Boolean('Is Person', states={'invisible': True}),
        'on_change_with_is_person')
    item_kind = fields.Function(
        fields.Char('Item Kind', states={'invisible': True}),
        'on_change_with_item_kind')
    party_extra_data = fields.Function(
        fields.Dict('extra_data', 'Party Extra Data',
            states={'invisible': Or(~IS_PARTY, ~Eval('party_extra_data'))},
            depends=['party_extra_data', 'item_kind']),
        'get_party_extra_data', 'set_party_extra_data')
    party_extra_data_string = party_extra_data.translated('party_extra_data')
    product = fields.Function(
        fields.Many2One('offered.product', 'Product'),
        'on_change_with_product')
    party_code = fields.Function(
        fields.Char('Party Code'), 'get_party_code',
        searcher='search_party_code')
    affiliated_to = fields.Function(
        fields.Many2One('party.party', 'Affiliated To',
            help='The company which is the closest (in terms of parent '
            'covered elements / subscribers) to the covered'),
        'getter_affiliated_to', searcher='search_affiliated_to')
    all_parents = fields.Function(
        fields.Many2Many('contract.covered_element', None, None, 'All Parents',
            help='All parents of the covered element linked to the same '
            'contract'),
        'getter_all_parents', searcher='search_all_parents')

    multi_mixed_view = options

    @classmethod
    def __setup__(cls):
        super(CoveredElement, cls).__setup__()
        cls.current_extra_data.states['readonly'] = COVERED_READ_ONLY
        cls.current_extra_data.depends += ['contract_status', 'versions',
            'parent']

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        # Migration from 2.0: Always store the contract field
        to_migrate = False
        if TableHandler.table_exist('contract_covered_element'):
            to_migrate = not table.column_exist('left')

        super(CoveredElement, cls).__register__(module_name)

        if to_migrate:
            # Initialize Tree
            contract = Pool().get('contract').__table__()
            cursor = Transaction().connection.cursor()
            cursor.execute(*contract.select(contract.id))
            for contract, in cursor.fetchall():
                cls._update_local_mptt_one(contract, None)

        # Migration from 1.12
        table.drop_constraint('party_unique')

    @classmethod
    def __post_setup__(cls):
        super(CoveredElement, cls).__post_setup__()
        Pool().get('extra_data')._register_extra_data_provider(cls,
            'find_extra_data_value', ['covered_element'])
        Pool().get('extra_data')._register_extra_data_provider(cls,
            'find_package_extra_data_value', ['package'])

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('party.full_name',) + tuple(clause[1:])],
            [('item_desc.rec_name',) + tuple(clause[1:])],
            [('name',) + tuple(clause[1:])],
            ]

    @classmethod
    def view_attributes(cls):
        return super(CoveredElement, cls).view_attributes() + [(
                '/form/notebook/page[@id="covered_relations"]',
                'states',
                {'invisible': ~Eval('item_kind').in_(
                        ['person', 'company', 'party'])}
                ), (
                '/form/notebook/page[@id="sub_elements"]',
                'states',
                {'invisible': ~Eval('has_sub_covered_elements')}
                )]

    @classmethod
    def functional_skips_for_duplicate(cls):
        return set([])

    @classmethod
    def _export_light(cls):
        return (super(CoveredElement, cls)._export_light() |
            set(['item_desc', 'product', 'contract', 'covered_relations']))

    @classmethod
    def _export_skips(cls):
        return super(CoveredElement, cls)._export_skips() | {
            'multi_mixed_view', 'all_options', 'left', 'right'}

    @classmethod
    def add_func_key(cls, values):
        pool = Pool()
        Party = pool.get('party.party')
        parties = Party.search_for_export_import(values['party'])
        if not parties:
            values['_func_key'] = ''
        elif len(parties) == 1:
            values['_func_key'] = parties[0].code
        else:
            raise ValidationError(
                gettext('contract_insurance.msg_too_many_party'))

    def get_synthesis_status(self):
        return '[%s]' % coog_string.translate_value(
            self.contract, 'status') if self.contract else ''

    def get_synthesis_rec_name(self):
        dates = self.get_synthesis_dates()
        status = self.get_synthesis_status()
        product = '[%s]' % self.contract.product.rec_name if self.contract \
            else ''
        number = (self.contract.contract_number or self.contract.quote_number
            if self.contract else '')
        if self.contract_status in ['void', 'declined']:
            return '%s %s %s' % (number, product, status)
        else:
            return '%s %s %s %s' % (number, product, status, dates)

    @classmethod
    def copy(cls, instances, default=None):
        default = {} if default is None else default.copy()
        if Transaction().context.get('copy_mode', '') == 'functional':
            skips = cls._export_skips() | cls.functional_skips_for_duplicate()
            for x in skips:
                default.setdefault(x, None)
        return super(CoveredElement, cls).copy(instances, default=default)

    @classmethod
    def validate(cls, covered_elements):
        super(CoveredElement, cls).validate(covered_elements)
        with model.error_manager():
            cls.check_party_overlaps(covered_elements)
            for covered_element in covered_elements:
                covered_element.check_options_dates()
                covered_element.check_overlapping()

    def check_overlapping(self):
        """
        Check overlapping between covered elements with
        the same parent and same party
        """
        parent = self.parent
        party = self.party

        if not parent or not party:
            return
        cursor = Transaction().connection.cursor()
        Covered = Pool().get('contract.covered_element')
        covered_1 = Covered.__table__()
        covered_2 = Covered.__table__()
        tables = {}
        tables['covered_1'] = covered_1
        tables['covered_2'] = covered_2

        join_condition = ((covered_1.party == covered_2.party) &
            (covered_1.parent == covered_2.parent) &
            (covered_1.parent == parent.id) &
            (covered_1.party == party.id))
        query = covered_1.join(covered_2, condition=join_condition)

        where_clause = self.check_overlapping_where_clause(tables)
        cursor.execute(*query.select(covered_1.id,
                where=where_clause)
            )

        res = [x for x in cursor.fetchall()]
        if res:
            self.append_functional_error(
                ValidationError(gettext(
                        'contract_insurance.msg_overlapped_elements')))

    def check_overlapping_where_clause(self, tables):
        covered_1 = tables['covered_1']
        covered_2 = tables['covered_2']
        cov_1_start = Coalesce(covered_1.manual_start_date, datetime.date.min)
        cov_1_end = Coalesce(covered_1.manual_end_date, datetime.date.max)
        cov_2_start = Coalesce(covered_2.manual_start_date, datetime.date.min)
        where_clause = ((covered_2.id != covered_1.id) &
            (cov_2_start >= cov_1_start) &
            (cov_2_start <= cov_1_end))
        return where_clause

    @classmethod
    def check_party_overlaps(cls, covered_elements):
        Contract = Pool().get('contract')
        contracts = []
        for cov in covered_elements:
            if cov.parent or not cov.party or not cov.contract:
                continue
            contracts.append(cov.contract.id)
        if not contracts:
            return
        covered = cls.__table__()
        cursor = Transaction().connection.cursor()

        query = covered.select(covered.contract,
                where=((covered.parent == Null) & (covered.party != Null
                    ) & (covered.contract.in_(contracts))),
                group_by=[covered.contract, covered.party],
                having=Count(covered.contract) > 1)
        cursor.execute(*query)
        res = {x for x, in cursor.fetchall()}

        def _group_by_contract_party(c):
            return (c.contract, c.party)

        if res:
            contracts = Contract.browse(res)
            for contract in contracts:
                covereds = sorted(contract.covered_elements,
                    key=_group_by_contract_party)
                for key, sub_covereds in groupby(covereds,
                        key=_group_by_contract_party):
                    cls._check_covereds_overlap(contract, list(
                            sub_covereds))

    def check_options_dates(self):
        Option = Pool().get('contract.option')
        Option.check_overlap(list(self.options), self.rec_name)
        if self.manual_start_date and any(
                x.manual_start_date < self.manual_start_date
                for x in self.options if x.manual_start_date):
            self.append_functional_error(
                ValidationError(gettext(
                        'contract_insurance.msg_bad_option_start',
                        covered=self.rec_name)))
        if self.manual_end_date and any(
                x.manual_end_date > self.manual_end_date
                for x in self.options if x.manual_end_date):
            self.append_functional_error(
                ValidationError(gettext(
                        'contract_insurance.msg_bad_option_end',
                        covered=self.rec_name)))

    @classmethod
    def _check_covereds_overlap(cls, contract, sub_covereds):
        sub_covereds = [
            x for x in sub_covereds
            if any(o.status != 'void' for o in x.options)]
        n_covered = len(sub_covereds)
        if n_covered > 1:
            sub_covereds = sorted(
                sub_covereds, key=lambda x: x.start_date)
            for idx, covered in enumerate(sub_covereds):
                next_covered = None
                if idx < n_covered - 1:
                    next_covered = sub_covereds[idx + 1]
                if not next_covered:
                    break
                if coog_date.period_overlap(covered.initial_start_date,
                        covered.end_date, next_covered.initial_start_date,
                        next_covered.end_date or datetime.date.max):
                    cls.append_functional_error(
                        ValidationError(gettext(
                                'contract_insurance.msg_duplicate_covered',
                                contract=contract.rec_name)))

    @classmethod
    def default_versions(cls):
        return [Pool().get(
                'contract.covered_element.version').get_default_version()]

    @fields.depends('contract', 'item_desc', 'item_kind',
        'options', 'parent', 'party', 'party_extra_data', 'product',
        'versions', 'contract_status')
    def on_change_contract(self):
        if self.contract:
            self.recalculate()

    @fields.depends('current_extra_data', 'item_desc',
        'party', 'party_extra_data', 'product', 'versions', 'contract_status')
    def on_change_current_extra_data(self):
        if not self.versions:
            return
        current_version = self.get_version_at_date(utils.today())
        if not current_version:
            return
        current_version.extra_data = self.current_extra_data
        self.update_extra_data(current_version)
        current_version.extra_data_as_string = \
            current_version.on_change_with_extra_data_as_string()
        self.versions = list(self.versions)
        self.current_extra_data = current_version.extra_data

    @fields.depends('contract', 'current_extra_data', 'item_desc',
        'item_kind', 'options', 'parent', 'party',
        'party_extra_data', 'product', 'versions', 'contract_status')
    def on_change_item_desc(self):
        self.recalculate()

    @fields.depends('contract', 'current_extra_data', 'item_desc', 'item_kind',
        'options', 'parent', 'party', 'party_extra_data',
        'product', 'versions', 'contract_status')
    def on_change_parent(self):
        self.recalculate()

    @fields.depends('contract', 'current_extra_data', 'item_desc', 'item_kind',
        'options', 'parent', 'party', 'party_extra_data',
        'product', 'versions', 'contract_status')
    def on_change_party(self):
        self.recalculate()

    @fields.depends('versions', 'contract_status')
    def on_change_versions(self):
        if len(self.versions) <= 1:
            return
        if self.versions[-1].start:
            return
        self.versions[-1].extra_data = dict(self.versions[-2].extra_data)
        self.versions[-1].extra_data_as_string = \
            self.versions[-1].on_change_with_extra_data_as_string()
        self.versions = list(self.versions)

    @fields.depends('name', 'rec_name', 'party')
    def on_change_with_covered_name(self, name=None):
        if self.party:
            return self.party.rec_name
        return self.rec_name or self.name

    @fields.depends('parent', 'item_desc')
    def on_change_with_show_name(self, name=None):
        return bool(self.item_desc and self.item_desc.show_name)

    def getter_has_sub_covered_elements(self, name):
        return bool(self.item_desc and self.item_desc.sub_item_descs)

    @fields.depends('item_kind')
    def on_change_with_icon(self, name=None):
        if self.item_kind in ('person', 'party'):
            return 'coopengo-party'
        elif self.item_kind == 'company':
            return 'coopengo-company'
        return ''

    @fields.depends('party')
    def on_change_with_is_person(self, name=None):
        return self.party and self.party.is_person

    @fields.depends('item_desc')
    def on_change_with_item_kind(self, name=None):
        if self.item_desc:
            return self.item_desc.kind
        return ''

    @fields.depends('contract')
    def on_change_with_contract_status(self, name=None):
        # Only 1st level must be read only to deal with group contracts
        return self.contract.status if self.contract else ''

    @fields.depends('contract', 'parent')
    def on_change_with_product(self, name=None):
        if self.contract and self.contract.product:
            return self.contract.product.id
        if self.parent:
            return self.parent.product.id

    @classmethod
    def get_current_version(cls, covered_elements, names):
        field_map = cls.get_field_map()
        return utils.version_getter(covered_elements, names,
            'contract.covered_element.version', 'covered_element',
            utils.today(), field_map=field_map)

    def get_synthesis_dates(self):
        Date = Pool().get('ir.date')
        return '[%s - %s]' % (
            Date.date_as_string(self.start_date) if self.start_date else '',
            Date.date_as_string(self.end_date) if self.end_date else '')

    @classmethod
    def get_field_map(cls):
        return {'id': 'current_version', 'extra_data': 'current_extra_data'}

    def get_party_code(self, name):
        return self.party.code if self.party else ''

    def get_party_extra_data(self, name=None):
        res = {}
        if not getattr(self, 'party', None) or not (self.item_desc
                and self.item_desc.kind in ['party', 'person', 'company']):
            return res
        for extra_data_def in set(list(self.item_desc.extra_data_def) +
                [x for x in self.product.extra_data_def
                    if x.kind == 'covered_element']):
            if self.party and extra_data_def.name in self.party.extra_data:
                res[extra_data_def.name] = self.party.extra_data[
                    extra_data_def.name]
        res.update(self.get_version_at_date(utils.today()).extra_data)
        return res

    def set_extra_data_value(self, key, value):
        for version in self.versions:
            if key in version.extra_data:
                version.extra_data[key] = value
        self.versions = self.versions
        for option in self.options:
            option.set_extra_data_value(key, value)
        self.options = self.options

    def get_rec_name(self, name):
        res = ''
        if self.party:
            res = self.party.full_name
            relations = self.get_relation_with_subscriber()
            if relations:
                return '%s (%s)' % (res, relations)
            return res
        if self.item_desc:
            res = ': '.join(
                [_f for _f in [self.item_desc.rec_name, self.name] if _f])
        extra_data = self.item_desc.extra_data_rec_name
        if extra_data:
            separator = ' ' if self.name else ': '
            res = separator.join([_f for _f in [
                        res, str(
                            self.current_extra_data.get(extra_data, None))
                        ] if _f])
        return res or self.name

    @classmethod
    def getter_affiliated_to(cls, instances, name):
        pool = Pool()
        Party = pool.get('party.party')
        Contract = pool.get('contract')
        covered = cls.__table__()
        parent_covered = cls.__table__()
        contract = Contract.__table__()
        subscriber = Party.__table__()
        party = Party.__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: None for x in instances}
        query = covered.join(parent_covered, 'LEFT OUTER',
            condition=(parent_covered.left <= covered.left) & (
                parent_covered.right >= covered.right) & (
                parent_covered.contract == covered.contract)
            ).join(party, 'LEFT OUTER', condition=(
                parent_covered.party == party.id)
            ).join(contract, condition=covered.contract == contract.id
            ).join(subscriber, condition=contract.subscriber == subscriber.id
            )

        sub_query = query.select(covered.id, parent_covered.party,
            parent_covered.left, subscriber.id.as_('subscriber'),
            subscriber.is_person,
            Max(Case((party.is_person == Literal(False), parent_covered.left),
                    else_=Literal(0)),
                window=Window([covered.id])).as_('max_left'))

        for cur_slice in grouped_slice(instances):
            cursor.execute(*sub_query.select(sub_query.id,
                    Case((sub_query.left != Literal(0), sub_query.party),
                        else_=sub_query.subscriber),
                    where=sub_query.id.in_([x.id for x in cur_slice]) &
                    (sub_query.left == sub_query.max_left)
                    ))

            for covered_id, party_id in cursor.fetchall():
                result[covered_id] = party_id
        return result

    @classmethod
    def getter_all_parents(cls, instances, name):
        pool = Pool()
        contract = pool.get('contract').__table__()
        covered = cls.__table__()
        parent_covered = cls.__table__()
        party = pool.get('party.party').__table__()

        cursor = Transaction().connection.cursor()

        result = {x.id: [] for x in instances}

        query = covered.join(parent_covered, 'LEFT OUTER',
            condition=(parent_covered.left < covered.left) & (
                parent_covered.right > covered.right) & (
                parent_covered.contract == covered.contract)
            ).join(contract, condition=covered.contract == contract.id
            ).join(party, condition=contract.subscriber == party.id)

        cursor.execute(*query.select(covered.id, parent_covered.id,
                where=(covered.id.in_([x.id for x in instances]) &
                    (parent_covered.party != Null))))

        for covered_id, parent_id in cursor.fetchall():
            result[covered_id].append(parent_id)
        return result

    @classmethod
    def search_all_parents(cls, name, clause):
        return []

    @classmethod
    def getter_end_date(cls, instances, name):
        pool = Pool()
        Option = pool.get('contract.option')
        covered = cls.__table__()
        parent = cls.__table__()
        option = Option.__table__()

        result = {x.id: None for x in instances}

        cursor = Transaction().connection.cursor()
        query = covered.join(parent,
            condition=(parent.left <= covered.left)
            & (parent.right >= covered.right)
            & (parent.contract == covered.contract)
            ).join(option, 'LEFT OUTER',
                condition=option.covered_element == parent.id)
        cursor.execute(*query.select(
                covered.id, option.id, parent.manual_end_date,
                where=covered.id.in_([x.id for x in instances]),
                order_by=[covered.id]))

        per_covered = defaultdict(list)
        options = defaultdict(set)
        for covered_id, option, manual_end in cursor.fetchall():
            per_covered[covered_id].append(manual_end)
            if option:
                options[option].add(covered_id)

        # No need to look for the contrat's end date since the option's already
        # takes it into account
        options_end = defaultdict(list)
        for option in Option.browse(list(options.keys())):
            for covered in options[option.id]:
                options_end[covered].append(option.end_date)

        for k, v in per_covered.items():
            option_end = max([x for x in options_end[k] if x] or [None])
            result[k] = min(([x for x in v if x] +
                    ([option_end] if option_end else [])) or [None])

        return result

    @classmethod
    def set_party_extra_data(cls, instances, name, vals):
        Party = Pool().get('party.party')
        to_save = []
        for covered in instances:
            if not covered.party:
                continue
            covered.party.extra_data = covered.party.extra_data or {}
            covered.party.extra_data.update({
                    k: v for k, v in vals.items() if v})
            to_save.append(covered.party)
        if to_save:
            Party.save(to_save)

    @classmethod
    def search_party_code(cls, name, clause):
        return [('party.code',) + tuple(clause[1:])]

    @classmethod
    def search_affiliated_to(cls, name, clause):
        pool = Pool()
        Party = pool.get('party.party')
        Contract = pool.get('contract')
        covered = cls.__table__()
        parent_covered = cls.__table__()
        contract = Contract.__table__()
        subscriber = Party.__table__()
        party = Party.__table__()

        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        query = covered.join(parent_covered, 'LEFT OUTER',
            condition=(parent_covered.left <= covered.left) & (
                parent_covered.right >= covered.right) & (
                parent_covered.contract == covered.contract)
            ).join(party, 'LEFT OUTER', condition=(
                parent_covered.party == party.id)
            ).join(contract, condition=covered.contract == contract.id
            ).join(subscriber, condition=contract.subscriber == subscriber.id
            )

        sub_query = query.select(covered.id, parent_covered.party,
            parent_covered.left, subscriber.id.as_('subscriber'),
            subscriber.is_person,
            Max(Case((party.is_person == Literal(False), parent_covered.left),
                    else_=Literal(0)),
                window=Window([covered.id])).as_('max_left'))

        final_query = sub_query.select(sub_query.id,
            where=(sub_query.left == sub_query.max_left) &
            Operator(Case((sub_query.left != Literal(0), sub_query.party),
                    else_=sub_query.subscriber), value))
        return [('id', 'in', final_query)]

    def get_currency(self):
        return self.contract.currency if self.contract else None

    def get_version_at_date(self, at_date):
        for version in sorted(self.versions,
                key=lambda x: x.start or datetime.date.min, reverse=True):
            if (version.start or datetime.date.min) <= at_date:
                return version
        raise Exception('No Version found for %s at %s' % (self, at_date))

    def clean_up_versions(self, contract):
        Option = Pool().get('contract.option')
        if self.options:
            to_write = []
            for option in self.options:
                option.clean_up_versions(contract)
                to_write.append(option)
            if to_write:
                Option.save(to_write)

    def recalculate(self):
        self.update_from_contract()

        self.update_item_desc()

        if self.party:
            self.party_extra_data = self.get_party_extra_data()
        else:
            self.party_extra_data = {}

        self.update_current_version()

        self.update_default_options()

        self.start_date = self.get_start_date()

    def update_from_contract(self):
        self.contract = self.parent.contract if self.parent else \
            self.contract
        if not self.contract:
            self.product = None
            return
        self.contract_status = self.contract.status
        self.product = self.contract.product

    def update_item_desc(self):
        if self.parent and self.parent.item_desc:
            if (not self.item_desc or self.item_desc not in
                    self.parent.item_desc.sub_item_descs) and len(
                    self.parent.item_desc.sub_item_descs) == 1:
                self.item_desc = self.parent.item_desc.sub_item_descs[0]
        elif self.product:
            if (not self.item_desc or self.item_desc not in
                    self.product.item_descriptors):
                if len(self.product.item_descriptors) == 1:
                    self.item_desc = self.product.item_descriptors[0]
                else:
                    self.item_desc = None
        else:
            self.item_desc = None
        if not self.item_desc:
            self.item_kind = ''
            self.options = []
            return
        self.item_kind = self.item_desc.kind

    def update_current_version(self):
        Version = Pool().get('contract.covered_element.version')
        if not getattr(self, 'versions', None):
            current_version = Version(**Version.get_default_version())
            self.versions = [current_version]
        else:
            current_version = self.get_version_at_date(utils.today())
        self.update_extra_data(current_version)
        self.versions = list(self.versions)
        self.current_extra_data = current_version.extra_data
        current_version.contract_status = self.contract_status
        current_version.covered_parent = self.parent
        return current_version

    def update_default_options(self):
        if not self.product or not self.item_desc:
            self.options = []
            return
        available_coverages = self.get_coverages(self.product, self.item_desc)
        new_options = list(getattr(self, 'options', ()))
        for elem in list(getattr(self, 'options', ())):
            if elem.coverage not in available_coverages:
                new_options.remove(elem)
            else:
                available_coverages.remove(elem.coverage)
        Option = Pool().get('contract.option')
        for elem in available_coverages:
            if elem.subscription_behaviour == 'optional':
                continue
            new_options.append(Option.new_option_from_coverage(elem,
                    self.product, self.contract.start_date,
                    item_desc=self.item_desc))

        self.options = new_options

    def update_extra_data(self, version):
        if not self.item_desc or not self.product:
            version.extra_data = {}
            return

        for k, v in self.party_extra_data.items():
            if k not in version.extra_data:
                version.extra_data[k] = v
        version.extra_data = self.item_desc.refresh_extra_data(
            version.extra_data)
        if self.party:
            self.party_extra_data = {k: v
                for k, v in version.extra_data.items()}

    def get_relation_with_subscriber(self):
        if not self.party or not self.contract:
            return
        subscriber = self.contract.subscriber
        kinds = [rel.type.name for rel in self.party.relations
            if rel.to.id == subscriber.id]
        return ', '.join(kinds)

    @classmethod
    def get_coverages(cls, product, item_desc):
        return [x for x in product.coverages if x.item_desc == item_desc]

    def init_options(self, product, start_date):
        existing = dict(((x.coverage, x) for x in getattr(
                    self, 'options', [])))
        good_options = []
        OptionModel = Pool().get('contract.option')
        for coverage in self.get_coverages(product, self.item_desc):
            good_opt = None
            if coverage in existing:
                good_opt = existing[coverage]
            elif coverage.subscription_behaviour == 'mandatory':
                good_opt = OptionModel.new_option_from_coverage(coverage,
                    product, start_date)
            if good_opt:
                good_opt.parent_contract = self.contract
                good_opt.covered_element = self
                good_options.append(good_opt)
        self.options = good_options

    def check_at_least_one_covered(self):
        for option in self.options:
            if option.status == 'active':
                return True
        return False

    def get_party_extra_data_def(self):
        if (self.item_desc and self.item_desc.kind in
                ['party', 'person', 'company']):
            return self.item_desc.extra_data_def

    def get_package(self, at_date=None):
        if not at_date:
            at_date = utils.today()
        for package in self.contract.product.packages:
            coverages = [c.option for c in package.option_relations
                if not c.option.is_service]
            if not coverages or not all([self.is_covered_at_date(at_date, c)
                    for c in coverages]):
                continue
            return package

    def is_covered_at_date(self, at_date, coverage=None, allow_quotes=False):
        if not self.contract:
            return False
        if not self.contract.is_active_at_date(at_date, allow_quotes):
            return False
        for option in self.options:
            if ((not coverage or option.coverage == coverage) and
                    option.is_active_at_date(at_date, allow_quotes)):
                return True
        if not self.item_desc.has_sub_options():
            return False
        return any((sub_elem.is_covered_at_date(at_date, coverage, allow_quotes)
                for sub_elem in self.sub_covered_elements))

    def is_valid_at_date(self, at_date):
        '''
            Return true if the covered element is active `at_date`. This checks
            covered_element dates, the contract's activation dates and the
            contract's company.
        '''
        assert at_date
        # Filter out lines for which manual dates were set which do not
        # match the given date
        if self.manual_start_date and self.manual_start_date > at_date:
            return False
        if self.manual_end_date and self.manual_end_date < at_date:
            return False

        # Filter out lines whose contract is not active at the effective
        # date
        if not self.contract.is_active_at_date(at_date):
            return False

        # Filter out contracts which do not match the current company
        company = Transaction().context.get('company')
        if company:
            if not self.contract.company or self.contract.company.id != company:
                return False

        return True

    def get_start_date(self, name=None):
        dates = []
        date = None
        options = [o.start_date for o in self.options
            if o.status not in ['void', 'declined'] and o.start_date]
        if options:
            dates.append(min(options))
        if getattr(self, 'manual_start_date', None):
            dates.append(self.manual_start_date)
        if dates:
            date = min(dates)
        if self.parent:
            date = max(date or datetime.date.min, self.parent.start_date)
        return max(
            self.contract.start_date if self.contract and
            self.contract.start_date else datetime.date.min,
            date or datetime.date.min)

    def get_covered_parties(self, at_date):
        '''
        Returns all covered persons sharing the same covered data
        for example an employe, his spouse and his children
        '''
        res = []
        if self.party:
            res.append(self.party)
        for relation in self.covered_relations:
            if not utils.is_effective_at_date(relation, at_date):
                continue
            if relation.from_party != self.party:
                res.append(relation.from_party)
            if relation.to_party != self.party:
                res.append(relation.to_party)
        for sub_covered in self.sub_covered_elements:
            res.extend(sub_covered.get_covered_parties(at_date))
        return res

    @classmethod
    def get_possible_covered_elements(cls, party, at_date):
        matches = []
        Contract = Pool().get('contract')
        covered_elements = cls.search([('party', '=', party.id)])
        for contract in Contract.search([('parties', '=', party.id)]):
            covered_elements += contract.covered_elements
        for covered in list(set(covered_elements)):
            # Check dates
            if not covered.is_valid_at_date(at_date):
                continue
            # Filter out lines which are not covered by any option
            if covered.contract:
                if not covered.is_covered_at_date(at_date):
                    continue
            elif not covered.parent.is_covered_at_date(at_date):
                continue
            matches.append(covered)
        return matches

    def match_key(self, from_name=None, party=None):
        if (from_name and self.name == from_name
                or party and self.party == party):
            return True
        if party:
            for relation in self.covered_relations:
                if relation.from_party == party or relation.to_party == party:
                    return True

    def get_covered_element(self, from_name=None, party=None):
        if self.match_key(from_name, party):
            return self
        for sub_element in self.sub_covered_elements:
            if sub_element.match_key(from_name, party):
                return sub_element

    def find_extra_data_value(self, name, **kwargs):
        version = self.get_version_at_date(kwargs.get('date', utils.today()))
        try:
            return version.find_extra_data_value(name, **kwargs)
        except KeyError:
            if self.parent:
                return self.parent.find_extra_data_value(name, **kwargs)
            raise

    def find_package_extra_data_value(self, name, **kwargs):
        package = self.get_package(kwargs.get('date', utils.today()))
        if package:
            return package.find_extra_data_value(name, **kwargs)
        raise KeyError

    def init_dict_for_rule_engine(self, args):
        args = args if args else {}
        if self.parent:
            self.parent.init_dict_for_rule_engine(args)
        elif self.contract:
            self.contract.init_dict_for_rule_engine(args)
        else:
            raise Exception('Orphan covered element')
        args['elem'] = self

    def get_publishing_values(self):
        result = super(CoveredElement, self).get_publishing_values()
        result['party'] = self.party
        return result

    def init_covered_element(self, product, item_desc, cov_dict):
        if (item_desc.kind in ['person', 'party', 'company']
                and 'party' in cov_dict):
            # TODO to enhance if the party is not created yet
            self.party, = Pool().get('party.party').search(
                [('code', '=', cov_dict['party']['code'])], limit=1, order=[])
        self.product = product
        self.item_desc = item_desc
        if 'name' in cov_dict:
            self.name = cov_dict['name']

        self.on_change_item_desc()
        if 'extra_data' in cov_dict:
            self.extra_data.update(cov_dict['extra_data'])

    def fill_list_with_covered_options(self, at_date):
        options = [option for option in self.options
            if option.is_active_at_date(at_date)]
        if not self.parent:
            return options
        return options + self.parent.fill_list_with_covered_options(at_date)

    def notify_contract_end_date_change(self, new_end_date):
        if self.versions:
            to_date_versions = [v for v in self.versions
                if v.start is None or v.start < new_end_date]
            self.versions = to_date_versions

    def get_summary_content(self, label, at_date=None, lang=None):
        res = [self.rec_name, []]
        if self.party and self.party.is_person:
            _, value = coog_string.get_field_summary(self.party,
                'birth_date', False, at_date, lang)
            res[0] += ' - %s (%s)' % (value, self.contract.calculate_age(
                    birth_date=self.party.birth_date,
                    at_date=at_date or self.contract.initial_start_date))
        res[1].append(coog_string.get_field_summary(self,
            'party_extra_data', True, at_date, lang))
        res[1].append(coog_string.get_field_summary(self, 'options', True,
            at_date, lang))
        return tuple(res)

    def get_contact(self):
        return self.party or self.contract.get_contact()

    def get_object_for_contact(self):
        return self.contract

    def get_sender(self):
        return self.party or self.contract.get_sender()


class CoveredElementVersion(model.CoogSQL, model.CoogView,
        with_extra_data(['covered_element'],
            create_summary='extra_data_as_string')):
    'Contract Covered Element Version'

    __name__ = 'contract.covered_element.version'
    _func_key = 'start'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', required=True, ondelete='CASCADE', select=True)
    contract_status = fields.Function(
        fields.Char('Contract Status'),
        'on_change_with_contract_status')
    covered_parent = fields.Function(
        fields.Many2One('contract.covered_element', 'Covered Parent'),
        'on_change_with_covered_parent')
    start = fields.Date('Start', readonly=True)

    @classmethod
    def __setup__(cls):
        super(CoveredElementVersion, cls).__setup__()
        cls.extra_data.states['readonly'] = (Eval('contract_status') != 'quote'
            ) & ~Eval('covered_parent')
        cls.extra_data.depends += ['contract_status', 'covered_parent']

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        CoveredElement = pool.get('contract.covered_element')
        TableHandler = backend.get('TableHandler')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        covered_element = CoveredElement.__table__()
        version = cls.__table__()

        # Migration from 1.4 : Create default contract.covered_element.version
        covered_h = TableHandler(CoveredElement, module)
        to_migrate = covered_h.column_exist('extra_data')

        super(CoveredElementVersion, cls).__register__(module)

        if to_migrate:
            version_h = TableHandler(cls, module)
            cursor.execute(*version.insert(
                    columns=[
                        version.create_date, version.create_uid,
                        version.write_date, version.write_uid,
                        version.extra_data, version.covered_element,
                        version.id],
                    values=covered_element.select(
                        covered_element.create_date,
                        covered_element.create_uid, covered_element.write_date,
                        covered_element.write_uid, covered_element.extra_data,
                        covered_element.id.as_('covered_element'),
                        covered_element.id.as_('id'))))
            cursor.execute(*version.select(Max(version.id)))
            transaction.database.setnextid(transaction.connection,
                version_h.table_name, cursor.fetchone()[0] or 0 + 1)
            covered_h = TableHandler(CoveredElement, module)
            covered_h.drop_column('extra_data')

    @fields.depends('covered_element')
    def on_change_covered_element(self):
        if not self.covered_element:
            self.covered_parent = None
            self.contract_status = None
            return
        self.contract_status = self.on_change_with_contract_status()
        self.covered_parent = self.on_change_with_covered_parent()

    @fields.depends('covered_element')
    def on_change_with_contract_status(self, name=None):
        return (self.covered_element.contract_status
            if self.covered_element else '')

    @fields.depends('covered_element')
    def on_change_with_covered_parent(self, name=None):
        return (self.covered_element.parent.id
            if self.covered_element and self.covered_element.parent else None)

    @classmethod
    def order_start(cls, tables):
        table, _ = tables[None]
        return [Coalesce(table.start, datetime.date.min)]

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values.get('start', None)

    @classmethod
    def get_default_version(cls):
        return {
            'start': None,
            'extra_data': {},
            }

    def get_rec_name(self, name):
        return self.covered_element.rec_name


class CoveredElementPartyRelation(model.CoogSQL):
    'Relation between Covered Element and Covered Relations'

    __name__ = 'contract.covered_element-party'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    party_relation = fields.Many2One('party.relation.all', 'Party Relation',
        ondelete='RESTRICT')


class ExtraPremium(model.CoogSQL, model.CoogView, ModelCurrency):
    'Extra Premium'

    __name__ = 'contract.option.extra_premium'

    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE',
        states={'invisible': ~Eval('option')}, select=True, required=True,
        readonly=True)
    contract_status = fields.Function(
        fields.Char('Contract Status'),
        'on_change_with_contract_status')
    calculation_kind = fields.Selection('get_possible_extra_premiums_kind',
        'Calculation Kind', states=_CONTRACT_STATUS_STATES,
        depends=_CONTRACT_STATUS_DEPENDS)
    calculation_kind_string = calculation_kind.translated('calculation_kind')
    start_date = fields.Function(
        fields.Date('Start Date', states=_CONTRACT_STATUS_STATES,
        depends=_CONTRACT_STATUS_DEPENDS),
        'get_start_date', setter='setter_void')
    manual_start_date = fields.Date('Manual Start date',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    end_date = fields.Function(fields.Date('End date', states={
            'invisible': ~Eval('time_limited')},
        depends=['time_limited']),
        'get_end_date')
    manual_end_date = fields.Date('Manual End Date',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    final_end_date = fields.Function(
        fields.Date('Final End Date'),
        'get_final_end_date')
    duration = fields.Integer('Duration', states={
            'invisible': ~Eval('time_limited'),
            'readonly': Eval('contract_status') != 'quote',
            }, depends=['time_limited', 'contract_status'])
    duration_unit = fields.Selection(
        [('month', 'Month'), ('year', 'Year')],
        'Duration Unit', sort=False, required=True, states={
            'invisible': ~Eval('time_limited'),
            'readonly': Eval('contract_status') != 'quote',
            }, depends=['time_limited', 'contract_status'])
    duration_unit_string = duration_unit.translated('duration_unit')
    time_limited = fields.Function(
        fields.Boolean('Time Limited', states=_CONTRACT_STATUS_STATES,
        depends=_CONTRACT_STATUS_DEPENDS),
        'get_time_limited', setter='setter_void')
    flat_amount = fields.Numeric('Flat amount', states={
            'invisible': Eval('calculation_kind', '') != 'flat',
            'required': Eval('calculation_kind', '') == 'flat',
            'readonly': Eval('contract_status') != 'quote',
            }, digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits', 'calculation_kind', 'is_discount',
                 'max_value', 'contract_status'],
        domain=[If(Eval('calculation_kind', '') != 'flat',
                [],
                If(Bool(Eval('is_discount')),
                    [('flat_amount', '<', 0),
                        ['OR',
                            [('max_value', '=', None)],
                            [('flat_amount', '>', Eval('max_value'))]]],
                    [('flat_amount', '>', 0),
                        ['OR',
                            [('max_value', '=', None)],
                            [('flat_amount', '<', Eval('max_value'))]]
                        ]))])
    motive = fields.Many2One('extra_premium.kind', 'Motive',
        ondelete='RESTRICT', required=True, states=_CONTRACT_STATUS_STATES,
        depends=_CONTRACT_STATUS_DEPENDS)
    rate = fields.Numeric('Rate on Premium', states={
            'invisible': Eval('calculation_kind', '') != 'rate',
            'required': Eval('calculation_kind', '') == 'rate',
            'readonly': Eval('contract_status') != 'quote',
            }, digits=(16, 4), depends=['calculation_kind', 'is_discount',
            'max_rate', 'contract_status'],
        domain=[If(Eval('calculation_kind', '') != 'rate',
                [],
                If(Bool(Eval('is_discount')),
                    [('rate', '<', 0),
                        ['OR',
                            [('max_rate', '=', None)],
                            [('rate', '>', Eval('max_rate'))]]],
                    [('rate', '>', 0),
                        ['OR',
                            [('max_rate', '=', None)],
                            [('rate', '<', Eval('max_rate'))]]]
                    ))])
    is_discount = fields.Function(
        fields.Boolean('Is Discount'),
        'on_change_with_is_discount')
    max_value = fields.Function(
        fields.Numeric('Max Value'),
        'on_change_with_max_value', searcher='search_max_value')
    max_rate = fields.Function(
        fields.Numeric('Max Rate'),
        'on_change_with_max_rate', searcher='search_max_rate')
    value_as_string = fields.Function(
        fields.Char('Value'),
        'on_change_with_value_as_string')
    covered_element = fields.Function(
        fields.Many2One('contract.covered_element', 'Covered element'),
        'on_change_with_covered_element')

    @classmethod
    def __setup__(cls):
        super(ExtraPremium, cls).__setup__()
        cls._buttons.update({'propagate': {
                    'readonly': Eval('contract_status') != 'quote'}})

    @classmethod
    def view_attributes(cls):
        return super(ExtraPremium, cls).view_attributes() + [(
                '/form/group[@id="flat_amounts"]/'
                'group[@id="flat_amount_discount"]',
                'states',
                {'invisible': Or(Eval('calculation_kind') != 'flat',
                        ~Eval('is_discount'))}
                ), (
                '/form/group[@id="flat_amounts"]/group[@id="flat_amount"]',
                'states',
                {'invisible': Or(Eval('calculation_kind') != 'flat',
                        Bool(Eval('is_discount')))}
                ), (
                '/form/group[@id="rates"]/group[@id="rate_discount"]',
                'states',
                {'invisible': Or(Eval('calculation_kind') != 'rate',
                        ~Eval('is_discount'))}
                ), (
                '/form/group[@id="rates"]/group[@id="rate"]',
                'states',
                {'invisible': Or(Eval('calculation_kind') != 'rate',
                        Bool(Eval('is_discount')))}
                ), (
                '/form/group[@id="invisible"]',
                'states', {'invisible': True}
                )]

    @classmethod
    def default_calculation_kind(cls):
        return 'rate'

    @classmethod
    def default_time_limited(cls):
        return False

    @classmethod
    def default_end_date(cls):
        if 'end_date' in Transaction().context:
            return Transaction().context.get('end_date')
        return None

    @fields.depends('option')
    def on_change_with_contract_status(self, name=None):
        return self.option.contract_status if self.option else ''

    @fields.depends('manual_start_date', 'option', 'start_date')
    def on_change_option(self):
        # no option when called from CreateExtraPremiumOptionSelector wizard
        if self.option:
            self.start_date = self.get_start_date(None)

    @fields.depends('time_limited', 'duration')
    def on_change_time_limited(self):
        if not self.time_limited:
            self.duration = 0
        self.end_date = self.calculate_end_date()

    @classmethod
    def default_duration_unit(cls):
        return 'month'

    @fields.depends('calculation_kind')
    def on_change_calculation_kind(self):
        if self.calculation_kind == 'flat':
            self.rate = None
        elif self.calculation_kind == 'rate':
            self.flat_amount = None

    @fields.depends('duration', 'start_date', 'duration_unit', 'time_limited')
    def on_change_duration(self):
        if not self.time_limited:
            self.duration = 0
        self.end_date = self.calculate_end_date()

    @fields.depends('start_date', 'duration', 'duration_unit')
    def on_change_duration_unit(self):
        self.end_date = self.calculate_end_date()

    @fields.depends('manual_start_date', 'option', 'start_date')
    def on_change_start_date(self):
        self.manual_start_date = self.start_date
        if self.option and self.start_date == self.option.start_date:
            self.manual_start_date = None

    @fields.depends('motive')
    def on_change_with_is_discount(self, name=None):
        return self.motive.is_discount if self.motive else False

    @fields.depends('motive')
    def on_change_with_max_value(self, name=None):
        return self.motive.max_value if self.motive else None

    @fields.depends('motive')
    def on_change_with_max_rate(self, name=None):
        return self.motive.max_rate if self.motive else None

    @fields.depends('option', 'motive', 'value_as_string')
    def on_change_with_rec_name(self, name=None):
        return self.get_rec_name(name)

    @fields.depends('calculation_kind', 'flat_amount', 'rate', 'currency')
    def on_change_with_value_as_string(self, name=None):
        return self.get_value_as_string(name)

    def get_currency(self):
        return self.option.currency if self.option else None

    def get_is_discount(self):
        return self.motive.is_discount if self.motive else False

    @staticmethod
    def get_possible_extra_premiums_kind():
        return list(POSSIBLE_EXTRA_PREMIUM_RULES)

    def get_rec_name(self, name):
        return '%s %s %s' % (self.option.rec_name if self.option else '',
            self.value_as_string, self.motive.name if self.motive else '')

    def get_value_as_string(self, name):
        if self.calculation_kind == 'flat' and self.flat_amount:
            return self.currency.amount_as_string(abs(self.flat_amount))
        elif self.calculation_kind == 'rate' and self.rate:
            return '%s %%' % coog_string.format_number('%.2f',
                abs(self.rate) * 100)

    def get_time_limited(self, name):
        return bool(self.duration != 0 or self.manual_end_date)

    @fields.depends('option')
    def on_change_with_covered_element(self, name=None):
        covered_element = getattr(self.option, 'covered_element', None)
        if covered_element:
            return covered_element.id

    @classmethod
    def search_max_value(cls, name, clause):
        return [(('motive.max_value',) + tuple(clause[1:]))]

    @classmethod
    def search_max_rate(cls, name, clause):
        return [(('motive.max_rate',) + tuple(clause[1:]))]

    @classmethod
    def validate(cls, extra_premiums):
        for extra in extra_premiums:
            if (extra.manual_start_date and extra.manual_start_date <
                    extra.option.start_date):
                raise ValidationError(gettext(
                            'contract_insurance.msg_bad_start_date',
                            motive=extra.motive.name,
                            start_date=extra.start_date,
                            option_start_date=extra.option.start_date))

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_extra_premium')
    def propagate(cls, extras):
        pass

    def calculate_premium_amount(self, args, base):
        if self.calculation_kind == 'flat':
            return self.flat_amount
        elif self.calculation_kind == 'rate':
            return base * self.rate
        return 0

    def get_start_date(self, name):
        return self.manual_start_date or self.option.initial_start_date

    def get_end_date(self, name):
        calculated = self.calculate_end_date()
        manual = self.manual_end_date
        if self.manual_end_date:
            return min(manual, calculated) if calculated else manual
        return calculated

    def get_final_end_date(self, name):
        return self.manual_end_date or (self.option.final_end_date
            if not self.duration and getattr(self, 'option', None)
            else self.end_date)

    def notify_contract_end_date_change(self, new_end_date):
        if (new_end_date and self.manual_end_date and
                self.manual_end_date > new_end_date):
            self.manual_end_date = None

    def notify_contract_start_date_change(self, new_start_date):
        pass

    def calculate_end_date(self):
        if not self.duration:
            if getattr(self, 'option', None):
                return self.option.end_date
        else:
            months, years = 0, 0
            if self.duration_unit == 'month':
                months = self.duration
            else:
                years = self.duration
            return self.start_date + relativedelta(months=months,
                years=years, days=-1)


class OptionExclusionKindRelation(model.CoogSQL, model.CoogView):
    'Option to Exclusion Kind relation'

    __name__ = 'contract.option.exclusion'

    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE',
        required=True, select=True)
    exclusion = fields.Many2One('offered.exclusion', 'Exclusion',
        ondelete='RESTRICT', required=True, select=True)
    comment = fields.Text('Comment', help='A free-input field '
        'to detail why the exclusion was added')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 2.4: rename 'contract_option-exclusion_kind' =>
        # 'contract_option_exclusion'
        TableHandler = backend.get('TableHandler')
        if TableHandler.table_exist(
                'contract_option-exclusion_kind '):
            TableHandler.table_rename(
                'contract_option-exclusion_kind',
                'contract_option_exclusion')
        elif TableHandler.\
                table_exist('contract_option-exclusion_kind__history'):
            TableHandler.table_rename(
                'contract_option-exclusion_kind__history',
                'contract_option_exclusion__history')
        super(OptionExclusionKindRelation, cls).__register__(module_name)

    @classmethod
    def search(cls, domain, *args, **kwargs):
        exclusions = Pool().get('offered.exclusion').search([])

        domain = ['AND', domain, ['OR', ('exclusion', '=', None),
            ('exclusion', 'in', [x.id for x in exclusions])]]
        return super(OptionExclusionKindRelation, cls).search(
            domain, *args, **kwargs)

    def get_rec_name(self, name):
        return '%s%s%s'\
               % (self.exclusion and self.exclusion.name or '',
                  ' - ' if self.comment else '',
                   self.comment)
