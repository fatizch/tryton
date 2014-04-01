import datetime
import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Or, Bool
from trytond.transaction import Transaction
from trytond.model import ModelView

from trytond.modules.cog_utils import model, fields
from trytond.modules.cog_utils import utils, coop_date
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency
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
    'ContractAgreementRelation',
    ]

_STATES = {
    'readonly': Eval('status') != 'quote',
    }
_DEPENDS = ['status']


class Contract(Printable):
    __name__ = 'contract'

    agreements = fields.One2Many('contract-agreement', 'contract',
        'Contract-Agreement Relations', states={
            'invisible': Eval('product_kind') != 'insurance',
            'readonly': Eval('status') != 'quote',
            }, depends=['status', 'product_kind'])
    contracts = fields.One2Many('contract-agreement',
        'protocol', 'Managing Roles', states={
            'invisible': Eval('product_kind') == 'insurance',
            'readonly': Eval('status') != 'quote',
            }, depends=['status', 'product_kind'])
    covered_elements = fields.One2ManyDomain('contract.covered_element',
        'contract', 'Covered Elements', domain=[('parent', '=', None)],
        context={
            'contract': Eval('id'),
            'product': Eval('product'),
            'start_date': Eval('start_date'),
            },
        states=_STATES, depends=['status', 'id', 'product', 'start_date'])
    documents = fields.One2Many('document.request', 'needed_by', 'Documents',
        states=_STATES, depends=_DEPENDS, size=1)
    last_renewed = fields.Date('Last Renewed', states=_STATES,
        depends=_DEPENDS)
    next_renewal_date = fields.Date('Next Renewal Date', states=_STATES,
        depends=_DEPENDS)
    multi_mixed_view = covered_elements

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'manage_extra_premium': {},
                'create_extra_premium': {},
                })

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
                        'sub_elem': covered_element,
                        'option': option,
                    })
                res = res and (not eligibility or eligibility.eligible)
                if eligibility:
                    errs += eligibility.details
                errs += errors
        return (res, errs)

    def init_from_product(self, product, start_date=None, end_date=None):
        res = super(Contract, self).init_from_product(product, start_date,
            end_date)
        self.last_renewed = self.start_date
        self.next_renewal_date = None
        self.next_renewal_date, errors = self.product.get_result(
            'next_renewal_date', {
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date,
                'contract': self})
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

    def init_covered_elements(self):
        for elem in self.covered_elements:
            Option = Pool().get('contract.option')
            if getattr(elem, 'options'):
                existing_options = dict([
                    (option.coverage, option)
                    for option in elem.options])
            else:
                existing_options = {}
            elem.options = []
            to_delete = [option for option in existing_options.itervalues()]
            good_options = []
            for coverage in self.product.coverages:
                if coverage in existing_options:
                    existing_options[coverage].init_extra_data()
                    good_options.append(existing_options[coverage])
                    to_delete.remove(existing_options[coverage])
                    continue
                else:
                    good_option = Option()
                    good_option.init_from_covered_element(elem)
                    good_option.init_from_coverage(coverage)
                    good_option.status_selection = True
                    good_option.append(good_option)
            Option.delete(to_delete)
            elem.options = good_options
            elem.save()
        return True, ()

    def get_agreement(self, kind, party=None, only_active_at_date=False,
            at_date=None):
        if only_active_at_date:
            roles = utils.get_good_versions_at_date(self, 'agreements',
                at_date)
        elif not utils.is_none(self, 'agreements'):
            roles = self.agreements
        else:
            roles = []
        good_roles = [x for x in roles if (not x.kind or x.kind == kind)
            and (not party or x.party == party)]
        return good_roles[0] if len(good_roles) == 1 else None

    def get_or_create_agreement(self, kind, party):
        role = self.get_agreement(kind, party)
        if not role:
            role = utils.instanciate_relation(self, 'agreements')
            role.party = party
            role.kind = kind
            if utils.is_none(self, 'agreements'):
                self.agreements = []
            else:
                self.agreements = list(self.agreements)
            self.agreements.append(role)
        return role

    def get_protocol_offered(self, kind):
        #what if several protocols exist?
        return None

    def update_agreements(self):
        #This method will update the management role and find the good protocol
        #based on real coverage subscribed
        if utils.is_none(self, 'agreements'):
            return
        for role in [x for x in self.agreements]:
            #we browse all roles that need to be updated on contract
            if not role.protocol:
                protocol_offered = self.get_protocol_offered(role.kind)
                if not protocol_offered:
                    #TODO : We can't find anything
                    return
                contracts = self.search_contract(protocol_offered, role.party,
                    self.start_date)
                protocol = None
                if len(contracts) == 1:
                    protocol = contracts[0]
                elif len(contracts) > 1:
                    #TODO
                    raise
                else:
                    protocol = self.subscribe_contract(protocol_offered,
                        role.party, protocol_offered.start_date)
                    protocol.save()
                role.protocol = protocol.id
            role.start_date = self.start_date
            role.save()

    def get_next_renewal_date(self):
        # TODO : make it better than just "yearly"
        return coop_date.add_frequency('yearly', self.start_date)

    def finalize_contract(self):
        super(Contract, self).finalize_contract()
        self.update_agreements()

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
        return Pool().get('extra_data').check_extra_data(self, 'extra_data')

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


