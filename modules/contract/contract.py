import copy

from trytond.modules.coop_utils import model, fields, coop_date
from trytond.transaction import Transaction
from trytond.pyson import Eval, If
from trytond.pool import Pool, PoolMeta

from trytond.modules.coop_utils import utils, coop_string
from trytond.modules.coop_currency import ModelCurrency
from trytond.modules.insurance_product import Printable

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
    'StatusHistory',
    'Contract',
    'SubscribedCoverage',
    'ContractClause',
    'ContractAddress',
    'DeliveredService',
    'LetterModel',
    ]


class StatusHistory(model.CoopSQL, model.CoopView):
    'Status History'

    __name__ = 'contract.status.history'

    reference = fields.Reference('Reference', 'get_possible_reference')
    status = fields.Selection(OPTIONSTATUS, 'Status',
        selection_change_with=['reference'])
    sub_status = fields.Char('Sub Status')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    @classmethod
    def get_possible_reference(cls):
        return []

    def init_from_reference(self, reference, to_status, at_date,
            sub_status=None):
        self.status = to_status
        self.start_date = at_date
        self.sub_status = sub_status
        if not reference.status_history:
            return
        previous_status = reference.status_history[-1]
        if not previous_status:
            return
        previous_status.end_date = max(coop_date.add_day(at_date, -1),
            previous_status.start_date)
        if previous_status == 'active':
            reference.end_date = previous_status.end_date


