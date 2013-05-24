import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coop_utils import abstract, model, fields

from trytond.modules.process import ClassAttr
from trytond.modules.coop_process import CoopProcessFramework
from trytond.modules.coop_process import ProcessFinder, ProcessParameters
from trytond.modules.coop_party.party import ACTOR_KIND

OPTION_SELECTION_STATUS = [
    ('active', 'Active'),
    ('refused', 'Refused'),
]

__all__ = [
    'ContractSubscription',
    'Option',
    'CoveredData',
    'CoveredElement',
    'SubscriptionManager',
    'ProcessDesc',
    'SubscriptionProcessParameters',
    'SubscriptionProcessFinder',
]


class ContractSubscription(CoopProcessFramework):
    'Contract'

    __name__ = 'ins_contract.contract'
    __metaclass__ = ClassAttr

    subscriber_kind = fields.Function(
        fields.Selection(ACTOR_KIND, 'Kind', on_change=[
            'subscriber_as_person', 'subscriber_as_company', ],
        ), 'get_subscriber_kind', 'setter_void', )
    subscriber_as_person = fields.Function(
        fields.Many2One(
            'party.party', 'Subscriber',
            states={
                'invisible': Eval('subscriber_kind') != 'person',
            },
            on_change=['subscriber', 'subscriber_as_person', ],
            domain=[('is_person', '=', True)],
        ), 'get_subscriber_as_person', 'setter_void', )
    subscriber_as_company = fields.Function(
        fields.Many2One(
            'party.party', 'Subscriber',
            states={
                'invisible': Eval('subscriber_kind') != 'company',
            }, domain=[('is_company', '=', True)],
            on_change=['subscriber', 'subscriber_as_company'],
        ), 'get_subscriber_as_company', 'setter_void', )
    subscriber_desc = fields.Function(
        fields.Text('Summary', on_change_with=[
            'subscriber_as_person', 'subscriber_as_company', 'subscriber', ],
        ), 'on_change_with_subscriber_desc', 'setter_void', )
    product_desc = fields.Function(
        fields.Text(
            'Description', on_change_with=['offered', ],
        ),
        'on_change_with_product_desc', 'setter_void', )
    subscription_mgr = fields.One2Many(
        'ins_contract.subscription_mgr', 'contract', 'Subscription Manager')
    doc_received = fields.Function(
        fields.Boolean(
            'All Document Received',
            depends=['documents'],
            on_change_with=['documents']),
        'on_change_with_doc_received')

    @classmethod
    def __setup__(cls):
        super(ContractSubscription, cls).__setup__()
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
        if self.get_product():
            res = self.get_product().description
        return res

    def on_change_subscriber_kind(self):
        res = {}
        if not (hasattr(self, 'subscriber_kind') and self.subscriber_kind):
            return res
        if self.subscriber_kind == 'person':
            res['subscriber_as_company'] = None
        elif self.subscriber_kind == 'company':
            res['subscriber_as_person'] = None
        return res

    def get_subscriber_kind(self, name):
        if (hasattr(self, 'subscriber_as_company') and
                self.subscriber_as_company):
            return 'company'
        return 'person'

    def get_subscriber_as_person(self, name):
        if not self.subscriber:
            return
        if self.subscriber.is_person:
            return self.subscriber.id

    def get_subscriber_as_company(self, name):
        if not self.subscriber:
            return
        if self.subscriber.is_company:
            return self.subscriber

    def on_change_subscriber_as_person(self):
        if (hasattr(self, 'subscriber_as_person') and
                self.subscriber_as_person):
            return {'subscriber': self.subscriber_as_person.id}
        return {}

    def on_change_subscriber_as_company(self):
        if (hasattr(self, 'subscriber_as_company') and
                self.subscriber_as_company):
            return {'subscriber': self.subscriber_as_company.id}
        return {}

    def on_change_with_doc_received(self, name=None):
        if not (hasattr(self, 'documents') and self.documents):
            return False

        for doc in self.documents:
            if not doc.is_complete:
                return False

        return True

    @classmethod
    def default_subscriber_kind(cls):
        return 'person'

    @classmethod
    def setter_void(cls, contracts, name, values):
        pass

    def check_product_not_null(self):
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
        eligibility, errors = self.get_product().get_result(
            'eligibility',
            {
                'subscriber': self.subscriber,
                'date': self.start_date
            })
        if eligibility:
            return eligibility.eligible, eligibility.details + errors
        return True, ()

        return eligibility.eligible, errors

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

            if eligibility and not eligibility.eligible:
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

    def calculate_prices(self):
        prices, errs = self.calculate_prices_at_all_dates()

        if errs:
            return False, errs
        self.billing_manager[0].store_prices(prices)
        self.billing_manager[0].save()

        return True, ()

    def finalize_contract(self):
        res = super(ContractSubscription, self).finalize_contract()
        return res
        # Model = utils.get_relation_model(self.__class__, 'subscription_mgr')
        # Model.delete([self.subscription_mgr])
        # return res

    def init_subscription_document_request(self):
        DocRequest = Pool().get('ins_product.document_request')

        if not (hasattr(self, 'documents') and self.documents):
            good_req = DocRequest()
            good_req.needed_by = self
            good_req.save()
        else:
            good_req = self.documents[0]

        documents = []
        product_docs, errs = self.get_product().get_result(
            'documents', {
                'contract': self,
                'date': self.start_date})

        if errs:
            return False, errs

        if product_docs:
            documents.extend([(doc_desc, self) for doc_desc in product_docs])

        for option in self.options:
            if not option.status == 'active':
                continue
            option_docs, errs = self.get_product().get_result(
                'documents', {
                    'contract': self,
                    'option': option.get_coverage().code,
                    'date': self.start_date})

            if errs:
                return False, errs

            if not option_docs:
                continue

            documents.extend([(doc_desc, self) for doc_desc in option_docs])

        for elem in self.covered_elements:
            for data in elem.covered_data:
                if not data.status == 'active':
                    continue
                sub_docs, errs = self.get_product().get_result(
                    'documents', {
                        'contract': self,
                        'option': data.option.get_coverage().code,
                        'date': self.start_date,
                        'kind': 'sub',
                        'sub_elem': elem})
                if errs:
                    return False, errs
                if not sub_docs:
                    continue

                documents.extend([(doc_desc, elem) for doc_desc in sub_docs])

        good_req.add_documents(self.start_date, documents)

        good_req.clean_extras(documents)

        return True, ()

    def init_management_roles(self):
        ManagementRole = Pool().get('ins_contract.management_role')
        ManagementProtocol = Pool().get('ins_contract.management_protocol')
        product = self.offered
        self.management = []
        # Set Contract Management Role
        if product.tmp_contract_manager:
            good_protocol = ManagementProtocol.search([
                ('kind', '=', 'contract_manager'),
                ('party', '=', product.tmp_contract_manager.id),
                ('start_date', '<=', self.start_date)])
            if not good_protocol:
                good_protocol = ManagementProtocol()
                good_protocol.start_date = self.start_date
                good_protocol.kind = 'contract_manager'
                good_protocol.party = product.tmp_contract_manager
                good_protocol.save()
            else:
                good_protocol = good_protocol[0]
            good_role = ManagementRole()
            good_role.protocol = good_protocol
            good_role.start_date = self.start_date
            good_role.contract = self
            good_role.save()
            self.management.append(good_role)
        # Set Claim Management Role
        if product.tmp_claim_manager:
            good_protocol = ManagementProtocol.search([
                ('kind', '=', 'claim_manager'),
                ('party', '=', product.tmp_claim_manager.id),
                ('start_date', '<=', self.start_date)])
            if not good_protocol:
                good_protocol = ManagementProtocol()
                good_protocol.start_date = self.start_date
                good_protocol.kind = 'claim_manager'
                good_protocol.party = product.tmp_claim_manager
                good_protocol.save()
            else:
                good_protocol = good_protocol[0]
            good_role = ManagementRole()
            good_role.protocol = good_protocol
            good_role.start_date = self.start_date
            good_role.contract = self
            good_role.save()
            self.management.append(good_role)
        return True


