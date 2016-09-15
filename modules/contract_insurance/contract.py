# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from dateutil.relativedelta import relativedelta

from sql import Null
from sql.conditionals import Coalesce
from sql.aggregate import Max

from trytond import backend
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Or, Bool, Len
from trytond.transaction import Transaction
from trytond.model import ModelView

from trytond.modules.cog_utils import model, fields
from trytond.modules.cog_utils import utils
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.contract import _CONTRACT_STATUS_STATES
from trytond.modules.contract import _CONTRACT_STATUS_DEPENDS
from trytond.modules.report_engine import Printable


IS_PARTY = Eval('item_kind').in_(['person', 'company', 'party'])

POSSIBLE_EXTRA_PREMIUM_RULES = [
    ('flat', 'Montant Fixe'),
    ('rate', 'Pourcentage'),
    ]

__metaclass__ = PoolMeta
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
    covered_element_options = fields.Function(
        fields.One2Many('contract.option', None, 'Covered Element Options'),
        'get_covered_element_options')
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
        cls._error_messages.update({
                'error_in_renewal_date_calculation': 'Errors occured during '
                'renewal date calculation : %s',
                'need_option': 'Select at least one option for %s',
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

    def get_covered_element_options(self, name):
        return [option.id
            for covered_element in self.covered_elements
            for option in covered_element.options]

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
                self.append_functional_error('need_option',
                    (covered.get_rec_name('')))

    def notify_end_date_change(self, value):
        super(Contract, self).notify_end_date_change(value)
        for element in self.covered_elements:
            for option in element.options:
                option.notify_contract_end_date_change(value)
            element.options = element.options
        self.covered_elements = self.covered_elements

    def notify_start_date_change(self, value):
        super(Contract, self).notify_start_date_change(value)
        for element in self.covered_elements:
            for option in element.options:
                option.notify_contract_start_date_change(value)
            element.options = element.options
        self.covered_elements = self.covered_elements

    @classmethod
    def check_option_end_dates(cls, contracts):
        super(Contract, cls).check_option_end_dates(contracts)
        Pool().get('contract.option').check_end_date([option
                for contract in contracts
                for option in contract.covered_element_options])

    @classmethod
    def get_coverages(cls, product):
        return [x.coverage for x in product.ordered_coverages
            if x.coverage.is_service]

    def init_covered_elements(self):
        for elem in self.covered_elements:
            elem.init_options(self.product, self.start_date)
            elem.save()

    @classmethod
    def search_contract(cls, product, subscriber, at_date):
        return cls.search([
                ('product', '=', product),
                ('subscriber', '=', subscriber),
                ('start_date', '<=', at_date)])

    def check_contract_extra_data(self):
        final_res, final_errs = True, []
        for extra_data in self.extra_datas:
            res, errs = Pool().get('extra_data').check_extra_data(extra_data,
                'extra_data_values')
            final_res = final_res and res
            final_errs.extend(errs)
        return final_res, final_errs

    def check_contract_option_extra_data(self):
        ExtraData = Pool().get('extra_data')
        final_res, final_errs = True, []
        for option in self.options:
            res, errs = ExtraData.check_extra_data(option,
                'extra_data')
            final_res = final_res and res
            final_errs.extend(errs)
        return final_res, final_errs

    def check_covered_element_extra_data(self):
        ExtraData = Pool().get('extra_data')
        final_res, final_errs = True, []
        for covered_element in self.covered_elements:
            res, errs = ExtraData.check_extra_data(covered_element,
                'extra_data')
            final_res = final_res and res
            final_errs.extend(errs)
        return final_res, final_errs

    def check_covered_element_option_extra_data(self):
        ExtraData = Pool().get('extra_data')
        final_res, final_errs = True, []
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                res, errs = ExtraData.check_extra_data(option,
                    'extra_data')
                final_res = final_res and res
                final_errs.extend(errs)
        return final_res, final_errs

    @classmethod
    def update_contract_after_import(cls, contracts):
        super(Contract, cls).update_contract_after_import(contracts)
        for contract in contracts:
            contract.init_covered_elements()

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
        result['Insurers'] = [x.coverage.insurer.party for x in self.options
            if x.coverage.insurer]
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

    def get_parties(self, name):
        parties = super(Contract, self).get_parties(name)
        parties += [x.party.id for x in self.covered_elements if x.party]
        return parties

    def activate_contract(self):
        super(Contract, self).activate_contract()
        for covered_element in getattr(self, 'covered_elements', []):
            for option in covered_element.options:
                option.status = 'active'
                option.save()

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
            covered_element.main_contract = self
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


class ContractOption:
    __name__ = 'contract.option'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', ondelete='CASCADE', select=True,
        states={
            'readonly': Eval('contract_status') != 'quote',
            'invisible': ~Eval('covered_element'),
            }, depends=_CONTRACT_STATUS_DEPENDS)
    exclusions = fields.Many2Many('contract.option-exclusion.kind',
        'option', 'exclusion', 'Exclusions',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    # O2M field to the M2M "exclusions" field table. This is for instance used
    # in endorsements
    exclusion_list = fields.One2Many('contract.option-exclusion.kind',
        'option', 'Exclusion List', delete_missing=True,
        order=[('exclusion', 'ASC')])
    extra_data_summary = fields.Function(
        fields.Text('Extra Data Summary'),
        'get_extra_data_summary')
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

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._buttons.update({
                'propagate_extra_premiums': _CONTRACT_STATUS_STATES,
                'propagate_exclusions': _CONTRACT_STATUS_STATES,
                })

    @classmethod
    def order_coverage(cls, tables):
        super(ContractOption, cls).order_coverage(tables)

        pool = Pool()
        table, _ = tables[None]
        query_table, _ = tables['coverage_order_tables'][None]

        contract = tables.get('contract')
        if contract is None:
            contract = pool.get('contract').__table__()

        covered_element = tables.get('contract.covered_element')
        if covered_element is None:
            covered_element = pool.get('contract.covered_element').__table__()

        new_query_table = query_table.join(covered_element, 'LEFT OUTER',
            condition=(covered_element.contract == query_table.contract)
            ).select(query_table.contract, query_table.coverage,
                query_table.order, covered_element.id.as_('covered_element'))

        tables['coverage_order_tables'] = {
            None: (new_query_table,
                (new_query_table.coverage == table.coverage) &
                (
                    ((new_query_table.contract == table.contract)
                        & (table.contract != Null)) |
                    ((new_query_table.covered_element == table.covered_element)
                        & (table.covered_element != Null))
                    ))}
        return [new_query_table.order]

    def get_full_name(self, name):
        return super(ContractOption, self).get_full_name(name)

    @classmethod
    def get_extra_data_summary(cls, extra_datas, name):
        return Pool().get('extra_data').get_extra_data_summary(extra_datas,
            'current_extra_data')

    @classmethod
    def _export_skips(cls):
        return super(ContractOption, cls)._export_skips() | {'exclusion_list',
            'extra_premium_discounts', 'extra_premium_increases'}

    @fields.depends('item_desc')
    def on_change_coverage(self):
        super(ContractOption, self).on_change_coverage()

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

    @fields.depends('covered_element')
    def on_change_with_parent_contract(self, name=None):
        contract_id = super(
            ContractOption, self).on_change_with_parent_contract(name)
        if contract_id:
            return contract_id
        elif self.covered_element:
            contract = getattr(self.covered_element, 'contract')
            if contract:
                return contract.id

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

    @classmethod
    def search_parent_contract(cls, name, clause):
        columns = clause[0].split('.')
        if len(columns) == 1:
            return ['OR',
                ('contract',) + tuple(clause[1:]),
                ('covered_element.contract',) + tuple(clause[1:]),
                ]
        else:
            columns_to_add = '.'.join(columns[1:])
            return ['OR',
                ('contract.' + columns_to_add,) + tuple(clause[1:]),
                ('covered_element.contract.' + columns_to_add,) +
                tuple(clause[1:]),
                ]

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
                ('covered_element.contract.start_date',) + tuple(clause[1:]),
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

    def get_extra_data_def(self):
        return self.coverage.get_extra_data_def(
            ['elem'])

    @classmethod
    def new_option_from_coverage(cls, coverage, product,
            start_date, end_date=None, item_desc=None):
        new_option = super(ContractOption, cls).new_option_from_coverage(
            coverage, product, start_date, end_date)
        new_option.item_desc = item_desc
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

    def recalculate_extra_data(self, extra_data):
        if not self.item_desc or not self.product or not self.coverage:
            return super(ContractOption, self).recalculate_extra_data(
                extra_data)
        return self.product.get_extra_data_def('option', extra_data.copy(),
            self.appliable_conditions_date, coverage=self.coverage,
            item_desc=self.item_desc)

    def get_all_extra_data(self, at_date):
        res = super(ContractOption, self).get_all_extra_data(at_date)
        if self.covered_element:
            res.update(self.covered_element.get_all_extra_data(at_date))
        return res


class ContractOptionVersion:
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


class CoveredElement(model.CoopSQL, model.CoopView, model.ExpandTreeMixin,
        ModelCurrency):
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
    versions = fields.One2Many('contract.covered_element.version',
        'covered_element', 'Versions', delete_missing=True,
        order=[('start', 'ASC')])
    covered_relations = fields.Many2Many('contract.covered_element-party',
        'covered_element', 'party_relation', 'Covered Relations', domain=[
            'OR',
            [('from_party', '=', Eval('party'))],
            [('to_party', '=', Eval('party'))],
            ], depends=['party'],
        states={'invisible': ~IS_PARTY})
    current_extra_data = fields.Function(
        fields.Dict('extra_data', 'Current Extra Data', states={
                'invisible': ~Eval('current_extra_data')},
            depends=['current_extra_data']),
        'get_current_version', setter='setter_void')
    current_extra_data_string = current_extra_data.translated(
        'current_extra_data')
    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='RESTRICT', required=True)
    name = fields.Char('Name', states={'invisible': IS_PARTY})
    options = fields.One2ManyDomain('contract.option', 'covered_element',
        'Options', domain=[
            ('coverage.products', '=', Eval('product')),
            ('coverage.item_desc', '=', Eval('item_desc')),
            ('status', '!=', 'declined'),
            ],
        depends=['item_desc', 'product'],
        target_not_required=True, order=[('coverage', 'ASC'),
            ('start_date', 'ASC')])
    declined_options = fields.One2ManyDomain('contract.option',
        'covered_element', 'Declined Options',
        domain=[('status', '=', 'declined')], target_not_required=True)
    all_options = fields.One2Many('contract.option', 'covered_element',
        'Options', target_not_required=True, delete_missing=True)
    parent = fields.Many2One('contract.covered_element', 'Parent',
        ondelete='CASCADE', select=True)
    party = fields.Many2One('party.party', 'Actor', domain=[
            If(
                Eval('item_kind') == 'person',
                ('is_person', '=', True),
                ()),
            If(
                Eval('item_kind') == 'company',
                ('is_company', '=', True),
                ())],
        states={
            'invisible': ~IS_PARTY,
            'required': IS_PARTY,
            }, ondelete='RESTRICT', depends=['item_kind'], select=True)
    sub_covered_elements = fields.One2Many('contract.covered_element',
        'parent', 'Sub Covered Elements',
        # TODO : invisibility should depend on a function field checking the
        # item desc definition
        states={'invisible': Eval('item_kind') == 'person'},
        depends=['contract', 'item_kind', 'id'],
        target_not_required=True)
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
    main_contract = fields.Function(
        fields.Many2One('contract', 'Contract',
            states={'invisible': Bool(Eval('contract'))},
            depends=['contract']),
        'on_change_with_main_contract')
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

    multi_mixed_view = options

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR', [
                ('party.full_name',) + tuple(clause[1:]),
                ], [
                ('item_desc.rec_name',) + tuple(clause[1:]),
                ],
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
                {'invisible': Eval('item_kind') == 'person'}
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
        return (super(CoveredElement, cls)._export_skips() |
            set(['multi_mixed_view']))

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
            cls.raise_user_error('too_many_party')

    @classmethod
    def write(cls, *args):
        action = iter(args)
        for covered_elements, values in zip(action, action):
            if 'sub_covered_elements' not in values:
                continue
            for covered_element in covered_elements:
                for val in values['sub_covered_elements']:
                    if val[0] != 'create':
                        continue
                    for sub_cov_elem in val[1]:
                        sub_cov_elem['contract'] = covered_element.contract.id
        super(CoveredElement, cls).write(*args)

    @classmethod
    def copy(cls, instances, default=None):
        default = {} if default is None else default.copy()
        if Transaction().context.get('copy_mode', '') == 'functional':
            skips = cls._export_skips() | cls.functional_skips_for_duplicate()
            for x in skips:
                default.setdefault(x, None)
        return super(CoveredElement, cls).copy(instances, default=default)

    @classmethod
    def default_versions(cls):
        return [Pool().get(
                'contract.covered_element.version').get_default_version()]

    @fields.depends('contract', 'item_desc', 'item_kind', 'main_contract',
        'options', 'parent', 'party', 'party_extra_data', 'product',
        'versions')
    def on_change_contract(self):
        self.main_contract = self.contract
        self.recalculate()

    @fields.depends('current_extra_data', 'item_desc', 'main_contract',
        'party', 'party_extra_data', 'product', 'versions')
    def on_change_current_extra_data(self):
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
        'item_kind', 'main_contract', 'options', 'parent', 'party',
        'party_extra_data', 'product', 'versions')
    def on_change_item_desc(self):
        self.recalculate()

    @fields.depends('contract', 'current_extra_data', 'item_desc', 'item_kind',
        'main_contract', 'options', 'parent', 'party', 'party_extra_data',
        'product', 'versions')
    def on_change_parent(self):
        self.recalculate()

    @fields.depends('contract', 'current_extra_data', 'item_desc', 'item_kind',
        'main_contract', 'options', 'parent', 'party', 'party_extra_data',
        'product', 'versions')
    def on_change_party(self):
        self.recalculate()

    @fields.depends('party')
    def on_change_with_covered_name(self, name=None):
        if self.party:
            return self.party.rec_name
        return ''

    @fields.depends('is_person')
    def on_change_with_icon(self, name=None):
        if self.is_person:
            return 'coopengo-party'
        return ''

    @fields.depends('party')
    def on_change_with_is_person(self, name=None):
        return self.party and self.party.is_person

    @fields.depends('item_desc')
    def on_change_with_item_kind(self, name=None):
        if self.item_desc:
            return self.item_desc.kind
        return ''

    @fields.depends('contract', 'parent')
    def on_change_with_main_contract(self, name=None):
        contract = getattr(self, 'contract', None)
        if contract:
            return contract.id
        parent = getattr(self, 'parent', None)
        if parent:
            return self.parent.main_contract.id

    @fields.depends('contract', 'parent', 'main_contract')
    def on_change_with_product(self, name=None):
        if self.contract and self.contract.product:
            return self.contract.product.id
        if self.main_contract and self.main_contract.product:
            return self.main_contract.product.id
        if self.parent:
            return self.parent.product.id

    @classmethod
    def get_current_version(cls, covered_elements, names):
        field_map = cls.get_field_map()
        return utils.version_getter(covered_elements, names,
            'contract.covered_element.version', 'covered_element',
            utils.today(), field_map=field_map)

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

    def get_rec_name(self, name):
        if self.party:
            res = self.party.full_name
            relations = self.get_relation_with_subscriber()
            if relations:
                return '%s (%s)' % (res, relations)
            return res
        names = [super(CoveredElement, self).get_rec_name(name)]
        names.append(self.item_desc.rec_name if self.item_desc else None)
        return ' '.join([x for x in names if x])

    @classmethod
    def set_party_extra_data(cls, instances, name, vals):
        Party = Pool().get('party.party')
        to_save = []
        for covered in instances:
            if not covered.party:
                continue
            covered.party.extra_data = covered.party.extra_data or {}
            covered.party.extra_data.update(vals)
            to_save.append(covered.party)
        if to_save:
            Party.save(to_save)

    @classmethod
    def search_party_code(cls, name, clause):
        return [('party.code',) + tuple(clause[1:])]

    def get_currency(self):
        return self.main_contract.currency if self.main_contract else None

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
        self.update_main_contract()

        self.update_item_desc()

        if self.party:
            self.party_extra_data = self.get_party_extra_data()
        else:
            self.party_extra_data = {}

        self.update_current_version()

        self.update_default_options()

    def update_main_contract(self):
        self.main_contract = self.parent.main_contract if self.parent else \
            self.contract
        if not self.main_contract:
            self.product = None
            return
        self.product = self.main_contract.product

    def update_item_desc(self):
        if self.parent and self.parent.item_desc:
            if (not self.item_desc or self.item_desc not in
                    self.parent.item_desc.sub_item_descriptors) and len(
                    self.parent.item_desc.sub_item_descriptors) == 1:
                self.item_desc = self.parent.item_desc.sub_item_descriptors[0]
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
        return current_version

    def update_default_options(self):
        available_coverages = self.get_coverages(self.product, self.item_desc)
        new_options = list(getattr(self, 'options', ()))
        for elem in new_options:
            if elem.coverage not in available_coverages:
                new_options.remove(elem)
            else:
                available_coverages.remove(elem.coverage)
        Option = Pool().get('contract.option')
        for elem in available_coverages:
            if elem.subscription_behaviour == 'optional':
                continue
            new_options.append(Option.new_option_from_coverage(elem,
                    self.product, self.main_contract.start_date,
                    item_desc=self.item_desc))
        self.options = new_options

    def update_extra_data(self, version):
        if not self.item_desc or not self.product:
            version.extra_data = {}
            return

        for k, v in self.party_extra_data.iteritems():
            if k not in version.extra_data:
                version.extra_data[k] = v
        version.extra_data = self.product.get_extra_data_def('covered_element',
            version.extra_data, self.main_contract.start_date,
            item_desc=self.item_desc)
        if self.party:
            self.party_extra_data = {k: v
                for k, v in version.extra_data.iteritems()}

    def get_relation_with_subscriber(self):
        if not self.party:
            return
        subscriber = self.contract.subscriber
        kinds = [rel.type.name for rel in self.party.relations
            if rel.to.id == subscriber.id]
        return ', '.join(kinds)

    @classmethod
    def get_coverages(cls, product, item_desc):
        return [x.coverage for x in product.ordered_coverages
            if x.coverage.item_desc == item_desc]

    def init_options(self, product, start_date):
        existing = dict(((x.coverage, x) for x in getattr(
                    self, 'options', [])))
        good_options = []
        to_delete = [elem for elem in existing.itervalues()]
        OptionModel = Pool().get('contract.option')
        for coverage in self.get_coverages(product, self.item_desc):
            good_opt = None
            if coverage in existing:
                good_opt = existing[coverage]
                to_delete.remove(good_opt)
            elif coverage.subscription_behaviour == 'mandatory':
                good_opt = OptionModel.new_option_from_coverage(coverage,
                    product, start_date)
            if good_opt:
                good_opt.save()
                good_options.append(good_opt)
        if to_delete:
            OptionModel.delete(to_delete)
        self.options = good_options

    def check_at_least_one_covered(self):
        for option in self.options:
            if option.status == 'active':
                return True
        return False

    def get_extra_data_def(self, at_date=None):
        res = []
        if (self.item_desc and self.item_desc.kind not in
                ['party', 'person', 'company']):
            res.extend(self.item_desc.extra_data_def)
        res.extend(self.product.get_extra_data_def(['elem'], at_date=at_date))
        return res

    def get_party_extra_data_def(self):
        if (self.item_desc and self.item_desc.kind in
                ['party', 'person', 'company']):
            return self.item_desc.extra_data_def

    def is_covered_at_date(self, at_date, coverage=None):
        for option in self.options:
            if ((not coverage or option.coverage == coverage) and
                    option.status not in ['void', 'declined'] and
                    utils.is_effective_at_date(option, at_date,
                        end_var_name='final_end_date')):
                return True
        return any((sub_elem.is_covered_at_date(at_date, coverage)
                for sub_elem in self.sub_covered_elements))

    def is_party_covered(self, party, at_date):
        # TODO : Maybe this should go in contract_life / claim
        if party in self.get_covered_parties(at_date):
            for option in self.options:
                if option.status != 'void' and utils.is_effective_at_date(
                        option, at_date, end_var_name='final_end_date'):
                    return True
        if hasattr(self, 'sub_covered_elements'):
            for sub_elem in self.sub_covered_elements:
                if sub_elem.is_party_covered(party, at_date):
                    return True
        return False

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
        # TODO : Maybe this should be set in claim
        # TODO : To enhance with status control on contract and option linked
        domain = [
            ('party', '=', party.id),
            ('options.start_date', '<=', at_date),
            # ['OR',
            #     ['options.end_date', '=', None],
            #     ['options.end_date', '>=', at_date]],
            ]
        if 'company' in Transaction().context:
            domain.append(
                ('contract.company', '=', Transaction().context['company']))
        return cls.search([domain])

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

    def get_all_extra_data(self, at_date):
        current_version = self.get_version_at_date(at_date)
        res = current_version.extra_data if current_version else {}
        if self.contract:
            res.update(self.contract.get_all_extra_data(at_date))
        return res

    def init_dict_for_rule_engine(self, args):
        args['elem'] = self
        if self.contract:
            self.contract.init_dict_for_rule_engine(args)
        elif self.parent:
            self.parent.init_dict_for_rule_engine(args)
        else:
            raise Exception('Orphan covered element')

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