class Subscribed(model.CoopView, ModelCurrency):
    'Subscribed'

    offered = fields.Many2One(
        None, 'Offered', ondelete='RESTRICT',
        states={'required': Eval('status') == 'active'},
        domain=[['OR',
                [('end_date', '>=', Eval('start_date'))],
                [('end_date', '=', None)],
                ], ['OR',
                [('start_date', '<=', Eval('start_date'))],
                [('start_date', '=', None)],
                ],
            ], depends=['start_date'])
    start_date = fields.Date('Effective Date', required=True)
    end_date = fields.Date(
        'End Date', domain=[('start_date', '<=', 'end_date')])
    # Management date is the date at which the company started to manage the
    # contract. Default value is start_date
    start_management_date = fields.Date('Management Date')
    summary = fields.Function(fields.Text('Summary'), 'get_summary')
    status_history = fields.One2Many(
        'contract.status.history', 'reference', 'Status History')

    @classmethod
    def __setup__(cls):
        cls.offered = copy.copy(cls.offered)
        model_name, cls.offered.string = cls.get_offered_name()
        cls.offered.model_name = model_name
        super(Subscribed, cls).__setup__()

    @staticmethod
    def default_start_date():
        return utils.today()

    @classmethod
    def get_offered_name(cls):
        '''
        returns a tuple of model_name, string for offered class name
        '''
        raise NotImplementedError

    @staticmethod
    def get_possible_status(name=None):
        raise NotImplementedError

    def get_dates(self, dates=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        res.add(self.start_date)
        if hasattr(self, 'end_date') and self.end_date:
            res.add(coop_date.add_day(self.end_date, 1))
        return res

    def init_from_offered(self, offered, start_date=None, end_date=None):
        #TODO : check eligibility
        if not start_date:
            start_date = utils.today()
        if utils.is_effective_at_date(offered, start_date):
            self.offered = offered
            self.start_date = (
                max(offered.start_date, start_date)
                if start_date else offered.start_date)
            self.end_date = (
                min(offered.end_date, end_date)
                if end_date else offered.end_date)
            self.update_status('quote', self.start_date)
            return True, []
        return False, ['offered_not_effective_at_date']

    def get_offered(self):
        return self.offered if hasattr(self, 'offered') else None

    @staticmethod
    def get_status_transition_authorized(from_status):
        res = []
        if from_status == 'quote':
            res = ['active', 'refused']
        elif from_status == 'active':
            res = ['terminated']
        return res

    def update_status(self, to_status, at_date, sub_status=None):
        if (hasattr(self, 'status') and not to_status in
                self.get_status_transition_authorized(self.status)):
            return False, [
                ('transition_unauthorized', (self.status, to_status))]
        if not hasattr(self, 'status_history'):
            self.status_history = []
        else:
            self.status_history = list(self.status_history)
        status_history = utils.instanciate_relation(
            self.__class__, 'status_history')
        status_history.init_from_reference(self, to_status, at_date,
            sub_status)
        self.status_history.append(status_history)
        self.status = to_status
        if hasattr(self, 'sub_status'):
            self.sub_status = sub_status
        return True, []

    @classmethod
    def get_summary(cls, instances, name):
        return dict((x.id, x.rec_name) for x in instances)

    def is_active_at_date(self, at_date):
        for status_hist in self.status_history:
            if (status_hist.status == 'active'
                    and utils.is_effective_at_date(status_hist)):
                return True
        return False

    def get_all_complementary_data(self, at_date):
        if not utils.is_none(self, 'complementary_data'):
            return self.complementary_data
        return {}


class Contract(model.CoopSQL, Subscribed, Printable):
    'Contract'

    __name__ = 'contract'
    _rec_name = 'contract_number'
    _history = True

    product_kind = fields.Function(
        fields.Char('Product Kind', on_change_with=['offered']),
        'on_change_with_product_kind', searcher='search_product_kind')
    status = fields.Selection(CONTRACTSTATUSES, 'Status')
    options = fields.One2Many(None, 'contract', 'Options')
    contract_number = fields.Char('Contract Number', select=1,
        states={'required': Eval('status') == 'active'})
    subscriber_kind = fields.Function(
        fields.Char('Subscriber Kind', on_change_with=['offered'],
            states={'invisible': True}),
        'on_change_with_subscriber_kind')
    subscriber = fields.Many2One('party.party', 'Subscriber',
        domain=[[If(
                    Eval('subscriber_kind') == 'person',
                    ('is_person', '=', True),
                    ())
                ], [
                If(
                    Eval('subscriber_kind') == 'company',
                    ('is_company', '=', True),
                    ())
                ]], depends=['subscriber_kind'], ondelete='RESTRICT')
    current_policy_owner = fields.Function(
        fields.Many2One('party.party', 'Current Policy Owner'),
        'get_current_policy_owner')
    complementary_data = fields.Dict(
        'offered.complementary_data_def', 'Complementary Data',
        on_change=[
            'complementary_data', 'start_date', 'options', 'offered',
            'appliable_conditions_date'],
        depends=[
            'complementary_data', 'start_date', 'options', 'offered'],
        # states={'invisible': ~Eval('complementary_data')
        )
    # TODO replace single contact by date versionned list
    contact = fields.Many2One('party.party', 'Contact')
    appliable_conditions_date = fields.Date('Appliable Conditions Date')
    documents = fields.One2Many(
        'document.request', 'needed_by', 'Documents', size=1)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True)
    addresses = fields.One2Many('contract.address', 'contract',
        'Addresses', context={
            'policy_owner': Eval('current_policy_owner'),
            'start_date': Eval('start_date'),
            }, depends=['current_policy_owner'])
    #temporary field to remove ASAP
    temp_endorsment_date = fields.Date('Endorsment Date')
    clauses = fields.One2Many('contract.clause', 'contract',
        'Clauses', context={'start_date': Eval('start_date')})

    @classmethod
    def __setup__(cls):
        cls.options = copy.copy(cls.options)
        cls.options.model_name = cls.get_options_model_name()
        super(Contract, cls).__setup__()
        cls.offered = copy.copy(cls.offered)
        cls.offered.domain.append(('company', '=', Eval('company')))
        cls.offered.depends.append('company')
        utils.update_on_change(cls, 'start_date', [
                'start_date', 'appliable_conditions_date'])
        utils.update_depends(cls, 'start_date', ['appliable_conditions_date'])

        cls._buttons.update({'option_subscription': {}})

    @classmethod
    @model.CoopView.button_action('contract.option_subscription_wizard')
    def option_subscription(cls, contracts):
        pass

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company', None)

    @classmethod
    def subscribe_contract(cls, offered, party, at_date=None,
            options_code=None):
        'WIP : This method should be the basic API to have a contract.'
        pool = Pool()
        Contract = pool.get('contract')
        SubscribedOpt = pool.get('contract.option')
        contract = Contract()
        contract.subscriber = party
        contract.init_from_offered(offered)
        contract.init_default_address()
        contract.options = []
        for option in offered.coverages:
            if options_code and option.code not in options_code:
                continue
            sub_option = SubscribedOpt()
            sub_option.init_from_offered(option, at_date)
            contract.options.append(sub_option)
        contract.activate_contract()
        contract.finalize_contract()
        return contract

    @classmethod
    def ws_subscribe_contract(cls, contract_dict):
        'This method is a standard API for webservice use'

    def init_clauses(self, offered):
        ClauseRelation = Pool().get('contract.clause')
        clauses, errs = offered.get_result('all_clauses', {
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date,
            })
        if errs or not clauses:
            return
        self.clauses = []
        for clause in clauses:
            new_clause = ClauseRelation()
            new_clause.clause = clause
            new_clause.text = clause.get_good_version_at_date(
                self.start_date).content
            self.clauses.append(new_clause)

    def init_from_offered(self, offered, start_date=None, end_date=None):
        res = super(Contract, self).init_from_offered(offered, start_date,
            end_date)
        self.appliable_conditions_date = self.start_date
        self.init_clauses(offered)
        return res

    @classmethod
    def get_options_model_name(cls):
        return 'contract.option'

    @classmethod
    def get_offered_name(cls):
        return 'offered.product', 'Product'

    def get_active_options_at_date(self, at_date):
        res = []
        for elem in self.options:
            #TODO : to be replaced with utils.is_effective_at_date
            if (elem.start_date and elem.start_date <= at_date
                and (not hasattr(elem, 'end_date') or (
                    elem.end_date is None or elem.end_date > at_date))):
                res += [elem]
        return list(set(res))

    def get_option_for_coverage_at_date(self, coverage, date):
        for elem in self.get_active_options_at_date(date):
            if elem.get_coverage() == coverage:
                return elem
        return None

    def get_active_coverages_at_date(self, at_date):
        return [
            elem.get_coverage()
            for elem in self.get_active_options_at_date(at_date)]

    def init_complementary_data(self):
        if not (hasattr(self, 'complementary_data') and
                self.complementary_data):
            self.complementary_data = {}
        self.complementary_data = self.on_change_complementary_data()[
            'complementary_data']
        return True, ()

    def get_complementary_data_def(self):
        compl_data_defs = []
        if self.offered:
            compl_data_defs.extend(self.offered.get_complementary_data_def(
                ['contract'], at_date=self.start_date))
        for option in self.options:
            compl_data_defs.extend(
                option.offered.get_complementary_data_def(
                    ['contract'], at_date=option.start_date))
        return set(compl_data_defs)

    def get_dates(self, dates=None):
        res = super(Contract, self).get_dates(dates)
        for covered in self.covered_elements:
            res.update(covered.get_dates(res))
        for option in self.options:
            res.update(option.get_dates(res))
        return res

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['contract'] = self
        cur_dict['appliable_conditions_date'] = self.appliable_conditions_date
        self.offered.init_dict_for_rule_engine(cur_dict)
        cur_dict['subscriber'] = self.get_policy_owner()

    def get_product(self):
        return self.offered

    def on_change_start_date(self):
        return {'appliable_conditions_date': self.start_date}

    @staticmethod
    def default_status():
        return 'quote'

    def get_new_contract_number(self):
        return self.get_product().get_result(
            'new_contract_number', {
                'appliable_conditions_date': self.appliable_conditions_date,
                'date': self.start_date,
                })[0]

    def finalize_contract(self):
        self.contract_number = self.get_new_contract_number()
        return True, ()

    def get_rec_name(self, val):
        if self.offered and self.get_policy_owner():
            if self.contract_number:
                return '%s (%s) - %s' % (
                    self.contract_number, self.get_product().get_rec_name(val),
                    self.get_policy_owner().get_rec_name(val))
            else:
                return 'Contract %s - %s' % (
                    self.get_product().get_rec_name(val),
                    self.get_policy_owner().get_rec_name(val))
        else:
            return super(Contract, self).get_rec_name(val)

    @classmethod
    def search_rec_name(cls, name, clause):
        contracts = cls.search([
            'OR',
            ('contract_number',) + tuple(clause[1:]),
            ('subscriber.name',) + tuple(clause[1:]),
        ])
        return [('id', 'in', [c.id for c in contracts])]

    @classmethod
    def get_summary(cls, instances, name, at_date=None, lang=None):
        return dict((x.id, x.contract_number) for x in instances)

    @staticmethod
    def get_possible_status(name=None):
        return CONTRACTSTATUSES

    def get_policy_owner(self, at_date=None):
        '''
        the owner of a contract could change over time, you should never use
        the direct link subscriber
        '''
        # TODO: to enhance
        if not utils.is_none(self, 'subscriber'):
            return self.subscriber

    def activate_contract(self):
        if not self.status == 'quote':
            return True, ()
        for option in self.options:
            if option.status == 'quote':
                option.update_status('active', self.start_date)
                option.save()
        self.update_status('active', self.start_date)
        return True, ()

    def init_options(self):
        existing = {}
        if not utils.is_none(self, 'options'):
            for opt in self.options:
                existing[opt.offered.code] = opt
        good_options = []
        to_delete = [elem for elem in existing.itervalues()]
        OptionModel = utils.get_relation_model(self, 'options')
        for coverage in self.offered.coverages:
            if coverage.code in existing:
                good_opt = existing[coverage.code]
                to_delete.remove(good_opt)
            else:
                good_opt = OptionModel()
                good_opt.init_from_offered(coverage, self.start_date)
                good_opt.contract = self
            good_opt.save()
            good_options.append(good_opt)
        if to_delete:
            OptionModel.delete(to_delete)
        self.options = good_options

        return True, ()

    def get_main_contact(self):
        return self.get_policy_owner()

    def get_contact(self):
        return self.get_policy_owner()

    def get_sender(self):
        raise NotImplementedError

    def get_currency(self):
        if hasattr(self, 'offered') and self.offered:
            return self.offered.currency

    def on_change_complementary_data(self):
        args = {'date': self.start_date, 'level': 'contract'}
        self.init_dict_for_rule_engine(args)
        return {'complementary_data': self.offered.get_result(
                'calculated_complementary_datas', args)[0]}

    @classmethod
    def get_possible_contracts_from_party(cls, party, at_date):
        if not party:
            return []
        domain = [
            ('subscriber', '=', party.id),
            ('status_history.status', '=', 'active'),
            ('status_history.start_date', '<=', at_date),
            ['OR',
                [('status_history.end_date', '=', None)],
                [('status_history.end_date', '>=', at_date)]],
            ]
        if 'company' in Transaction().context:
            domain.append(('company', '=', Transaction().context['company']))
        return cls.search(domain)

    def get_current_policy_owner(self, name):
        policy_owner = self.get_policy_owner(utils.today())
        return policy_owner.id if policy_owner else None

    def get_contract_address(self, at_date=None):
        res = utils.get_good_versions_at_date(self, 'addresses', at_date)
        if res:
            return res[0].address

    def get_next_renewal_date(self):
        return coop_date.add_frequency('yearly', self.start_date)

    def on_change_with_product_kind(self, name=None):
        return self.offered.kind if self.offered else ''

    @classmethod
    def search_product_kind(cls, name, clause):
        return [('offered.kind', ) + tuple(clause[1:])]

    def init_default_address(self):
        if not utils.is_none(self, 'addresses'):
            return True
        addresses = self.subscriber.address_get(
            at_date=self.start_date)
        if addresses:
            cur_address = utils.instanciate_relation(self, 'addresses')
            cur_address.address = addresses
            cur_address.start_date = self.start_date
            self.addresses = [cur_address]
        return True

    def get_letter_model_kind(self):
        return 'contract'

    def on_change_with_subscriber_kind(self, name=None):
        return self.offered.subscriber_kind if self.offered else 'all'

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['subscriber', ('offered', 'light'), 'complementary_data',
            'options', 'covered_elements', 'start_date', 'end_date']