class Option():
    'Option'

    __metaclass__ = PoolMeta

    __name__ = 'ins_contract.option'

    status_selection = fields.Function(
        fields.Boolean('Status',
            on_change=['status_selection', 'status']),
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


class CoveredElement():
    'Covered Element'

    __name__ = 'ins_contract.covered_element'
    __metaclass__ = PoolMeta

    @classmethod
    def default_covered_data(cls):
        if '_master_covered' in Transaction().context:
            return super(CoveredElement, cls).default_covered_data()
        contract = Transaction().context.get('current_contract')

        if not contract:
            return []

        Contract = Pool().get('ins_contract.contract')
        contract = Contract(contract)

        CoveredData = Pool().get('ins_contract.covered_data')

        covered_datas = []
        for option in contract.options:
            good_data = CoveredData()
            good_data.init_from_option(option)
            # good_data.start_date = max(
                # good_data.start_date, contract.start_date)
            # good_data.init_complementary_data(option.offered, contract)
            good_data.status_selection = True
            covered_datas.append(good_data)
        return abstract.WithAbstract.serialize_field(covered_datas)


class CoveredData():
    'Coverage Data'

    __name__ = 'ins_contract.covered_data'
    __metaclass__ = PoolMeta

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


class SubscriptionManager(model.CoopSQL):
    'Subscription Manager'
    '''Temporary object used during the subscription, it is dropped as soon
    as the contract is activated'''

    __name__ = 'ins_contract.subscription_mgr'

    contract = fields.Reference(
        'Contract',
        [
            ('ins_contract.contract', 'Contract'),
            ('ins_collective.contract', 'Contract')],
    )
    is_custom = fields.Boolean('Custom')


class ProcessDesc():
    'Process Desc'

    __metaclass__ = PoolMeta

    __name__ = 'process.process_desc'

    @classmethod
    def __setup__(cls):
        super(ProcessDesc, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('subscription', 'Contract Subscription'))


class SubscriptionProcessParameters(ProcessParameters):
    'Subscription Process Parameters'

    __name__ = 'ins_contract.subscription_process_parameters'

    product = fields.Many2One(
        'ins_product.product',
        'Product',
        domain=['AND',
            ['OR',
                [('end_date', '>=', Eval('date'))],
                [('end_date', '=', None)],
            ],
            ['OR',
                [('start_date', '<=', Eval('date'))],
                [('start_date', '=', None)],
            ],
        ], depends=['date']
    )

    @classmethod
    def build_process_domain(cls):
        result = super(
            SubscriptionProcessParameters, cls).build_process_domain()
        result.append(('for_products', '=', Eval('product')))
        result.append(('kind', '=', 'subscription'))
        return result

    @classmethod
    def build_process_depends(cls):
        result = super(
            SubscriptionProcessParameters, cls).build_process_depends()
        result.append('product')
        return result

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'ins_contract.contract')])[0].id


class SubscriptionProcessFinder(ProcessFinder):
    'Subscription Process Finder'

    __name__ = 'ins_contract.subscription_process_finder'

    @classmethod
    def get_parameters_model(cls):
        return 'ins_contract.subscription_process_parameters'

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'insurance_contract_subscription',
            'subscription_process_parameters_form')

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(SubscriptionProcessFinder,
            self).init_main_object_from_process(obj, process_param)
        if res:
            res, err = obj.init_from_offered(process_param.product,
                process_param.date)
            errs += err
        return res, errs