class ContractOption:
    __name__ = 'contract.option'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    exclusions = fields.Many2Many('contract.option-exclusion.kind',
        'option', 'exclusion', 'Exclusions')
    extra_data = fields.Dict('extra_data', 'Complementary Data',
        states={'invisible': ~Eval('extra_data')}, depends=['extra_data'])
    extra_premiums = fields.One2Many('contract.option.extra_premium',
        'option', 'Extra Premiums')
    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')
    parent_option = fields.Function(
        fields.Many2One('contract.option', 'Parent Covered Data'),
        'on_change_with_parent_option')

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._buttons.update({
                'propagate_extra_premiums': {},
                'propagate_exclusions': {},
                })

    @fields.depends('extra_data', 'coverage', 'covered_element.contract')
    def on_change_with_extra_data(self):
        if (not self.covered_element or self.covered_element.id < 0
                or not self.coverage):
            return {}
        args = {'date': self.start_date, 'level': 'option'}
        self.init_dict_for_rule_engine(args)
        return self.covered_element.contract.product.get_result(
                'calculated_extra_datas', args)[0]

    @fields.depends('covered_element', 'start_date')
    def on_change_with_appliable_conditions_date(self, name=None):
        if not self.covered_element:
            return super(ContractOption,
                self).on_change_with_appliable_conditions_date()
        contract = getattr(self.covered_element, 'contract', None)
        return (contract.appliable_conditions_date if
            contract else self.start_date)

    @fields.depends('covered_element')
    def on_change_with_end_date(self, name=None):
        if self.covered_element:
            return self.covered_element.contract.end_date
        return super(ContractOption, self).on_change_with_end_date(name)

    def on_change_with_icon(self, name=None):
        return 'umbrella-black'

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

    @fields.depends('covered_element')
    def on_change_with_start_date(self, name=None):
        if self.covered_element:
            return self.covered_element.contract.start_date
        return super(ContractOption, self).on_change_with_start_date(name)

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
            ['sub_elem'])

    def init_extra_data(self):
        self.extra_data = getattr(self, 'extra_data', {})
        self.extra_data.update(self.on_change_extra_data()['extra_data'])

    def init_from_coverage(self, coverage):
        self.coverage = coverage
        self.init_extra_data()

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
        args['data'] = self
        args['extra_premiums'] = []
        for elem in getattr(self, 'extra_premiums', []):
            if elem.start_date <= args['date'] <= (elem.end_date or
                    datetime.date.max):
                args['extra_premiums'].append(elem)
        self.covered_element.init_dict_for_rule_engine(args)
        self.coverage.init_dict_for_rule_engine(args)

    def get_publishing_values(self):
        result = super(ContractOption, self).get_publishing_values()
        result['offered'] = self.coverage
        return result