class SubscribedCoverage(model.CoopSQL, Subscribed):
    'Subscribed Coverage'

    __name__ = 'contract.option'
    _history = True

    status = fields.Selection(OPTIONSTATUS, 'Status')
    contract = fields.Many2One('contract', 'Contract',
        ondelete='CASCADE')
    coverage_kind = fields.Function(
        fields.Char('Coverage Kind', on_change_with=['offered']),
        'on_change_with_coverage_kind', searcher='search_coverage_kind')
    contract_number = fields.Function(
        fields.Char('Contract Number'), 'get_contract_number')
    current_policy_owner = fields.Function(
        fields.Many2One('party.party', 'Current Policy Owner'),
        'get_current_policy_owner_id')
    product = fields.Function(
        fields.Many2One('offered.product', 'Product'),
        'get_product_id')

    @classmethod
    def get_offered_name(cls):
        return 'offered.coverage', 'Coverage'

    def get_coverage(self):
        return self.offered

    def get_dates(self, dates=None):
        res = super(SubscribedCoverage, self).get_dates(dates)
        res.update(self.offered.get_dates(res))
        return res

    @staticmethod
    def get_possible_status(name=None):
        return OPTIONSTATUS

    def get_rec_name(self, name):
        if self.offered:
            return self.offered.get_rec_name(name)
        return super(SubscribedCoverage, self).get_rec_name(name)

    def get_currency(self):
        if hasattr(self, 'offered') and self.offered:
            return self.offered.currency

    def get_contract_number(self, name):
        return self.contract.contract_number if self.contract else ''

    def get_current_policy_owner_id(self, name):
        if self.contract:
            return self.contract.get_current_policy_owner(name)

    def get_product_id(self, name):
        return self.contract.offered.id if self.contract else None

    def on_change_with_coverage_kind(self, name=None):
        return self.offered.kind if self.offered else ''

    @classmethod
    def search_coverage_kind(cls, name, clause):
        return [('offered.kind', ) + tuple(clause[1:])]

    def get_all_complementary_data(self, at_date):
        res = super(SubscribedCoverage, self).get_all_complementary_data(
            at_date)
        res.update(self.contract.get_all_complementary_data(at_date))
        return res

    def init_dict_for_rule_engine(self, args):
        args['option'] = self
        self.offered.init_dict_for_rule_engine(args)
        self.contract.init_dict_for_rule_engine(args)

    @classmethod
    def get_var_names_for_full_extract(cls):
        return [('offered', 'light'), 'start_date', 'end_date']


