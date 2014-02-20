import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Or, Bool, Equal
from trytond.transaction import Transaction
from trytond.model import ModelView

from trytond.modules.cog_utils import model, fields
from trytond.modules.cog_utils import utils, coop_date
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.contract import contract
from trytond.modules.offered_insurance import offered


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
    'CoveredData',
    'ExtraPremium',
    'CoveredDataExclusionKindRelation',
    'ContractAgreementRelation',
    ]


class Contract:
    __name__ = 'contract'

    covered_elements = fields.One2ManyDomain('contract.covered_element',
        'contract', 'Covered Elements', domain=[('parent', '=', None)],
        context={'contract': Eval('id')})
    covered_datas = fields.One2Many('contract.covered_data', 'contract',
        'Covered Datas')
    agreements = fields.One2Many('contract-agreement', 'contract',
        'Contract-Agreement Relations', states={
            'invisible': Eval('product_kind') != 'insurance'})
    contracts = fields.One2Many('contract-agreement',
        'protocol', 'Managing Roles', states={
            'invisible': Eval('product_kind') == 'insurance'})
    next_renewal_date = fields.Date('Next Renewal Date')
    last_renewed = fields.Date('Last Renewed')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'manage_extra_premium': {},
                'create_extra_premium': {},
                })

    def check_sub_elem_eligibility(self, at_date=None, ext=None):
        errors = []
        if not at_date:
            at_date = self.start_date
        options = dict(
            [(option.offered.code, option) for option in self.options])
        res, errs = (True, [])
        for covered_element in self.covered_elements:
            for covered_data in covered_element.covered_data:
                if (covered_data.start_date > at_date
                        or hasattr(covered_data, 'end_date') and
                        covered_data.end_date and
                        covered_data.end_date > at_date):
                    continue
                eligibility, errors = covered_data.get_coverage().get_result(
                    'sub_elem_eligibility',
                    {
                        'date': at_date,
                        'appliable_conditions_date':
                        self.appliable_conditions_date,
                        'sub_elem': covered_element,
                        'data': covered_data,
                        'option': options[covered_data.get_coverage().code]
                    })
                res = res and (not eligibility or eligibility.eligible)
                if eligibility:
                    errs += eligibility.details
                errs += errors
        return (res, errs)

    def init_from_offered(self, offered, start_date=None, end_date=None):
        res = super(Contract, self).init_from_offered(offered,
            start_date, end_date)
        self.last_renewed = self.start_date
        self.next_renewal_date = None
        self.next_renewal_date, errors = self.offered.get_result(
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
        options = dict([(o.offered.code, o) for o in self.options])
        for elem in self.covered_elements:
            CoveredData = utils.get_relation_model(elem, 'covered_data')
            if (hasattr(elem, 'covered_data') and elem.covered_data):
                existing_datas = dict([
                    (data.get_coverage().code, data)
                    for data in elem.covered_data])
            else:
                existing_datas = {}
            elem.covered_data = []
            to_delete = [data for data in existing_datas.itervalues()]
            good_datas = []
            for code, option in options.iteritems():
                if code in existing_datas:
                    existing_datas[code].init_extra_data()
                    good_datas.append(existing_datas[code])
                    to_delete.remove(existing_datas[code])
                    continue
                else:
                    good_data = CoveredData()
                    good_data.init_from_covered_element(elem)
                    good_data.init_from_option(option)
                    good_data.status_selection = True
                    good_datas.append(good_data)
            CoveredData.delete(to_delete)
            elem.covered_data = good_datas
            elem.save()
        return True, ()

    def init_options_from_covered_elements(self):
        if self.options:
            return True, ()
        self.options = []
        for coverage in [x.coverage for x in self.offered.ordered_coverages]:
            option = utils.instanciate_relation(self, 'options')
            option.init_from_offered(coverage, self.start_date)
            for covered_element in self.covered_elements:
                option.append_covered_data(covered_element)
            self.options.append(option)
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
        return coop_date.add_frequency('yearly', self.start_date)

    def finalize_contract(self):
        super(Contract, self).finalize_contract()
        self.update_agreements()

    def renew(self):
        renewal_date = self.next_renewal_date
        self.next_renewal_date, errors = self.offered.get_result(
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
        result['Insurers'] = [x.offered.insurer.party for x in self.options]
        return result


class ContractOption:
    __name__ = 'contract.option'

    covered_data = fields.One2ManyDomain('contract.covered_data', 'option',
        'Covered Data', domain=[('covered_element.parent', '=', None)])

    def append_covered_data(self, covered_element=None):
        res = utils.instanciate_relation(self.__class__, 'covered_data')
        if not hasattr(self, 'covered_data'):
            self.covered_data = []
        else:
            self.covered_data = list(self.covered_data)
        self.covered_data.append(res)
        res.init_from_covered_element(covered_element)
        res.init_from_option(self)
        return res

    def get_covered_data(self):
        raise NotImplementedError

    def get_coverage_amount(self):
        raise NotImplementedError


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
        states={'invisible': ~Eval('contract')})
    # The link to use either for direct covered element or sub covered element
    main_contract = fields.Function(
        fields.Many2One('contract', 'Contract',
            states={'invisible': Bool(Eval('contract'))}),
        'get_main_contract_id')
    #We need to put complementary data in depends, because the complementary
    #data are set through on_change_with and the item desc can be set on an
    #editable tree, or we can not display for the moment dictionnary in tree
    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        domain=[If(
                ~~Eval('possible_item_desc'),
                ('id', 'in', Eval('possible_item_desc')),
                ())], states={
                'invisible': Equal(Eval('possible_item_desc_nb', 0), 1)},
            depends=['possible_item_desc', 'extra_data',
                'possible_item_desc_nb'],
            ondelete='RESTRICT')
    possible_item_desc = fields.Function(
        fields.Many2Many('offered.item.description', None, None,
            'Possible Item Desc', states={'invisible': True}),
        'get_possible_item_desc_ids')
    possible_item_desc_nb = fields.Function(
        fields.Integer('Possible Item Desc Number',
            states={'invisible': True}),
        'on_change_with_possible_item_desc_nb')
    covered_data = fields.One2Many('contract.covered_data',
        'covered_element', 'Covered Element Data')
    name = fields.Char('Name', states={'invisible': IS_PARTY})
    parent = fields.Many2One('contract.covered_element', 'Parent')
    sub_covered_elements = fields.One2Many('contract.covered_element',
        'parent', 'Sub Covered Elements',
        states={'invisible': Eval('item_kind') == 'person'},
        domain=[('covered_data.option.contract', '=', Eval('contract'))],
        depends=['contract'], context={'_master_covered': Eval('id')})
    extra_data = fields.Dict('extra_data',
        'Contract Complementary Data', states={
            'invisible': ~Eval('extra_data')})
    party_extra_data = fields.Function(
        fields.Dict('extra_data', 'Party Complementary Data',
            states={'invisible': Or(~IS_PARTY, ~Eval('party_extra_data'))}),
        'on_change_with_party_extra_data', 'set_party_extra_data')
    extra_data_summary = fields.Function(
        fields.Char('Complementary Data'),
        'on_change_with_extra_data_summary')
    party = fields.Many2One('party.party', 'Actor', domain=[If(
                Eval('item_kind') == 'person',
                ('is_person', '=', True),
                (),
                ), If(
                Eval('item_kind') == 'company',
                ('is_company', '=', True),
                (),
                )
            ], ondelete='RESTRICT', states={
            'invisible': ~IS_PARTY,
            'required': IS_PARTY,
            }, depends=['item_kind'])
    is_person = fields.Function(
        fields.Boolean('Is Person', states={'invisible': True}),
        'on_change_with_is_person')
    covered_relations = fields.Many2Many('contract.covered_element-party',
        'covered_element', 'party_relation', 'Covered Relations', domain=[
            'OR',
            [('from_party', '=', Eval('party'))],
            [('to_party', '=', Eval('party'))],
            ], depends=['party'],
        states={'invisible': ~IS_PARTY})
    item_kind = fields.Function(
        fields.Char('Item Kind', states={'invisible': True}),
        'on_change_with_item_kind')
    covered_name = fields.Function(
        fields.Char('Name'),
        'on_change_with_covered_name')

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
        return ['name', 'sub_covered_elements',
            'extra_data', 'party', 'covered_relations']

    @classmethod
    def get_parent_in_transaction(cls):
        if not '_master_covered' in Transaction().context:
            return None
        GoodModel = Pool().get(cls.__name__)
        return GoodModel(Transaction().context.get('_master_covered'))

    @classmethod
    def default_covered_data(cls):
        master = cls.get_parent_in_transaction()
        if not master:
            return None
        CoveredData = Pool().get('contract.covered_data')
        result = []
        for covered_data in master.covered_data:
            tmp_covered = CoveredData()
            tmp_covered.option = covered_data.option
            tmp_covered.start_date = covered_data.start_date
            tmp_covered.end_date = covered_data.end_date
            result.append(tmp_covered)
        return model.serialize_this(result)

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
        for data in self.covered_data:
            if data.status == 'active':
                found = True
                break
        if not found:
            errors.append(('need_option', (self.get_rec_name(''))))
        if errors:
            return False, errors
        return True, ()

    @fields.depends('item_desc', 'extra_data', 'party', 'main_contract',
        'start_date')
    def on_change_item_desc(self):
        res = {}
        if not (hasattr(self, 'item_desc') and self.item_desc):
            res['extra_data'] = {}
        else:
            res['extra_data'] = \
                self.on_change_with_extra_data()
        res['item_kind'] = self.on_change_with_item_kind()
        res['party_extra_data'] = self.on_change_with_party_extra_data()
        return res

    @fields.depends('item_desc', 'extra_data', 'contract', 'start_date',
        'main_contract')
    def on_change_with_extra_data(self):
        return utils.init_extra_data(self.get_extra_data_def())

    @fields.depends('item_desc')
    def on_change_with_extra_data_summary(self, name=None):
        if not (hasattr(self, 'extra_data') and
                self.extra_data):
            return ''
        return ' '.join([
            '%s: %s' % (x[0], x[1])
            for x in self.extra_data.iteritems()])

    def get_main_contract_id(self, name):
        if not utils.is_none(self, 'contract'):
            return self.contract.id
        elif not utils.is_none(self, 'parent'):
            return self.parent.main_contract.id
        elif 'contract' in Transaction().context:
            return Transaction().context.get('contract')

    @fields.depends('item_desc', 'extra_data', 'party')
    def on_change_with_party_extra_data(self, name=None):
        res = {}
        if utils.is_none(self, 'party') or not (self.item_desc
                and self.item_desc.kind in ['party', 'person', 'company']):
            return res
        for extra_data_def in self.item_desc.extra_data_def:
            if (self.party
                    and not utils.is_none(self.party, 'extra_data')
                    and extra_data_def.name in self.party.extra_data):
                res[extra_data_def.name] = self.party.extra_data[
                    extra_data_def.name]
            else:
                res[extra_data_def.name] = extra_data_def.get_default_value(
                    None)
        return res

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

    def get_extra_data_def(self, at_date=None):
        contract = self.main_contract
        if not contract:
            Contract = Pool().get('contract')
            contract = Contract(Transaction().context.get('contract'))
        res = []
        if (self.item_desc
                and not self.item_desc.kind in ['party', 'person', 'company']):
            res.extend(self.item_desc.extra_data_def)
        res.extend(contract.offered.get_extra_data_def(
            ['sub_elem'], at_date=at_date))
        return res

    def get_party_extra_data_def(self):
        if (self.item_desc
                and self.item_desc.kind in ['party', 'person', 'company']):
            return self.item_desc.extra_data_def

    def init_from_party(self, party):
        self.party = party

    def is_party_covered(self, party, at_date, option):
        if party in self.get_covered_parties(at_date):
            for covered_data in self.covered_data:
                if (utils.is_effective_at_date(covered_data, at_date)
                        and covered_data.option == option):
                    return True
        if hasattr(self, 'sub_covered_elements'):
            for sub_elem in self.sub_covered_elements:
                if sub_elem.is_party_covered(party, at_date, option):
                    return True
        return False

    @fields.depends('item_desc')
    def on_change_with_item_kind(self, name=None):
        if self.item_desc:
            return self.item_desc.kind
        return ''

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

    @fields.depends('party')
    def on_change_with_covered_name(self, name=None):
        if self.party:
            return self.party.rec_name
        return ''

    @classmethod
    def get_possible_covered_elements(cls, party, at_date):
        #TODO : To enhance with status control on contract and option linked
        domain = [
            ('party', '=', party.id),
            ('covered_data.start_date', '<=', at_date),
            ['OR',
                ['covered_data.end_date', '=', None],
                ['covered_data.end_date', '>=', at_date]],
            ]
        if 'company' in Transaction().context:
            domain.append(
                ('contract.company', '=', Transaction().context['company']))
        return cls.search([domain])

    def get_currency(self):
        return self.main_contract.currency if self.main_contract else None

    @classmethod
    def get_possible_item_desc(cls, contract=None, parent=None):
        Contract = Pool().get('contract')
        if not parent:
            parent = cls.get_parent_in_transaction()
        if parent and parent.item_desc:
            return parent.item_desc.sub_item_descs
        if not contract:
            contract = Contract(Transaction().context.get('contract'))
        if contract and not utils.is_none(contract, 'offered'):
            return contract.offered.item_descriptors
        return []

    def get_possible_item_desc_ids(self, name):
        return [x.id for x in
            self.get_possible_item_desc(self.main_contract, self.parent)]

    @classmethod
    def default_item_desc(cls):
        item_descs = cls.get_possible_item_desc()
        if len(item_descs) == 1:
            return item_descs[0].id

    @classmethod
    def default_possible_item_desc(cls):
        return [x.id for x in cls.get_possible_item_desc()]

    def match_key(self, from_name=None, party=None):
        if (from_name and self.name == from_name
                or party and self.party == party):
            return True
        if party:
            for relation in self.covered_relations:
                if relation.from_party == party or relation.to_party == party:
                    return self

    def get_covered_element(self, from_name=None, party=None):
        if self.match_key(from_name, party):
            return self
        for sub_element in self.sub_covered_elements:
            if sub_element.match_key(from_name, party):
                return sub_element

    def get_all_extra_data(self, at_date):
        res = {}
        if not utils.is_none(self, 'extra_data'):
            res = self.extra_data
        if not utils.is_none(self, 'party_extra_data'):
            res.update(self.party_extra_data)
        return res

    def init_dict_for_rule_engine(self, args):
        args['sub_elem'] = self

    @fields.depends('party')
    def on_change_with_is_person(self, name=None):
        return self.party and self.party.is_person

    @classmethod
    def default_main_contract(cls):
        return Transaction().context.get('contract')

    @fields.depends('possible_item_desc')
    def on_change_with_possible_item_desc_nb(self, name=None):
        return len(self.possible_item_desc)

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


