import copy

from trytond.modules.coop_utils import model, fields, date
from trytond.pyson import Eval

from trytond.modules.coop_utils import utils
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
    ]


class StatusHistory(model.CoopSQL, model.CoopView):
    'Status History'

    __name__ = 'contract.status_history'

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
        previous_status.end_date = max(date.add_day(at_date, -1),
            previous_status.start_date)
        if previous_status == 'active':
            reference.end_date = previous_status.end_date


class Subscribed(model.CoopView):
    'Subscribed'

    offered = fields.Many2One(
        None, 'Offered', ondelete='RESTRICT',
        states={'required': Eval('status') == 'active'},
        domain=[
            'AND',
            [
                'OR',
                [('end_date', '>=', Eval('start_date'))],
                [('end_date', '=', None)],
            ],
            [
                'OR',
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
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency_id')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    status_history = fields.One2Many(
        'contract.status_history', 'reference', 'Status History')

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

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        res.add(self.start_date)
        if hasattr(self, 'end_date') and self.end_date:
            res.add(self.end_date)
        return utils.limit_dates(res, start, end)

    def init_from_offered(self, offered, start_date=None, end_date=None):
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

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits

    @classmethod
    def get_summary(cls, instances, name):
        return dict((x.id, '') for x in instances)

    def get_currency_id(self, name):
        currency = self.get_currency()
        if currency:
            return currency.id

    def is_active_at_date(self, at_date):
        for status_hist in self.status_history:
            if (status_hist.status == 'active'
                    and utils.is_effective_at_date(status_hist)):
                return True
        return False


class Contract(model.CoopSQL, Subscribed, Printable):
    'Contract'

    __name__ = 'contract.contract'
    _rec_name = 'contract_number'
    _history = True

    kind = fields.Selection('get_possible_contract_kind', 'kind')
    status = fields.Selection(CONTRACTSTATUSES, 'Status')
    options = fields.One2Many(None, 'contract', 'Options')
    contract_number = fields.Char('Contract Number', select=1,
        states={'required': Eval('status') == 'active'})
    subscriber = fields.Many2One('party.party', 'Subscriber')
    current_policy_owner = fields.Function(
        fields.Many2One('party.party', 'Current Policy Owner'),
        'get_current_policy_owner')
    complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Complementary Data',
        on_change=[
            'complementary_data', 'start_date', 'options', 'offered'],
        depends=[
            'complementary_data', 'start_date', 'options', 'offered'],
        # states={'invisible': ~Eval('complementary_data')
        )
    # TODO replace single contact by date versionned list
    contact = fields.Many2One('party.party', 'Contact')
    documents = fields.One2Many(
        'ins_product.document_request', 'needed_by', 'Documents', size=1)

    @classmethod
    def __setup__(cls):
        cls.options = copy.copy(cls.options)
        cls.options.model_name = cls.get_options_model_name()
        super(Contract, cls).__setup__()

    @classmethod
    def get_options_model_name(cls):
        return 'contract.subscribed_option'

    @classmethod
    def get_offered_name(cls):
        #TODO : to replace with generic product
        return 'ins_product.product', 'Product'

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

    def get_complementary_data_value(self, at_date, value):
        return utils.get_complementary_data_value(
            self, 'complementary_data', self.get_complementary_data_def(),
            at_date, value)

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

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        for covered in self.covered_elements:
            res.update(covered.get_dates(start, end))
        for option in self.options:
            res.update(option.get_dates(start, end))
        return super(Contract, self).get_dates(res, start, end)

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['contract'] = self

    def get_product(self):
        return self.offered

    @staticmethod
    def default_status():
        return 'quote'

    def get_new_contract_number(self):
        return self.get_product().get_result('new_contract_number', {})[0]

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
            ('contract_number',) + clause[1:],
            ('subscriber.name',) + clause[1:],
        ])
        return [('id', 'in', [c.id for c in contracts])]

    @classmethod
    def get_summary(cls, insurers, name=None, at_date=None, lang=None):
        return ''

    @staticmethod
    def get_possible_status(name=None):
        return CONTRACTSTATUSES

    def get_policy_owner(self, at_date=None):
        '''
        the owner of a contract could change over time, you should never use
        the direct link subscriber
        '''
        # TODO: to enhance
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
            return self.offered.get_currency()

    def on_change_complementary_data(self):
        return {'complementary_data': self.offered.get_result(
            'calculated_complementary_datas',
            {'date': self.start_date, 'contract': self})[0]}

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
                [('status_history.end_date', '>=', at_date)]]
        ]
        return cls.search(domain)

    def get_current_policy_owner(self, name):
        policy_owner = self.get_policy_owner(utils.today())
        return policy_owner.id if policy_owner else None

    def get_contract_address(self, at_date=None):
        res = utils.get_good_versions_at_date(self, 'addresses', at_date)
        if res:
            return res[0].address

    def get_next_renewal_date(self):
        return utils.add_frequency('yearly', self.start_date)

    @staticmethod
    def get_possible_contract_kind():
        return []


class SubscribedCoverage(model.CoopSQL, Subscribed):
    'Subscribed Coverage'

    __name__ = 'contract.subscribed_option'
    _history = True

    status = fields.Selection(OPTIONSTATUS, 'Status')
    contract = fields.Many2One(None, 'Contract', ondelete='CASCADE')
    contract_number = fields.Function(
        fields.Char('Contract Number'), 'get_contract_number')
    current_policy_owner = fields.Function(
        fields.Many2One('party.party', 'Current Policy Owner'),
        'get_current_policy_owner_id')
    product = fields.Function(
        fields.Many2One('ins_product.product', 'Product'),
        'get_product_id')

    @classmethod
    def __setup__(cls):
        cls.contract = copy.copy(cls.contract)
        cls.contract.model_name = cls.get_contract_model_name()
        super(SubscribedCoverage, cls).__setup__()

    @classmethod
    def get_contract_model_name(cls):
        return 'contract.contract'

    @classmethod
    def get_offered_name(cls):
        #TODO : to replace with generic product
        return 'ins_product.coverage', 'Coverage'

    def get_coverage(self):
        return self.offered

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        res.update(self.offered.get_dates(dates, start, end))
        return super(SubscribedCoverage, self).get_dates(res, start, end)

    @staticmethod
    def get_possible_status(name=None):
        return OPTIONSTATUS

    def get_rec_name(self, name):
        if self.offered:
            return self.offered.get_rec_name(name)
        return super(SubscribedCoverage, self).get_rec_name(name)

    def get_contract(self):
        return self.contract

    def get_currency(self):
        if hasattr(self, 'offered') and self.offered:
            return self.offered.get_currency()

    def get_contract_number(self, name):
        return self.contract.contract_number if self.contract else ''

    def get_current_policy_owner_id(self, name):
        if self.contract:
            return self.contract.get_current_policy_owner(name)

    def get_product_id(self, name):
        return self.contract.offered.id if self.contract else None
