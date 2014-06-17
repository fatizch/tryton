from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.modules.cog_utils import fields

from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CogProcessFramework

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    ]


class Contract(CogProcessFramework):
    __name__ = 'contract'
    __metaclass__ = ClassAttr

    doc_received = fields.Function(
        fields.Boolean('All Document Received', depends=['documents']),
        'on_change_with_doc_received')
    product_desc = fields.Function(
        fields.Text('Description', readonly=True),
        'on_change_with_product_desc', 'setter_void', )
    subscriber_desc = fields.Function(
        fields.Text('Summary', readonly=True),
        'on_change_with_subscriber_desc', 'setter_void', )

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
                'payment_bank_account_required': 'The payment bank account is '
                    'required as the payment mode is Direct Debit'
                })
        cls.__rpc__.update({'get_allowed_payment_methods': RPC(instantiate=0)})

    @fields.depends('documents')
    def on_change_with_doc_received(self, name=None):
        if not self.documents:
            return False
        for doc in self.documents:
            if not doc.is_complete:
                return False
        return True

    @fields.depends('com_product')
    def on_change_with_product_desc(self, name=None):
        return self.com_product.description if self.com_product else ''

    @fields.depends('subscriber')
    def on_change_with_subscriber_desc(self, name=None):
        return self.subscriber.summary if self.subscriber else ''

    def on_change_subscriber_kind(self):
        res = super(Contract, self).on_change_subscriber_kind()
        res['subscriber_desc'] = ''
        return res

    def check_product_not_null(self):
        if not self.product:
            return False, (('no_product', ()),)
        return True, ()

    def check_subscriber_not_null(self):
        if not self.subscriber:
            return False, (('no_subscriber', ()),)
        return True, ()

    def check_start_date_valid(self):
        if not self.start_date:
            return False, (('no_start_date', ()),)
        if self.start_date >= self.product.start_date and (
                not self.product.end_date
                or self.start_date < self.product.end_date):
            return True, ()
        return False, (('bad_date', (
            self.start_date, self.product.get_rec_name(None))),)

    def check_product_eligibility(self):
        eligibility, errors = self.product.get_result('eligibility',
            {
                'subscriber': self.subscriber,
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date,
            })
        if eligibility:
            return eligibility.eligible, eligibility.details + errors
        return True, ()

    def check_options_eligibility(self):
        errs = []
        eligible = True
        for option in self.options:
            if option.status != 'active':
                continue
            eligibility, errors = option.coverage.get_result(
                'eligibility',
                {
                    'date': self.start_date,
                    'subscriber': self.subscriber,
                    'appliable_conditions_date':
                    self.appliable_conditions_date,
                })
            if eligibility and not eligibility.eligible:
                errs.append(('option_not_eligible', (option.coverage.code)))
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

    def check_billing_data(self):
        # TODO : Move to billing_individual
        result = True
        errs = []
        for manager in self.billing_datas:
            if not manager.payment_mode == 'direct_debit':
                continue
            if not manager.payment_bank_account:
                result = False
                errs.append(('payment_bank_account_required', ()))
        return result, errs

    def check_option_dates(self):
        result = True
        errs = []

        for option in self.options:
            if option.start_date < self.start_date:
                result = False
                errs.append((
                    'bad_start_date', (
                        option.coverage.code,
                        self.start_date)))
            elif option.start_date < option.coverage.start_date:
                result = False
                errs.append((
                    'bad_start_date', (
                        option.coverage.code,
                        option.coverage.start_date)))
        return result, errs

    def init_subscription_document_request(self):
        DocRequest = Pool().get('document.request')
        if not (hasattr(self, 'documents') and self.documents):
            good_req = DocRequest()
            good_req.needed_by = self
            good_req.save()
        else:
            good_req = self.documents[0]
        documents = []
        product_docs, errs = self.product.get_result(
            'documents', {
                'contract': self,
                'date': self.start_date,
                'appliable_conditions_date': self.appliable_conditions_date})
        if errs:
            return False, errs
        if product_docs:
            documents.extend([(doc_desc, self) for doc_desc in product_docs])
        for option in self.options:
            if not option.status == 'active':
                continue
            option_docs, errs = self.product.get_result(
                'documents', {
                    'contract': self,
                    'option': option.coverage.code,
                    'appliable_conditions_date':
                    self.appliable_conditions_date,
                    'date': self.start_date})
            if errs:
                return False, errs
            if not option_docs:
                continue
            documents.extend([(doc_desc, self) for doc_desc in option_docs])
        for elem in self.covered_elements:
            for option in elem.options:
                if not option.status == 'active':
                    continue
                sub_docs, errs = self.product.get_result(
                    'documents', {
                        'contract': self,
                        'option': option.coverage.code,
                        'date': self.start_date,
                        'appliable_conditions_date':
                        self.appliable_conditions_date,
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

    @classmethod
    def subscribe_contract(cls, *args, **kwargs):
        # Set running process to None to avoid associating the new contract to
        # a process
        with Transaction().set_context(running_process=None):
            result = super(Contract, cls).subscribe_contract(*args, **kwargs)
            result.save()
            return result


class ContractOption:
    __name__ = 'contract.option'

    status_selection = fields.Function(
        fields.Boolean('Status'),
        'on_change_with_status_selection', 'setter_void')

    @classmethod
    def default_status_selection(cls):
        return True

    @fields.depends('status_selection', 'status')
    def on_change_status_selection(self):
        return {'status': 'active' if self.status_selection else 'refused'}

    @fields.depends('status')
    def on_change_with_status_selection(self, name=None):
        return self.status and self.status == 'active'