class CoveredData(model.CoopSQL, model.CoopView, ModelCurrency):
    'Covered Data'

    __name__ = 'contract.covered_data'

    option = fields.Many2One('contract.option', 'Contract Option',
        domain=[('id', 'in', Eval('possible_options'))],
        depends=['possible_options'], ondelete='CASCADE')
    possible_options = fields.Function(
        fields.Many2Many('contract.option', None, None,
            'Possible Options', states={'invisible': True}),
        'get_possible_options')
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    extra_data = fields.Dict('extra_data', 'Complementary Data',
        depends=['extra_data', 'option', 'start_date'],
        states={'invisible': ~Eval('extra_data')})
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    status = fields.Selection(contract.OPTIONSTATUS, 'Status')
    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_contract_id', searcher='search_contract')
    deductible_duration = fields.Many2One('offered.deductible.rule.duration',
        'Deductible Duration', states={
            'invisible': ~Eval('possible_deductible_duration'),
            # 'required': ~~Eval('possible_deductible_duration')
            }, domain=[('id', 'in', Eval('possible_deductible_duration'))],
        depends=['possible_deductible_duration'])
    possible_deductible_duration = fields.Function(
        fields.Many2Many(
            'offered.deductible.rule.duration', None, None,
            'Possible Deductible Duration', states={'invisible': True}),
        'get_possible_deductible_duration')
    parent_covered_data = fields.Function(
        fields.Many2One('contract.covered_data', 'Parent Covered Data'),
        'get_parent_covered_data_id')
    clauses = fields.One2Many('contract.clause', 'covered_data',
        'Clauses', context={'start_date': Eval('start_date')})
    exclusions = fields.Many2Many(
        'contract.covered_data-exclusion.kind', 'covered_data', 'exclusion',
        'Exclusions')
    extra_premiums = fields.One2Many('contract.covered_data.extra_premium',
        'covered_data', 'Extra Premiums', context={
            'start_date': Eval('start_date'), 'end_date': Eval('end_date')})

    @classmethod
    def __setup__(cls):
        super(CoveredData, cls).__setup__()
        cls._buttons.update({
                'propagate_extra_premiums': {},
                'propagate_exclusions': {},
                })

    @classmethod
    def default_status(cls):
        return 'active'

    def get_rec_name(self, name):
        return self.get_coverage().name

    def get_extra_data_def(self):
        return self.option.offered.get_extra_data_def(
            ['sub_elem'], at_date=self.start_date)

    def init_extra_data(self):
        if not (hasattr(self, 'extra_data') and
                self.extra_data):
            self.extra_data = {}
        self.extra_data = self.on_change_extra_data()[
            'extra_data']

    def init_clauses(self, option):
        clauses, errs = self.option.offered.get_result('all_clauses', {
                'date': option.start_date,
                'appliable_conditions_date':
                self.option.contract.appliable_conditions_date,
            })
        self.clauses = []
        if errs or not clauses:
            return
        ContractClause = Pool().get('contract.clause')
        for clause in clauses:
            new_clause = ContractClause()
            new_clause.clause = clause
            new_clause.text = clause.get_version_at_date(
                option.start_date).content
            new_clause.contract = option.contract
            self.clauses.append(new_clause)

    def init_from_option(self, option):
        self.option = option
        self.start_date = option.start_date
        self.end_date = option.end_date
        self.init_clauses(option)
        self.init_extra_data()

    @fields.depends('extra_data', 'option', 'start_date',
        'deductible_duration', 'covered_element')
    def on_change_extra_data(self):
        args = {'date': self.start_date, 'level': 'covered_data'}
        self.init_dict_for_rule_engine(args)
        return {'extra_data': self.option.contract.offered.get_result(
                'calculated_extra_datas', args)[0]}

    def init_from_covered_element(self, covered_element):
        self.covered_element = covered_element
        pass

    def get_coverage(self):
        if (hasattr(self, 'option') and self.option):
            return self.option.offered

    def get_contract_id(self, name):
        contract = self.option.contract if self.option else None
        return contract.id if contract else None

    def get_currency(self):
        return (self.covered_element.currency
            if self.covered_element else None)

    def get_possible_deductible_duration(self, name):
        try:
            durations = self.option.offered.get_result(
                'possible_deductible_duration', {
                    'date': self.start_date,
                    'appliable_conditions_date':
                    self.option.contract.appliable_conditions_date,
                    'scope': 'covered'},
                kind='deductible')[0]
            return [x.id for x in durations] if durations else []
        except offered.NonExistingRuleKindException:
            return []

    def get_deductible_duration(self):
        if not utils.is_none(self, 'deductible_duration'):
            return self.deductible_duration

    def get_possible_options(self, name):
        return [x.id for x in self.contract.options] if self.contract else []

    def get_covered_element(self, from_name=None, party=None):
        if self.covered_element:
            return self.covered_element.get_covered_element(from_name, party)

    def get_covered_data(self, from_name=None, party=None):
        covered_element = self.get_covered_element(from_name, party)
        if not covered_element:
            return
        for covered_data in covered_element.covered_data:
            if covered_data.option == self.option:
                return covered_data

    def _expand_tree(self, name):
        return True

    def get_all_extra_data(self, at_date):
        res = {}
        if not utils.is_none(self, 'extra_data'):
            res = self.extra_data
        res.update(self.covered_element.get_all_extra_data(at_date))
        res.update(self.option.get_all_extra_data(at_date))
        parent_covered_data = self.get_parent_covered_data()
        if parent_covered_data:
            res.update(parent_covered_data.get_all_extra_data(at_date))
        return res

    def init_dict_for_rule_engine(self, args):
        args['data'] = self
        args['deductible_duration'] = self.get_deductible_duration()
        if hasattr(self, 'extra_premiums'):
            args['extra_premiums'] = self.extra_premiums
        else:
            args['extra_premiums'] = []
        # if not utils.is_none(self, 'covered_element'):
        self.covered_element.init_dict_for_rule_engine(args)
        self.option.init_dict_for_rule_engine(args)

    def get_parent_covered_data(self):
        if (utils.is_none(self, 'covered_element')
                or not self.covered_element.parent):
            return None
        for covered_data in self.covered_element.parent.covered_data:
            if covered_data.option == self.option:
                return covered_data

    def get_parent_covered_data_id(self, name):
        covered_data = self.get_parent_covered_data()
        return covered_data.id if covered_data else None

    def is_active_at_date(self, date):
        if self.start_date > date:
            return False
        if not self.end_date or self.end_date <= date:
            return True
        return False

    @classmethod
    def search_contract(cls, name, clause):
        return [(('covered_element.contract',) + tuple(clause[1:]))]

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_extra_premium')
    def propagate_extra_premiums(cls, covered_datas):
        pass

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_exclusion')
    def propagate_exclusions(cls, covered_datas):
        pass

    def get_publishing_values(self):
        result = super(CoveredData, self).get_publishing_values()
        result['offered'] = self.option.offered
        return result