class ContractClause(model.CoopSQL, model.CoopView):
    'Contract clauses'

    __name__ = 'contract.clause'

    contract = fields.Many2One('contract', 'Contract',
        ondelete='CASCADE')
    clause = fields.Many2One('ins_product.clause', 'Clause',
        ondelete='RESTRICT')
    override_text = fields.Function(
        fields.Boolean('Override Text', on_change_with=['clause'],
            states={'invisible': True}),
        'on_change_with_override_text')
    text = fields.Text('Text', states={
            'readonly': ~Eval('override_text'),
            'invisible': True,
        })
    visual_text = fields.Function(
        fields.Text('Clause Text', on_change_with=[
                'text', 'clause', 'override_text', 'contract']),
        'on_change_with_visual_text')
    kind = fields.Function(
        fields.Char('Kind', on_change_with=['clause', 'contract']),
        'on_change_with_kind')

    def on_change_with_override_text(self, name=None):
        if not self.clause:
            return False
        return self.clause.may_be_overriden

    def on_change_with_visual_text(self, name=None):
        if not self.clause:
            return ''
        if self.override_text:
            return self.text
        return self.clause.get_version_at_date(
            self.contract.appliable_conditions_date).content

    def on_change_with_kind(self, name=None):
        if not self.clause:
            return ''
        return self.clause.kind


