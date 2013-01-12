from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

from trytond.modules.coop_utils import utils
from trytond.transaction import Transaction

from trytond.modules.process import ClassAttr
from trytond.modules.coop_party import ACTOR_KIND

OPTION_SELECTION_STATUS = [
    ('active', 'Active'),
    ('refused', 'Refused'),
]

__all__ = [
    'Contract',
    'Option',
    'CoveredData',
    'CoveredElement',
]


class Contract():
    'Contract'

    __name__ = 'ins_contract.contract'
    __metaclass__ = ClassAttr

    subscriber_kind = fields.Function(
        fields.Selection(ACTOR_KIND, 'Kind',
            on_change=['subscriber_as_person', 'subscriber_as_society', ],
        ), 'get_subscriber_kind', 'setter_void', )
    subscriber_as_person = fields.Function(
        fields.Many2One('party.person', 'Subscriber',
            states={
                'invisible': Eval('subscriber_kind') != 'party.person',
            },
            on_change=['subscriber', 'subscriber_as_person', ],
        ), 'get_subscriber_as_person', 'setter_void', )
    subscriber_as_society = fields.Function(
        fields.Many2One('party.society', 'Subscriber',
            states={
                'invisible': Eval('subscriber_kind') != 'party.society',
            },
            on_change=['subscriber', 'subscriber_as_society'],
        ), 'get_subscriber_as_society', 'setter_void', )
    subscriber_desc = fields.Function(
        fields.Text('Summary',
            on_change_with=['subscriber_as_person', 'subscriber_as_society',
                'subscriber', ],
        ), 'on_change_with_subscriber_desc', 'setter_void', )
    product_desc = fields.Function(
        fields.Text('Description', on_change_with=['offered', ],
        ), 'on_change_with_product_desc', 'setter_void', )

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._error_messages.update({
            'no_product': 'A product must be provided',
            'no_subscriber': 'A subscriber must be provided',
            'no start_date': 'A start date must be provided',
            'bad_date': '%s is not a valid start date for product %s',
            'option_not_eligible': 'Option %s is not eligible',
            'no_option': 'At least an option must be selected',
            'bad_start_date': 'Option %s must be subscribed after %s',
            'need_option': 'At least one option must be selected for %s',
            'need_covered': 'There must be at least one covered element',
        })

    def on_change_with_subscriber_desc(self, name=None):
        res = ''
        if self.subscriber:
            res = self.subscriber.summary
        return res

    def on_change_with_product_desc(self, name=None):
        res = ''
        if self.offered:
            res = self.offered.description
        return res

    def on_change_subscriber_kind(self):
        res = {}
        if not (hasattr(self, 'subscriber_kind') and self.subscriber_kind):
            return res
        if self.subscriber_kind == 'party.person':
            res['subscriber_as_society'] = None
        elif self.subscriber_kind == 'party.society':
            res['subscriber_as_person'] = None
        return res

    def get_subscriber_kind(self, name):
        if (hasattr(self, 'subscriber_as_society') and
                self.subscriber_as_society):
            return 'party.society'
        return 'party.person'

    def get_subscriber_as_person(self, name):
        if not self.subscriber:
            return
        if self.subscriber.person:
            res = self.subscriber.person[0]
            return res.id

    def get_subscriber_as_society(self, name):
        if not self.subscriber:
            return
        if self.subscriber.society:
            return self.subscriber.society[0].id

    def on_change_subscriber_as_person(self):
        if (hasattr(self, 'subscriber_as_person') and
                self.subscriber_as_person):
            return {'subscriber': self.subscriber_as_person.party.id}
        return {}

    def on_change_subscriber_as_society(self):
        if (hasattr(self, 'subscriber_as_society') and
                self.subscriber_as_society):
            return {'subscriber': self.subscriber_as_society.party.id}
        return {}

    @classmethod
    def default_subscriber_kind(cls):
        return 'party.person'

    @classmethod
    def setter_void(cls, contracts, name, values):
        pass

    def check_product_not_null(self):
        print '*' * 80
        if not (hasattr(self, 'offered') and self.offered):
            return False, (('no_product', ()),)
        return True, ()

    def check_subscriber_not_null(self):
        if not (hasattr(self, 'subscriber') and self.subscriber):
            return False, (('no_subscriber', ()),)
        return True, ()

    def check_start_date_valid(self):
        if not (hasattr(self, 'start_date') and self.start_date):
            return False, (('no_start_date', ()),)
        if self.start_date >= self.offered.start_date and (
                not self.offered.end_date
                or self.start_date < self.offered.end_date):
            return True, ()

        return False, (('bad_date', (
            self.start_date, self.offered.get_rec_name(None))),)

    def check_product_eligibility(self):
        eligibility, errors = self.offered.get_result(
            'eligibility',
            {
                'subscriber': self.subscriber,
                'date': self.start_date
            })
        print '*' * 80
        
        if eligibility:
            return eligibility.eligible, eligibility.details + errors
        return True, ()

        return eligibility.eligible, errors

    def init_dynamic_data(self):
        if (not (hasattr(self, 'complementary_data')
            and self.complementary_data)):
            self.complementary_data = {}

        utils.set_default_dict(
            self.complementary_data,
            utils.init_dynamic_data(
                self.offered.get_result(
                    'complementary_data_getter',
                    {
                        'date': self.start_date,
                        'dd_args': {
                            'kind': 'main'}})[0]))
        return True, ()

    def init_options(self):
        existing = {}
        if (hasattr(self, 'options') and self.options):
            for opt in self.options:
                existing[opt.offered.code] = opt

        good_options = []
        to_delete = [elem for elem in existing.itervalues()]

        OptionModel = Pool().get(self.give_option_model())
        for coverage in self.offered.options:
            if coverage.code in existing:
                good_opt = existing[coverage.code]
                to_delete.remove(good_opt)
            else:
                good_opt = OptionModel()
                good_opt.init_from_coverage(coverage)
                good_opt.contract = self

            good_opt.start_date = max(
                good_opt.start_date,
                self.start_date)

            good_opt.save()

            good_options.append(good_opt)

        if to_delete:
            OptionModel.delete(to_delete)

        self.options = good_options

        return True, ()

    def check_options_eligibility(self):
        errs = []
        eligible = True

        for option in self.options:
            if option.status != 'active':
                continue

            eligibility, errors = option.offered.get_result(
                'eligibility',
                {
                    'date': self.start_date,
                    'subscriber': self.subscriber,
                })

            if not eligibility.eligible:
                errs.append(('option_not_eligible', (option.offered.code)))
                errs += (
                    ('%s' % elem, ())
                    for elem in eligibility.details + errors)
                eligible = False

        return eligible, errs

    def check_option_selected(self):
        for option in self.options:
            if option.status == 'active':
                return True, ()

        return False, (('no_option', ()),)

    def check_option_dates(self):
        result = True
        errs = []

        for option in self.options:
            if option.start_date < self.start_date:
                result = False
                errs.append((
                    'bad_start_date', (
                        option.offered.code,
                        self.start_date)))
            elif option.start_date < option.offered.start_date:
                result = False
                errs.append((
                    'bad_start_date', (
                        option.offered.code,
                        option.offered.start_date)))

        return result, errs

    def init_billing_manager(self):
        if not (hasattr(self, 'billing_manager') and
                self.billing_manager):
            BillingManager = Pool().get(self.get_manager_model())
            bm = BillingManager()
            self.billing_manager = [bm]

        return True, ()

    def calculate_prices(self):
        prices, errs = self.calculate_prices_at_all_dates()

        if errs:
            return False, errs

        #print len(prices[0].details)
        self.billing_manager[0].store_prices(prices)
        self.billing_manager[0].save()

        return True, ()

    def activate_contract(self):
        if not self.status == 'quote':
            return True, ()

        self.status = 'active'

        return True, ()