class ExtraPremium(model.CoopSQL, model.CoopView, ModelCurrency):
    'Extra Premium'

    __name__ = 'contract.covered_data.extra_premium'

    covered_data = fields.Many2One('contract.covered_data',
        'Covered Data', ondelete='CASCADE')
    motive = fields.Many2One('extra_premium.kind', 'Motive',
        ondelete='RESTRICT', states={'required': True})
    start_date = fields.Date('Start date', states={'required': True})
    end_date = fields.Date('End date')
    calculation_kind = fields.Selection('get_possible_extra_premiums_kind',
        'Calculation Kind', depends=['covered_data'])
    flat_amount = fields.Numeric('Flat amount', states={
            'invisible': Eval('calculation_kind', '') != 'flat',
            'required': Eval('calculation_kind', '') == 'flat',
            }, digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    rate = fields.Numeric('Rate on Premium', states={
            'invisible': Eval('calculation_kind', '') != 'rate',
            'required': Eval('calculation_kind', '') == 'rate'},
        digits=(16, 4))
    duration = fields.Function(
        fields.Integer('Duration'),
        'get_duration', 'setter_void')
    duration_unit = fields.Function(
        fields.Selection(coop_date.DAILY_DURATION, 'Duration Unit',
            sort=False),
        'get_duration_unit', 'setter_void')

    @classmethod
    def __setup__(cls):
        super(ExtraPremium, cls).__setup__()
        cls._error_messages.update({
                'bad_start_date': 'Extra premium %s start date (%s) should be '
                'greater than the coverage\'s (%s)'})
        cls._buttons.update({'propagate': {}})

        utils.update_on_change_with(cls, 'rec_name',
            ['flat_amount', 'rate', 'calculation_kind', 'currency'])

    @classmethod
    def default_start_date(cls):
        if 'start_date' in Transaction().context:
            return Transaction().context.get('start_date')
        return utils.today()

    @classmethod
    def default_end_date(cls):
        if 'end_date' in Transaction().context:
            return Transaction().context.get('end_date')
        return None

    @classmethod
    def default_calculation_kind(cls):
        return 'rate'

    @fields.depends('covered_data')
    def get_possible_extra_premiums_kind(self):
        return list(POSSIBLE_EXTRA_PREMIUM_RULES)

    @classmethod
    def validate(cls, records):
        for record in records:
            if not record.start_date >= record.covered_data.start_date:
                record.raise_user_error('bad_start_date', (record.motive.name,
                        record.start_date, record.covered_data.start_date))

    def calculate_premium_amount(self, args, base):
        if self.calculation_kind == 'flat':
            return self.flat_amount
        elif self.calculation_kind == 'rate':
            return base * self.rate
        return 0

    def get_currency(self):
        return self.covered_data.currency if self.covered_data else None

    @classmethod
    @ModelView.button_action('contract_insurance.act_manage_extra_premium')
    def propagate(cls, extras):
        pass

    def get_rec_name(self, name):
        if self.calculation_kind == 'flat' and self.flat_amount:
            return self.currency.amount_as_string(self.flat_amount)
        elif self.calculation_kind == 'rate' and self.rate:
            return '%s %%' % coop_string.format_number('%.2f',
                self.rate * 100)
        else:
            return super(ExtraPremium, self).get_rec_name(name)

    @fields.depends('calculation_kind', 'flat_amount', 'rate')
    def on_change_with_rec_name(self, name=None):
        return self.get_rec_name(name)

    def get_duration(self, name):
        return coop_date.duration_between(self.start_date, self.end_date,
            'month') if self.start_date and self.end_date else None

    @staticmethod
    def default_duration_unit():
        return 'month'

    def get_duration_unit(self, name):
        return 'month'

    @fields.depends('start_date', 'end_date', 'duration', 'duration_unit')
    def on_change_with_end_date(self):
        if not self.duration or not self.duration_unit:
            return
        return coop_date.add_duration(self.start_date, self.duration,
            self.duration_unit)


class CoveredDataExclusionKindRelation(model.CoopSQL):
    'Covered Data to Exclusion Kind relation'

    __name__ = 'contract.covered_data-exclusion.kind'

    covered_data = fields.Many2One('contract.covered_data', 'Covered Data',
        ondelete='CASCADE')
    exclusion = fields.Many2One('offered.exclusion', 'Exclusion',
        ondelete='RESTRICT')


class ContractAgreementRelation(model.CoopSQL, model.CoopView):
    'Contract-Agreement Relation'

    __name__ = 'contract-agreement'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    party = fields.Many2One('party.party', 'Party', ondelete='RESTRICT')
    protocol = fields.Many2One('contract', 'Protocol', domain=[
            utils.get_versioning_domain('start_date', 'end_date'),
            ('product_kind', '!=', 'insurance'),
            ('subscriber', '=', Eval('party')),
            ], depends=['start_date', 'end_date', 'party'],
        #we only need to have a protocole when the management is effective
        states={'required': ~~Eval('start_date')},
        ondelete='RESTRICT',)
    agency = fields.Many2One('party.address', 'Agency', ondelete='RESTRICT',
        domain=[('party', '=', Eval('party'))], depends=['party'])
    contract = fields.Many2One('contract', 'Contract',
        depends=['party'], ondelete='CASCADE')
    kind = fields.Selection([('', '')], 'Kind')

    @classmethod
    def __setup__(cls):
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection = list(set(cls.get_possible_agreement_kind()))
        super(ContractAgreementRelation, cls).__setup__()

    @classmethod
    def get_possible_agreement_kind(cls):
        return [('', '')]
