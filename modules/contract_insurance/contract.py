import datetime

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Or, Bool, Len
from trytond.transaction import Transaction
from trytond.model import ModelView

from trytond.modules.cog_utils import model, fields
from trytond.modules.cog_utils import utils, coop_date
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.contract import _STATES, _DEPENDS, _CONTRACT_STATUS_STATES
from trytond.modules.contract import _CONTRACT_STATUS_DEPENDS
from trytond.modules.offered_insurance import Printable


IS_PARTY = Eval('item_kind').in_(['person', 'company', 'party'])

POSSIBLE_EXTRA_PREMIUM_RULES = [
    ('flat', 'Montant Fixe'),
    ('rate', 'Pourcentage'),
    ]

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    'CoveredElement',
    'CoveredElementPartyRelation',
    'ExtraPremium',
    'OptionExclusionKindRelation',
    ]


class Contract(Printable):
    __name__ = 'contract'

    covered_elements = fields.One2ManyDomain('contract.covered_element',
        'contract', 'Covered Elements',
        context={
            'contract': Eval('id'),
            'product': Eval('product'),
            'start_date': Eval('start_date'),
            'all_extra_datas': Eval('extra_data_values')},
        domain=[
            ('item_desc', 'in', Eval('possible_item_desc', [])),
            ('parent', '=', None)],
        states={
            'readonly': Eval('status') != 'quote',
            'invisible': Len(Eval('possible_item_desc', [])) <= 0,
            },
        depends=['status', 'id', 'product', 'start_date', 'extra_data_values',
            'possible_item_desc'])
    last_renewed = fields.Date('Last Renewed', states=_STATES,
        depends=_DEPENDS)
    next_renewal_date = fields.Date('Next Renewal Date', states=_STATES,
        depends=_DEPENDS)
    possible_item_desc = fields.Function(
        fields.Many2Many('offered.item.description', None, None,
            'Possible Item Desc', states={'invisible': True}),
        'on_change_with_possible_item_desc')
    multi_mixed_view = covered_elements

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'manage_extra_premium': {},
                'create_extra_premium': {},
                'generic_send_letter': {},
                })

    def calculate(self):
        super(Contract, self).calculate()
        for covered_element in self.covered_elements:
            covered_element.calculate()

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

    def check_sub_elem_eligibility(self, ext=None):
        errors = []
        res, errs = (True, [])
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                eligibility, errors = option.coverage.get_result(
                    'sub_elem_eligibility',
                    {
                        'date': self.start_date,
                        'appliable_conditions_date':
                        self.appliable_conditions_date,
                        'elem': covered_element,
                        'option': option,
                    })
                res = res and (not eligibility or eligibility.eligible)
                if eligibility:
                    errs += eligibility.details
                errs += errors
        return (res, errs)

    def init_from_product(self, product, start_date=None, end_date=None):
        super(Contract, self).init_from_product(product, start_date, end_date)
        self.last_renewed = self.start_date
        self.next_renewal_date = None
        self.next_renewal_date, errors = self.product.get_result(
            'next_renewal_date', {
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date,
                'contract': self})
        res = True, []
        if len(errors) == 1 and errors[0][0] == 'no_renewal_rule_configured':
            return res[0], []
        else:
            res = (res[0] and not errors, res[1] + errors)
            return res

    def check_at_least_one_covered(self):
        errors = []
        for covered in self.covered_elements:
            found, errors = covered.check_at_least_one_covered(errors)
            if found:
                break
        if errors:
            return False, errors
        return True, ()

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

    def get_next_renewal_date(self):
        # TODO : make it better than just "yearly"
        return coop_date.add_frequency('yearly', self.start_date)

    def renew(self):
        renewal_date = self.next_renewal_date
        self.next_renewal_date, errors = self.product.get_result(
            'next_renewal_date', {
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date,
                'contract': self})
        self.last_renewed = renewal_date
        if errors:
            return False
        prices_update, errs = self.calculate_prices_between_dates(renewal_date)
        if errors:
            return False
        self.store_prices(prices_update)
        return True

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

    def get_publishing_context(self, cur_context):
        result = super(Contract, self).get_publishing_context(cur_context)
        result['Insurers'] = [x.coverage.insurer.party for x in self.options]
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

    def set_end_date(self, end_date, force=False):
        super(Contract, self).set_end_date(end_date, force)
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                if not option.end_date:
                    option.end_date = end_date
            covered_element.options = covered_element.options
        self.covered_elements = self.covered_elements

    def get_maximum_end_date(self):
        contract_maximum = super(Contract, self).get_maximum_end_date()
        all_end_dates = [option.end_date
            for covered_elements in self.covered_elements
            for option in covered_elements.options]
        if contract_maximum is not None:
            all_end_dates.append(contract_maximum)
        if all_end_dates:
            return max(all_end_dates)
        else:
            return None

    def update_from_start_date(self):
        super(Contract, self).update_from_start_date()
        for covered_element in self.covered_elements:
            for option in covered_element.options:
                option.set_start_date(self.start_date)
                option.save()

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
            covered_element.start_date = contract_dict['start_date']
            covered_element.init_covered_element(product, item_desc, cov_dict)
            self.covered_elements.append(covered_element)

    @classmethod
    def _export_skips(cls):
        return super(Contract, cls)._export_skips() | set(['multi_mixed_view'])