class CoveredElementVersion(model.CoopSQL, model.CoopView):
    'Contract Covered Element Version'

    __name__ = 'contract.covered_element.version'
    _func_key = 'start'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', required=True, ondelete='CASCADE', select=True)
    start = fields.Date('Start')
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={
            'invisible': ~Eval('extra_data'),
            },
        depends=['extra_data'])
    extra_data_as_string = fields.Function(
        fields.Char('Extra Data'),
        'on_change_with_extra_data_as_string')
    extra_data_string = extra_data.translated('extra_data')

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

    @fields.depends('extra_data')
    def on_change_with_extra_data_as_string(self, name=None):
        if not self.extra_data:
            return ''
        return Pool().get('extra_data').get_extra_data_summary([self],
            'extra_data')[self.id]

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


class CoveredElementPartyRelation(model.CoopSQL):
    'Relation between Covered Element and Covered Relations'

    __name__ = 'contract.covered_element-party'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    party_relation = fields.Many2One('party.relation.all', 'Party Relation',
        ondelete='RESTRICT')


class ExtraPremium(model.CoopSQL, model.CoopView, ModelCurrency):
    'Extra Premium'

    __name__ = 'contract.option.extra_premium'

    calculation_kind = fields.Selection('get_possible_extra_premiums_kind',
        'Calculation Kind')
    calculation_kind_string = calculation_kind.translated('calculation_kind')
    start_date = fields.Function(
        fields.Date('Start Date'), 'get_start_date', setter='setter_void')
    manual_start_date = fields.Date('Manual Start date')
    end_date = fields.Function(fields.Date('End date',
        states={'invisible': ~Eval('time_limited')},
        depends=['time_limited']),
        'get_end_date')
    manual_end_date = fields.Date('Manual End Date')
    final_end_date = fields.Function(
        fields.Date('Final End Date'),
        'get_final_end_date')
    duration = fields.Integer('Duration', states={
            'invisible': ~Eval('time_limited')}, depends=['time_limited'])
    duration_unit = fields.Selection(
        [('month', 'Month'), ('year', 'Year')],
        'Duration Unit', sort=False, required=True, states={
            'invisible': ~Eval('time_limited')}, depends=['time_limited'])
    duration_unit_string = duration_unit.translated('duration_unit')
    time_limited = fields.Function(
        fields.Boolean('Time Limited'), 'get_time_limited',
        setter='setter_void')
    flat_amount = fields.Numeric('Flat amount', states={
            'invisible': Eval('calculation_kind', '') != 'flat',
            'required': Eval('calculation_kind', '') == 'flat',
            }, digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits', 'calculation_kind', 'is_discount',
                 'max_value'],
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
        ondelete='RESTRICT', required=True)
    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE',
        states={'invisible': ~Eval('option')}, select=True, required=True)
    rate = fields.Numeric('Rate on Premium', states={
            'invisible': Eval('calculation_kind', '') != 'rate',
            'required': Eval('calculation_kind', '') == 'rate'},
        digits=(16, 4), depends=['calculation_kind', 'is_discount',
                                 'max_rate'],
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
        cls._error_messages.update({
                'bad_start_date': 'Extra premium %s start date (%s) should be '
                'greater than the coverage\'s (%s)'})
        cls._buttons.update({'propagate': {}})

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

    @fields.depends('value_as_string')
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
        return '%s %s %s' % (self.option.rec_name,
            self.get_value_as_string(name), self.motive.name)

    def get_value_as_string(self, name):
        if self.calculation_kind == 'flat' and self.flat_amount:
            return self.currency.amount_as_string(abs(self.flat_amount))
        elif self.calculation_kind == 'rate' and self.rate:
            return '%s %%' % coop_string.format_number('%.2f',
                abs(self.rate) * 100)

    def get_time_limited(self, name):
        return self.duration != 0 or self.manual_end_date

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
                extra.raise_user_error('bad_start_date', (extra.motive.name,
                        extra.start_date, extra.option.start_date))

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
        if self.manual_end_date:
            return min(self.manual_end_date, self.calculate_end_date())
        return self.calculate_end_date()

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


class OptionExclusionKindRelation(model.CoopSQL):
    'Option to Exclusion Kind relation'

    __name__ = 'contract.option-exclusion.kind'

    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE',
        required=True, select=True)
    exclusion = fields.Many2One('offered.exclusion', 'Exclusion',
        ondelete='RESTRICT', required=True, select=True)