class ContractAddress(model.CoopSQL, model.CoopView):
    'Contract Address'

    __name__ = 'contract.address'

    contract = fields.Many2One('contract', 'Contract',
        ondelete='CASCADE')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('policy_owner'))],
        depends=['policy_owner'])
    policy_owner = fields.Function(
        fields.Many2One('party.party', 'Policy Owner',
            states={'invisible': True}),
        'get_policy_owner')

    @staticmethod
    def default_policy_owner():
        return Transaction().context.get('policy_owner')

    def get_policy_owner(self, name):
        if self.contract and self.start_date:
            res = self.contract.get_policy_owner(self.start_date)
        else:
            res = self.default_policy_owner()
        if res:
            return res.id

    @staticmethod
    def default_start_date():
        return Transaction().context.get('start_date')


class DeliveredService(model.CoopView, model.CoopSQL):
    'Delivered Service'

    __name__ = 'contract.service'

    status = fields.Selection([
            ('calculating', 'Calculating'),
            ('not_eligible', 'Not Eligible'),
            ('calculated', 'Calculated'),
            ('delivered', 'Delivered'),
            ], 'Status')
    contract = fields.Many2One('contract', 'Contract',
        ondelete='RESTRICT')
    subscribed_service = fields.Many2One(
        'contract.option', 'Coverage', ondelete='RESTRICT',
        domain=[
            If(~~Eval('contract'), ('contract', '=', Eval('contract', {})), ())
        ], depends=['contract'])
    func_error = fields.Many2One('rule_engine.error', 'Error',
        ondelete='RESTRICT', states={
            'invisible': ~Eval('func_error'),
            'readonly': True})

    def get_rec_name(self, name=None):
        if self.subscribed_service:
            res = self.subscribed_service.get_rec_name(name)
        else:
            res = super(DeliveredService, self).get_rec_name(name)
        if self.status:
            res += ' [%s]' % coop_string.translate_value(self, 'status')
        return res

    @staticmethod
    def default_status():
        return 'calculating'

    def get_contract(self):
        return self.contract


class LetterModel():
    'Letter Model'

    __metaclass__ = PoolMeta
    __name__ = 'document.template'

    @classmethod
    def __setup__(cls):
        super(LetterModel, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('contract', 'Contract Documents'))
        cls.kind.selection = list(set(cls.kind.selection))