class ContractOption:
    __name__ = 'contract.option'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', ondelete='CASCADE',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    exclusions = fields.Many2Many('contract.option-exclusion.kind',
        'option', 'exclusion', 'Exclusions',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={
            'invisible': ~Eval('extra_data'),
            'readonly': Eval('contract_status') != 'quote'
            },
        depends=['extra_data', 'contract_status'])
    extra_premiums = fields.One2Many('contract.option.extra_premium',
        'option', 'Extra Premiums',
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    extra_premium_discounts = fields.One2ManyDomain(
        'contract.option.extra_premium', 'option', 'Discounts',
        domain=[('motive.is_discount', '=', True)],
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    extra_premium_increases = fields.One2ManyDomain(
        'contract.option.extra_premium', 'option', 'Increases',
        domain=[('motive.is_discount', '=', False)],
        states=_CONTRACT_STATUS_STATES, depends=_CONTRACT_STATUS_DEPENDS)
    all_extra_datas = fields.Function(
        fields.Dict('extra_data', 'All Extra Datas'),
        'on_change_with_all_extra_data')
    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')
    parent_option = fields.Function(
        fields.Many2One('contract.option', 'Parent Covered Data'),
        'on_change_with_parent_option')
    parent_contract = fields.Function(
        fields.Many2One('contract', 'Parent Contract'),
        'on_change_with_parent_contract', searcher='search_parent_contract')

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._buttons.update({
                'propagate_extra_premiums': _CONTRACT_STATUS_STATES,
                'propagate_exclusions': _CONTRACT_STATUS_STATES,
                })

    @classmethod
    def default_all_extra_datas(cls):
        return {}

    @classmethod
    def default_extra_data(cls):
        return {}

    @fields.depends('all_extra_datas', 'start_date', 'coverage', 'contract',
        'appliable_conditions_date', 'product', 'covered_element')
    def on_change_coverage(self):
        super(ContractOption, self).on_change_coverage()
        self.on_change_extra_data()

    @fields.depends('extra_data', 'start_date', 'coverage', 'contract',
        'appliable_conditions_date', 'product', 'covered_element')
    def on_change_extra_data(self):
        if not self.coverage or not self.product:
            self.extra_data = {}
            self.all_extra_datas = self.on_change_with_all_extra_data()
            return
        item_desc_id = Transaction().context.get('item_desc', None)
        item_desc = None
        if not item_desc_id:
            if self.covered_element and self.covered_element.id > 0:
                item_desc = self.covered_element.item_desc
        else:
            item_desc = Pool().get('offered.item.description')(item_desc_id)
        self.extra_data = self.product.get_extra_data_def('option',
            self.on_change_with_all_extra_data(),
            self.appliable_conditions_date, coverage=self.coverage,
            item_desc=item_desc)
        self.all_extra_datas = self.on_change_with_all_extra_data()

    @fields.depends('covered_element', 'contract', 'extra_data')
    def on_change_with_all_extra_data(self, name=None):
        all_extra_datas = Transaction().context.get('all_extra_datas', {})
        if all_extra_datas:
            parent_extra_data = all_extra_datas
        elif self.contract and self.contract.id > 0:
            parent_extra_data = dict(self.contract.extra_data_values)
        elif self.covered_element and self.covered_element.id > 0:
            parent_extra_data = dict(self.covered_element.all_extra_datas)
        else:
            parent_extra_data = {}
        parent_extra_data.update(self.extra_data if self.extra_data else {})
        return parent_extra_data

    @fields.depends('covered_element', 'start_date')
    def on_change_with_appliable_conditions_date(self, name=None):
        if not self.covered_element:
            return super(ContractOption,
                self).on_change_with_appliable_conditions_date()
        contract = getattr(self.covered_element, 'contract', None)
        return (contract.appliable_conditions_date if
            contract else self.start_date)

    def on_change_with_icon(self, name=None):
        return 'umbrella-black'

    @fields.depends('contract', 'covered_element')
    def on_change_with_parent_contract(self, name=None):
        if self.contract:
            return self.contract.id
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
        if self.covered_element:
            return self.covered_element.contract.product.id
        return super(ContractOption, self).on_change_with_product(name)

    @fields.depends('parent_contract')
    def on_change_with_contract_status(self, name=None):
        return self.parent_contract.status if self.parent_contract else ''

    @classmethod
    def search_parent_contract(cls, name, clause):
        return ['OR',
            ('contract',) + tuple(clause[1:]),
            ('covered_element.contract',) + tuple(clause[1:]),
            ]

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_extra_premium')
    def propagate_extra_premiums(cls, options):
        pass

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_exclusion')
    def propagate_exclusions(cls, options):
        pass

    def get_rec_name(self, name):
        return self.coverage.name

    def get_extra_data_def(self):
        return self.coverage.get_extra_data_def(
            ['elem'])

    @classmethod
    def new_option_from_coverage(cls, coverage, product,
            start_date, end_date=None, item_desc=None):
        new_option = super(ContractOption, cls).new_option_from_coverage(
            coverage, product, start_date, end_date)
        new_option.on_change_extra_data()
        return new_option

    def init_from_covered_element(self, covered_element):
        self.covered_element = covered_element

    def get_currency(self):
        return self.covered_element.currency if self.covered_element else None

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

    def get_all_extra_data(self, at_date):
        res = getattr(self, 'extra_data', {})
        res.update(self.covered_element.get_all_extra_data(at_date))
        if self.parent_option:
            res.update(self.parent_option.get_all_extra_data(at_date))
        return res

    def init_dict_for_rule_engine(self, args):
        args['option'] = self
        args['extra_premiums'] = []
        for elem in getattr(self, 'extra_premiums', []):
            if elem.start_date <= args['date'] <= (elem.end_date or
                    datetime.date.max):
                args['extra_premiums'].append(elem)
        covered_element = getattr(self, 'covered_element', None)
        if covered_element is not None:
            covered_element.init_dict_for_rule_engine(args)
        self.coverage.init_dict_for_rule_engine(args)

    def get_publishing_values(self):
        result = super(ContractOption, self).get_publishing_values()
        result['offered'] = self.coverage
        return result

    def set_start_date(self, start_date):
        super(ContractOption, self).set_start_date(start_date)
        for extra_premium in self.extra_premiums:
            extra_premium.set_start_date(start_date)
            extra_premium.save()

    @classmethod
    def set_end_date(cls, options, name, end_date):
        Date = Pool().get('ir.date')
        to_write, to_super = [], []
        if not end_date:
            cls.raise_user_error('end_date_none')
        for option in options:
            if end_date > option.start_date:
                if not option.parent_contract:
                    to_super.append(option)
                    continue
                if end_date <= (option.parent_contract.end_date
                        or datetime.date.max):
                    to_write.append(option)
                else:
                    cls.raise_user_error('end_date_posterior_to_contract',
                        Date.date_as_string(
                            option.parent_contract.end_date))
            else:
                cls.raise_user_error('end_date_anterior_to_start_date',
                        Date.date_as_string(option.start_date))
        if to_write:
            cls.write(to_write, {'manual_end_date': end_date})
        if to_super:
            super(ContractOption, cls).set_end_date(to_super, name, end_date)

    def get_end_date(self, name):
        if not self.covered_element:
            return super(ContractOption, self).get_end_date(name)
        if self.manual_end_date:
            return self.manual_end_date
        elif (self.automatic_end_date and
                self.automatic_end_date > self.start_date):
            if self.parent_contract:
                return min(self.parent_contract.end_date or datetime.date.max,
                    self.automatic_end_date)
            else:
                return self.automatic_end_date
        elif self.parent_contract and self.parent_contract.end_date:
            return self.parent_contract.end_date


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
        states={'invisible': ~Eval('contract')}, depends=['contract'])
    covered_relations = fields.Many2Many('contract.covered_element-party',
        'covered_element', 'party_relation', 'Covered Relations', domain=[
            'OR',
            [('from_party', '=', Eval('party'))],
            [('to_party', '=', Eval('party'))],
            ], depends=['party'],
        states={'invisible': ~IS_PARTY})
    extra_data = fields.Dict('extra_data', 'Contract Extra Data',
        states={'invisible': ~Eval('extra_data')})
    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        depends=['product', 'options', 'extra_data'], ondelete='RESTRICT')
    name = fields.Char('Name', states={'invisible': IS_PARTY})
    options = fields.One2Many('contract.option', 'covered_element', 'Options',
        domain=[
            ('coverage.products', '=', Eval('product')),
            ('coverage.item_desc', '=', Eval('item_desc'))],
        context={
            'covered_element': Eval('id'),
            'item_desc': Eval('item_desc'),
            'all_extra_datas': Eval('all_extra_datas'),
            },
        depends=['id', 'item_desc', 'all_extra_datas', 'product'])
    parent = fields.Many2One('contract.covered_element', 'Parent',
        ondelete='CASCADE')
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
            }, ondelete='RESTRICT', depends=['item_kind'])
    sub_covered_elements = fields.One2Many('contract.covered_element',
        'parent', 'Sub Covered Elements',
        # TODO : invisibility should depend on a function field checking the
        # item desc definition
        states={'invisible': Eval('item_kind') == 'person'},
        depends=['contract', 'item_kind', 'id'],
        # TODO : Check usage of _master_covered, rename to 'covered' ?
        context={'_master_covered': Eval('id')})
    covered_name = fields.Function(
        fields.Char('Name'),
        'on_change_with_covered_name')
    extra_data_summary = fields.Function(
        fields.Char('Extra Data'),
        'on_change_with_extra_data_summary')
    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')
    is_person = fields.Function(
        fields.Boolean('Is Person', states={'invisible': True}),
        'on_change_with_is_person')
    item_kind = fields.Function(
        fields.Char('Item Kind', states={'invisible': True}),
        'on_change_with_item_kind')
    all_extra_datas = fields.Function(
        fields.Dict('extra_data', 'All Extra Datas'),
        'on_change_with_all_extra_data')
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
    product = fields.Function(
        fields.Many2One('offered.product', 'Product'),
        'on_change_with_product')
    party_code = fields.Function(
        fields.Char('Party Code'), 'get_party_code',
        searcher='search_party_code')

    multi_mixed_view = options

    def calculate(self):
        for option in self.options:
            option.calculate()

    def get_party_code(self, name):
        return self.party.code

    @classmethod
    def search_party_code(cls, name, clause):
        return [('party.code',) + tuple(clause[1:])]

    @classmethod
    def _export_skips(cls):
        return (super(CoveredElement, cls)._export_skips() |
            set(['multi_mixed_view']))

    @classmethod
    def _export_light(cls):
        return (super(CoveredElement, cls)._export_light() |
            set(['item_desc', 'product', 'contract', 'covered_relations']))

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
    def default_all_extra_datas(cls):
        return Transaction().context.get('all_extra_datas', {})

    @classmethod
    def default_extra_data(cls):
        return {}

    @classmethod
    def default_item_desc(cls):
        product_id = cls.default_product()
        if not product_id:
            return None
        product = Pool().get('offered.product')(product_id)
        if len(product.item_descriptors) == 1:
            return product.item_descriptors[0].id

    @classmethod
    def default_main_contract(cls):
        result = Transaction().context.get('contract')
        return result if result and result > 0 else None

    @classmethod
    def default_product(cls):
        product_id = Transaction().context.get('product', None)
        if product_id:
            return product_id
        contract_id = Transaction().context.get('contract', None)
        if contract_id:
            Contract = Pool().get('contract')
            return Contract(contract_id).product.id

    @fields.depends('extra_data', 'start_date', 'item_desc', 'contract',
        'appliable_conditions_date', 'product', 'party_extra_data')
    def on_change_extra_data(self):
        if not self.item_desc or not self.product:
            self.extra_data = {}
            self.all_extra_datas = self.on_change_with_all_extra_data()
            return

        self.all_extra_datas = self.on_change_with_all_extra_data()
        self.extra_data = self.product.get_extra_data_def('covered_element',
            self.on_change_with_all_extra_data(),
            self.appliable_conditions_date, item_desc=self.item_desc)

        if self.party_extra_data:
            self.party_extra_data.update(dict([
                        (key, value) for (key, value)
                        in self.extra_data.iteritems()
                        if key in self.party_extra_data]))
            self.party_extra_data = self.party_extra_data

    @fields.depends('item_desc', 'all_extra_datas', 'party', 'product',
        'start_date', 'options')
    def on_change_item_desc(self):
        if not self.start_date:
            self.start_date = Transaction().context.get('start_date', None)
        self.on_change_extra_data()
        self.item_kind = self.on_change_with_item_kind()
        self.party_extra_data = self.get_party_extra_data()
        # update extra_data dict with common extradata key from
        # party_extra_data

        self.extra_data.update(self.party_extra_data)

        if self.item_desc is None:
            self.options = []
            return
        available_coverages = self.get_coverages(self.product, self.item_desc)
        new_options = list(self.options)
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
                    self.product, item_desc=self.item_desc,
                    start_date=self.start_date))
        self.options = new_options

    @fields.depends('contract', 'extra_data')
    def on_change_with_all_extra_data(self, name=None):
        contract_extra_data = Transaction().context.get('all_extra_datas',
            {})
        if contract_extra_data is None:
            if self.contract and self.contract.id > 0:
                contract_extra_data = self.contract.extra_data
        result = dict(contract_extra_data)
        result.update(dict(self.extra_data if self.extra_data else {}))
        return result

    @fields.depends('party')
    def on_change_with_covered_name(self, name=None):
        if self.party:
            return self.party.rec_name
        return ''

    @fields.depends('extra_data')
    def on_change_with_extra_data_summary(self, name=None):
        if not self.extra_data:
            return ''
        return ' '.join([
            '%s: %s' % (x[0], x[1])
            for x in self.extra_data.iteritems()])

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

    def get_party_extra_data(self, name=None):
        res = {}
        if not getattr(self, 'party', None) or not (self.item_desc
                and self.item_desc.kind in ['party', 'person', 'company']):
            return res
        for extra_data_def in self.item_desc.extra_data_def:
            if (self.party and getattr(self.party, 'extra_data', None)
                    and extra_data_def.name in self.party.extra_data):
                res[extra_data_def.name] = self.party.extra_data[
                    extra_data_def.name]
            else:
                res[extra_data_def.name] = extra_data_def.get_default_value(
                    None)
        return res

    @fields.depends('contract', 'parent')
    def on_change_with_main_contract(self, name=None):
        contract = getattr(self, 'contract', None)
        if contract:
            return contract.id
        if 'contract' in Transaction().context:
            return Transaction().context.get('contract')
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
        return Transaction().context.get('product', None)

    @classmethod
    def set_party_extra_data(cls, instances, name, vals):
        Party = Pool().get('party.party')
        for covered in instances:
            if not covered.party:
                continue
            if not getattr(covered.party, 'extra_data', None):
                Party.write([covered.party], {'extra_data': vals})
            else:
                covered.party.extra_data.update(vals)
                covered.party.extra_data = covered.party.extra_data
                covered.party.save()

    @classmethod
    def write(cls, cov_elements, vals, *_args):
        # TODO : apply treatment to all parameters, not just the first ones
        if 'sub_covered_elements' in vals:
            for cov_element in cov_elements:
                for val in vals['sub_covered_elements']:
                    if val[0] == 'create':
                        for sub_cov_elem in val[1]:
                            sub_cov_elem['contract'] = cov_element.contract.id
        super(CoveredElement, cls).write(cov_elements, vals, *_args)

    def clean_up_versions(self, contract):
        Option = Pool().get('contract.option')
        if self.options:
            to_write = []
            for option in self.options:
                option.clean_up_versions(contract)
                to_write += [[option], option._save_values]
            if to_write:
                Option.write(*to_write)

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['name', 'sub_covered_elements', 'extra_data', 'party',
            'covered_relations']

    @classmethod
    def get_parent_in_transaction(cls):
        if '_master_covered' not in Transaction().context:
            return None
        GoodModel = Pool().get(cls.__name__)
        return GoodModel(Transaction().context.get('_master_covered'))

    def get_name_for_info(self):
        return self.get_rec_name('info')

    def get_rec_name(self, value):
        if self.party:
            return self.party.rec_name
        names = [super(CoveredElement, self).get_rec_name(value)]
        names.append(self.item_desc.rec_name if self.item_desc else None)
        names.append(self.name)
        return ' '.join([x for x in names if x])

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

    def check_at_least_one_covered(self, errors=None):
        if not errors:
            errors = []
        found = False
        for option in self.options:
            if option.status == 'active':
                found = True
                break
        if not found:
            errors.append(('need_option', (self.get_rec_name(''))))
        if errors:
            return False, errors
        return True, ()

    def get_extra_data_def(self, at_date=None):
        pool = Pool()
        contract = self.main_contract
        if not contract:
            Contract = pool.get('contract')
            contract_id = Transaction().context.get('contract')
            contract = None if contract_id <= 0 else Contract(contract_id)
        if contract:
            product = contract.product
        else:
            product_id = Transaction().context.get('product', None)
            if not product_id:
                return []
            Product = pool.get('offered.product')
            product = Product(product_id)
        res = []
        if (self.item_desc and self.item_desc.kind not in
                ['party', 'person', 'company']):
            res.extend(self.item_desc.extra_data_def)
        res.extend(product.get_extra_data_def(['elem'], at_date=at_date))
        return res

    def get_party_extra_data_def(self):
        if (self.item_desc and self.item_desc.kind in
                ['party', 'person', 'company']):
            return self.item_desc.extra_data_def

    def is_party_covered(self, party, at_date, option):
        # TODO : Maybe this should go in contract_life / claim
        if party in self.get_covered_parties(at_date):
            for option in self.options:
                if (utils.is_effective_at_date(option, at_date)
                        and option.option == option):
                    return True
        if hasattr(self, 'sub_covered_elements'):
            for sub_elem in self.sub_covered_elements:
                if sub_elem.is_party_covered(party, at_date, option):
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
        return res

    @classmethod
    def get_possible_covered_elements(cls, party, at_date):
        # TODO : Maybe this should be set in claim
        # TODO : To enhance with status control on contract and option linked
        domain = [
            ('party', '=', party.id),
            ('option.start_date', '<=', at_date),
            ['OR',
                ['option.end_date', '=', None],
                ['option.end_date', '>=', at_date]],
            ]
        if 'company' in Transaction().context:
            domain.append(
                ('contract.company', '=', Transaction().context['company']))
        return cls.search([domain])

    def get_currency(self):
        return self.main_contract.currency if self.main_contract else None

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
        res = getattr(self, 'party_extra_data', {})
        res.update(getattr(self, 'extra_data', {}))
        res.update(self.contract.get_all_extra_data(at_date))
        return res

    def init_dict_for_rule_engine(self, args):
        if self.contract:
            args['elem'] = self
            self.contract.init_dict_for_rule_engine(args)
        elif self.parent:
            args['elem'] = self
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
    end_date = fields.Date('End date', states={
            'invisible': ~Eval('time_limited')}, depends=['time_limited'])
    flat_amount = fields.Numeric('Flat amount', states={
            'invisible': Eval('calculation_kind', '') != 'flat',
            'required': Eval('calculation_kind', '') == 'flat',
            }, digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits', 'calculation_kind', 'is_discount',
                 'max_value'],
        domain= [If(Eval('calculation_kind', '') != 'flat',
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
        states={'invisible': ~Eval('option')})
    rate = fields.Numeric('Rate on Premium', states={
            'invisible': Eval('calculation_kind', '') != 'rate',
            'required': Eval('calculation_kind', '') == 'rate'},
        digits=(16, 4), depends=['calculation_kind', 'is_discount',
                                 'max_rate'],
        domain= [If(Eval('calculation_kind', '') != 'rate',
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
    start_date = fields.Date('Start date', states={
        'required': True,
        'invisible': ~Eval('time_limited'),
        }, depends=['time_limited'])
    duration = fields.Function(
        fields.Integer('Duration',
            states={'invisible': ~Eval('time_limited')}),
        'get_duration', 'setter_void')
    duration_unit = fields.Function(
        fields.Selection([('', ''), ('month', 'Month'), ('year', 'Year')],
            'Duration Unit', sort=False,
            states={'invisible': ~Eval('time_limited')}),
        'on_change_with_duration_unit', 'setter_void')
    duration_unit_string = duration_unit.translated('duration_unit')
    time_limited = fields.Function(
        fields.Boolean('Time Limited'),
        'on_change_with_time_limited', 'setter_void')

    @classmethod
    def __setup__(cls):
        super(ExtraPremium, cls).__setup__()
        cls._error_messages.update({
                'bad_start_date': 'Extra premium %s start date (%s) should be '
                'greater than the coverage\'s (%s)'})
        cls._buttons.update({'propagate': {}})

    @classmethod
    def default_calculation_kind(cls):
        return 'rate'

    @classmethod
    def default_end_date(cls):
        if 'end_date' in Transaction().context:
            return Transaction().context.get('end_date')
        return None

    @staticmethod
    def default_duration_unit():
        return 'month'

    @classmethod
    def default_start_date(cls):
        if 'start_date' in Transaction().context:
            return Transaction().context.get('start_date')
        return utils.today()

    @fields.depends('calculation_kind')
    def on_change_calculation_kind(self):
        if self.calculation_kind == 'flat':
            self.rate = None
        elif self.calculation_kind == 'rate':
            self.flat_amount = None

    @fields.depends('start_date', 'end_date')
    def on_change_with_duration_unit(self, name=None):
        res = (coop_date.duration_between_and_is_it_exact(
                self.start_date, self.end_date, 'month')
            if self.start_date and self.end_date else (None, False))
        if res[0] is not None and res[1]:
            return 'month'

    @fields.depends('start_date', 'end_date', 'duration', 'duration_unit')
    def on_change_with_end_date(self):
        if not self.duration or not self.duration_unit:
            return
        return coop_date.get_end_of_period(self.start_date, self.duration_unit,
            self.duration)

    @fields.depends('end_date')
    def on_change_with_time_limited(self, name=None):
        return self.end_date is not None

    @fields.depends('motive')
    def on_change_with_is_discount(self, name=None):
        return self.motive.is_discount if self.motive else False

    @fields.depends('motive')
    def on_change_with_max_value(self, name=None):
        return self.motive.max_value if self.motive else None

    @fields.depends('motive')
    def on_change_with_max_rate(self, name=None):
        return self.motive.max_rate if self.motive else None

    @fields.depends('calculation_kind', 'flat_amount', 'rate', 'currency')
    def on_change_with_rec_name(self, name=None):
        return self.get_rec_name(name)

    def get_currency(self):
        return self.option.currency if self.option else None

    def get_is_discount(self):
        return self.motive.is_discount if self.motive else False

    @staticmethod
    def get_possible_extra_premiums_kind():
        return list(POSSIBLE_EXTRA_PREMIUM_RULES)

    def get_rec_name(self, name):
        if self.calculation_kind == 'flat' and self.flat_amount:
            return self.currency.amount_as_string(abs(self.flat_amount))
        elif self.calculation_kind == 'rate' and self.rate:
            return '%s %%' % coop_string.format_number('%.2f',
                abs(self.rate) * 100)
        else:
            return super(ExtraPremium, self).get_rec_name(name)

    @classmethod
    def search_max_value(cls, name, clause):
        return [(('motive.max_value',) + tuple(clause[1:]))]

    @classmethod
    def search_max_rate(cls, name, clause):
        return [(('motive.max_rate',) + tuple(clause[1:]))]

    @classmethod
    def validate(cls, extra_premiums):
        # TODO : rewrite once start_date is properly defined on option
        for extra_premium in extra_premiums:
            if not extra_premium.start_date >= extra_premium.option.start_date:
                extra_premium.raise_user_error('bad_start_date',
                    (extra_premium.motive.name, extra_premium.start_date,
                        extra_premium.option.start_date))

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

    def get_duration(self, name):
        res = (coop_date.duration_between_and_is_it_exact(self.start_date,
                self.end_date, 'month')
            if self.start_date and self.end_date else (None, False))
        if res[0] is None or not res[1]:
            return None
        return res[0]

    def set_start_date(self, new_start_date):
        if self.start_date and self.start_date < new_start_date:
            self.start_date = new_start_date


class OptionExclusionKindRelation(model.CoopSQL):
    'Option to Exclusion Kind relation'

    __name__ = 'contract.option-exclusion.kind'

    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE')
    exclusion = fields.Many2One('offered.exclusion', 'Exclusion',
        ondelete='RESTRICT')