class CoveredElement(model.CoopSQL, model.CoopView, ModelCurrency):
    'Covered Element'
    '''
        Covered elements represents anything which is covered by at least one
        option of the contract.
        It has a list of covered datas which describes which options covers
        element and in which conditions.
        It could contains recursively sub covered element (fleet or population)
    '''

    __name__ = 'contract.covered_element'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        states={'invisible': ~Eval('contract')}, depends=['contract'])
    covered_relations = fields.Many2Many('contract.covered_element-party',
        'covered_element', 'party_relation', 'Covered Relations', domain=[
            'OR',
            [('from_party', '=', Eval('party'))],
            [('to_party', '=', Eval('party'))],
            ], depends=['party'],
        states={'invisible': ~IS_PARTY})
    extra_data = fields.Dict('extra_data', 'Contract Complementary Data',
        states={'invisible': ~Eval('extra_data')})
    #We need to put complementary data in depends, because the complementary
    #data are set through on_change_with and the item desc can be set on an
    #editable tree, or we can not display for the moment dictionnary in tree
    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        domain=[If(
                ~~Eval('possible_item_desc'),
                ('id', 'in', Eval('possible_item_desc')),
                ())],
            depends=['possible_item_desc', 'extra_data'],
            ondelete='RESTRICT')
    name = fields.Char('Name', states={'invisible': IS_PARTY})
    options = fields.One2Many('contract.option', 'covered_element', 'Options',
        context={'covered_element': Eval('id')}, depends=['id'])
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
        fields.Char('Complementary Data'),
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
    # The link to use either for direct covered element or sub covered element
    main_contract = fields.Function(
        fields.Many2One('contract', 'Contract',
            states={'invisible': Bool(Eval('contract'))},
            depends=['contract']),
        'on_change_with_main_contract')
    party_extra_data = fields.Function(
        fields.Dict('extra_data', 'Party Complementary Data',
            states={'invisible': Or(~IS_PARTY, ~Eval('party_extra_data'))},
            depends=['party_extra_data', 'item_kind']),
        'on_change_with_party_extra_data', 'set_party_extra_data')
    possible_item_desc = fields.Function(
        fields.Many2Many('offered.item.description', None, None,
            'Possible Item Desc', states={'invisible': True}),
        'on_change_with_possible_item_desc')
    multi_mixed_view = options

    @classmethod
    def default_item_desc(cls):
        item_descs = cls.get_possible_item_desc()
        if len(item_descs) == 1:
            return item_descs[0].id

    @classmethod
    def default_main_contract(cls):
        result = Transaction().context.get('contract')
        return result if result and result > 0 else None

    @classmethod
    def default_options(cls):
        master = cls.get_parent_in_transaction()
        if not master:
            return []
        Option = Pool().get('contract.option')
        result = []
        for option in master.options:
            tmp_covered = Option()
            tmp_covered.coverage = option.coverage
            result.append(tmp_covered)
        return model.serialize_this(result)

    @classmethod
    def default_possible_item_desc(cls):
        return [x.id for x in cls.get_possible_item_desc()]

    @fields.depends('item_desc', 'extra_data', 'party', 'main_contract',
        'start_date')
    def on_change_item_desc(self):
        res = {}
        if not (getattr(self, 'item_desc', None)):
            res['extra_data'] = {}
        else:
            res['extra_data'] = self.on_change_with_extra_data()
        res['item_kind'] = self.on_change_with_item_kind()
        res['party_extra_data'] = self.on_change_with_party_extra_data()
        return res

    @fields.depends('party')
    def on_change_with_covered_name(self, name=None):
        if self.party:
            return self.party.rec_name
        return ''

    @fields.depends('item_desc', 'extra_data', 'contract', 'start_date',
        'main_contract')
    def on_change_with_extra_data(self):
        return utils.init_extra_data(self.get_extra_data_def())

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

    @fields.depends('item_desc', 'extra_data', 'party')
    def on_change_with_party_extra_data(self, name=None):
        res = {}
        if utils.is_none(self, 'party') or not (self.item_desc
                and self.item_desc.kind in ['party', 'person', 'company']):
            return res
        for extra_data_def in self.item_desc.extra_data_def:
            if (self.party and not utils.is_none(self.party, 'extra_data')
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
    def on_change_with_possible_item_desc(self, name=None):
        return [x.id for x in
            self.get_possible_item_desc(self.main_contract, self.parent)]

    @classmethod
    def set_party_extra_data(cls, instances, name, vals):
        #We'll update the party complementary data with existing key or add new
        #keys, but if others keys already exist we won't modify them
        Party = Pool().get('party.party')
        for covered in instances:
            if not covered.party:
                continue
            if utils.is_none(covered.party, 'extra_data'):
                Party.write([covered.party], {'extra_data': vals})
            else:
                covered.party.extra_data.update(vals)
                covered.party.save()

    @classmethod
    def write(cls, cov_elements, vals):
        if 'sub_covered_elements' in vals:
            for cov_element in cov_elements:
                for val in vals['sub_covered_elements']:
                    if val[0] == 'create':
                        for sub_cov_elem in val[1]:
                            sub_cov_elem['contract'] = cov_element.contract.id
        super(CoveredElement, cls).write(cov_elements, vals)

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['name', 'sub_covered_elements', 'extra_data', 'party',
            'covered_relations']

    @classmethod
    def get_parent_in_transaction(cls):
        if not '_master_covered' in Transaction().context:
            return None
        GoodModel = Pool().get(cls.__name__)
        return GoodModel(Transaction().context.get('_master_covered'))

    def get_name_for_info(self):
        return self.get_rec_name('info')

    def get_rec_name(self, value):
        if self.party:
            return self.party.rec_name
        res = super(CoveredElement, self).get_rec_name(value)
        if self.item_desc:
            res = coop_string.concat_strings(
                self.item_desc.get_rec_name(value), res)
            if self.name:
                res = '%s : %s' % (res, self.name)
        elif self.name:
            res = coop_string.concat_strings(res, self.name)
        return res

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
        if (self.item_desc and not self.item_desc.kind in
                ['party', 'person', 'company']):
            res.extend(self.item_desc.extra_data_def)
        res.extend(product.get_extra_data_def(['sub_elem'], at_date=at_date))
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
        #TODO : To enhance with status control on contract and option linked
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

    @classmethod
    def get_possible_item_desc(cls, contract=None, parent=None):
        pool = Pool()
        if not parent:
            parent = cls.get_parent_in_transaction()
        if parent and parent.item_desc:
            return parent.item_desc.sub_item_descs
        if not contract:
            Contract = pool.get('contract')
            contract = Contract(Transaction().context.get('contract'))
            if contract.id <= 0:
                contract = None
        if contract and contract.product:
            return contract.product.item_descriptors
        product = Transaction().context.get('product', None)
        if product:
            Product = pool.get('offered.product')
            return Product(product).item_descriptors
        return []

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
        res = getattr(self, 'extra_data', {})
        res.update(getattr(self, 'party_extra_data', {}))
        return res

    def init_dict_for_rule_engine(self, args):
        if self.contract:
            args['elem'] = self
            self.contract.init_dict_for_rule_engine(args)
        elif self.parent:
            args['sub_elem'] = self
            self.parent.init_dict_for_rule_engine(args)
        else:
            raise Exception('Orphan covered element')

    def get_publishing_values(self):
        result = super(CoveredElement, self).get_publishing_values()
        result['party'] = self.party
        return result


class CoveredElementPartyRelation(model.CoopSQL):
    'Relation between Covered Element and Covered Relations'

    __name__ = 'contract.covered_element-party'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    party_relation = fields.Many2One('party.relation', 'Party Relation',
        ondelete='RESTRICT')


class ExtraPremium(model.CoopSQL, model.CoopView, ModelCurrency):
    'Extra Premium'

    __name__ = 'contract.option.extra_premium'

    calculation_kind = fields.Selection('get_possible_extra_premiums_kind',
        'Calculation Kind')
    end_date = fields.Date('End date', states={
            'invisible': ~Eval('time_limited')}, depends=['time_limited'])
    flat_amount = fields.Numeric('Flat amount', states={
            'invisible': Eval('calculation_kind', '') != 'flat',
            'required': Eval('calculation_kind', '') == 'flat',
            }, digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits', 'calculation_kind'])
    motive = fields.Many2One('extra_premium.kind', 'Motive',
        ondelete='RESTRICT', states={'required': True})
    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE')
    rate = fields.Numeric('Rate on Premium', states={
            'invisible': Eval('calculation_kind', '') != 'rate',
            'required': Eval('calculation_kind', '') == 'rate'},
        digits=(16, 4), depends=['calculation_kind'])
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

    @fields.depends('calculation_kind', 'flat_amount', 'rate')
    def on_change_with_rec_name(self, name=None):
        return self.get_rec_name(name)

    def get_currency(self):
        return self.option.currency if self.option else None

    def get_possible_extra_premiums_kind(self):
        return list(POSSIBLE_EXTRA_PREMIUM_RULES)

    def get_rec_name(self, name):
        if self.calculation_kind == 'flat' and self.flat_amount:
            return self.currency.amount_as_string(self.flat_amount)
        elif self.calculation_kind == 'rate' and self.rate:
            return '%s %%' % coop_string.format_number('%.2f',
                self.rate * 100)
        else:
            return super(ExtraPremium, self).get_rec_name(name)

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


class OptionExclusionKindRelation(model.CoopSQL):
    'Option to Exclusion Kind relation'

    __name__ = 'contract.option-exclusion.kind'

    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE')
    exclusion = fields.Many2One('offered.exclusion', 'Exclusion',
        ondelete='RESTRICT')


class ContractAgreementRelation(model.CoopSQL, model.CoopView):
    'Contract-Agreement Relation'

    __name__ = 'contract-agreement'

    agency = fields.Many2One('party.address', 'Agency', ondelete='RESTRICT',
        domain=[('party', '=', Eval('party'))], depends=['party'])
    contact_info = fields.Char('Contact Information')
    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    end_date = fields.Date('End Date', states={
            'invisible': Eval('_parent_contract', {}).get('status') == 'quote',
            })
    kind = fields.Selection([('', '')], 'Kind')
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT',
        readonly=True)
    protocol = fields.Many2One('contract', 'Protocol', domain=[
            utils.get_versioning_domain('start_date', 'end_date'),
            ('product_kind', '!=', 'insurance'),
            ('subscriber', '=', Eval('party')),
            ], depends=['start_date', 'end_date', 'party'],
        #we only need to have a protocole when the management is effective
        states={'required': ~~Eval('start_date')},
        ondelete='RESTRICT',)
    start_date = fields.Date('Start Date', states={
            'invisible': Eval('_parent_contract', {}).get('status') == 'quote',
            })

    @classmethod
    def __setup__(cls):
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection = list(set(cls.get_possible_agreement_kind()))
        super(ContractAgreementRelation, cls).__setup__()

    @classmethod
    def get_possible_agreement_kind(cls):
        return [('', '')]