class Option():
    'Option'

    __metaclass__ = PoolMeta

    __name__ = 'ins_contract.option'

    status_selection = fields.Function(
        fields.Selection(
            OPTION_SELECTION_STATUS,
            'Status',
            on_change=['status_selection', 'status'],
        ),
        'get_status_selection',
        'setter_void',
    )

    def on_change_status_selection(self):
        if self.status_selection == 'active':
            return {'status': 'active'}
        else:
            return {'status': 'refused'}

    def get_status_selection(self, name):
        if self.status == 'active':
            return 'active'
        return 'refused'

    @classmethod
    def default_status_selection(cls):
        return 'active'

    @classmethod
    def setter_void(cls, contracts, name, values):
        pass


class CoveredElement():
    'Covered Element'

    __metaclass__ = PoolMeta

    __name__ = 'ins_contract.covered_element'

    @classmethod
    def default_covered_data(cls):
        contract = Transaction().context.get('current_contract')

        if not contract:
            return []

        Contract = Pool().get('ins_contract.contract')
        contract = Contract(contract)

        CoveredData = Pool().get(
            cls._fields['covered_data'].model_name)

        covered_datas = []
        for option in contract.options:
            good_data = CoveredData()
            good_data.init_from_coverage(option.offered)
            good_data.start_date = max(
                good_data.start_date, contract.start_date)
            good_data.init_dynamic_data(option.offered, contract)
            good_data.status_selection = True
            covered_datas.append(good_data)
        return utils.WithAbstract.serialize_field(covered_datas)


class CoveredData():
    'Coverage Data'

    __metaclass__ = PoolMeta

    __name__ = 'ins_contract.covered_data'

    status_selection = fields.Function(
        fields.Boolean(
            'Status',
            on_change=['status_selection', 'status'],
        ),
        'get_status_selection',
        'setter_void',
    )

    def on_change_status_selection(self):
        if self.status_selection:
            return {'status': 'active'}
        else:
            return {'status': 'refused'}

    def get_status_selection(self, name):
        if self.status == 'active':
            return True
        return False

    @classmethod
    def default_status_selection(cls):
        return True
    
    @classmethod
    def setter_void(cls, contracts, name, values):
        pass

