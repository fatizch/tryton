from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.modules.cog_utils import fields, utils

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
                'no_option': 'At least an option must be selected',
                'bad_start_date': 'Option %s must be subscribed after %s',
                'need_option': 'At least one option must be selected for %s',
                'need_covered': 'There must be at least one covered element',
                'payment_bank_account_required': 'The payment bank account is '
                'required as the payment mode is Direct Debit',
                'no_subscriber_address': 'The selected subscriber does not '
                'have an address',
                })
        cls.__rpc__.update({'get_allowed_payment_methods': RPC(instantiate=0)})

    @classmethod
    def copy(cls, contracts, default=None):
        clones = super(Contract, cls).copy(contracts, default)
        if Transaction().context.get('copy_mode', 'functional') != 'functional':
            return clones
        Process = Pool().get('process')
        products = set([x.product for x in clones])
        processes = Process.search([
                ('for_products', 'in', [x.id for x in products]),
                ('kind', '=', 'subscription'),
                ])
        for clone in clones:
            process = [x for x in processes if clone.product in x.for_products]
            if process:
                clone.current_state = process[0].all_steps[0]
                clone.save()
        return clones

    @fields.depends('com_product')
    def on_change_with_product_desc(self, name=None):
        return self.com_product.description if self.com_product else ''

    @fields.depends('subscriber')
    def on_change_with_subscriber_desc(self, name=None):
        return self.subscriber.summary if self.subscriber else ''

    def on_change_subscriber_kind(self):
        super(Contract, self).on_change_subscriber_kind()
        self.subscriber_desc = ''

    def check_product_not_null(self):
        if not self.product:
            return False, (('no_product', ()),)
        return True, ()

    def check_subscriber_not_null(self):
        if not self.subscriber:
            return False, (('no_subscriber', ()),)
        return True, ()

    def check_subscriber_address(self):
        if not self.subscriber:
            return False, (('no_subscriber', ()),)
        if not self.subscriber.addresses:
            return False, (('no_subscriber_address', ()),)
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

    @classmethod
    def subscribe_contract(cls, *args, **kwargs):
        # Set running process to None to avoid associating the new contract to
        # a process
        with Transaction().set_context(running_process=None):
            result = super(Contract, cls).subscribe_contract(*args, **kwargs)
            result.save()
            return result

    def generate_and_attach_reports(self, template_codes):
        """template_codes should be a comma separated list
        of document template codes between single quotes,
        i.e : 'template1', 'template2', etc.
        """
        pool = Pool()
        Template = pool.get('document.template')
        Attachment = pool.get('ir.attachment')
        Report = pool.get('document.generate.report', type='report')
        Date = pool.get('ir.date')

        template_instances = Template.search([('code', 'in', template_codes),
                ('internal_edm', '=', 'True')])

        for template_instance in template_instances:
            _, filedata, _, file_basename = Report.execute(
                [self.id], {
                    'id': self.id,
                    'ids': [self.id],
                    'model': 'contract',
                    'doc_template': [template_instance],
                    'party': self.subscriber.id,
                    'address': self.subscriber.addresses[0].id,
                    'sender': None,
                    'sender_address': None,
                    })
            data = Report.unoconv(filedata, 'odt', 'pdf')

            attachment = Attachment()
            attachment.resource = 'contract,%s' % self.id
            attachment.data = data
            date_string = Date.date_as_string(utils.today(),
                    self.company.party.lang)
            date_string_underscore = ''.join([c if c.isdigit() else "_"
                    for c in date_string])
            attachment.name = '%s_%s_%s.pdf' % (template_instance.name,
                self.rec_name, date_string_underscore)
            attachment.document_desc = template_instance.document_desc
            attachment.save()


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
        self.status = 'active' if self.status_selection else 'refused'

    @fields.depends('status')
    def on_change_with_status_selection(self, name=None):
        return self.status and self.status == 'active'
