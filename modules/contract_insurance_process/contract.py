from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.pyson import Eval, Or, Bool
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
                'no_option': 'At least an option must be selected',
                'bad_start_date': 'Option %s must be subscribed after %s',
                'need_option': 'At least one option must be selected for %s',
                'need_covered': 'There must be at least one covered element',
                'no_subscriber_address': 'The selected subscriber does not '
                'have an address',
                })
        cls.__rpc__.update({'get_allowed_payment_methods': RPC(instantiate=0)})
        cls._buttons['button_activate']['invisible'] = Or(
            cls._buttons['button_activate']['invisible'],
            Bool(Eval('current_state', False)))
        cls._buttons['button_decline']['invisible'] = Or(
            cls._buttons['button_decline']['invisible'],
            Bool(Eval('current_state', False)))

    @classmethod
    def copy(cls, contracts, default=None):
        clones = super(Contract, cls).copy(contracts, default)
        if Transaction().context.get('copy_mode', 'functional') != \
                'functional':
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

    def check_subscriber_address(self):
        if not self.subscriber:
            return False, (('no_subscriber', ()),)
        if not self.subscriber.addresses:
            return False, (('no_subscriber_address', ()),)
        return True, ()

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

    def generate_and_attach_reports(self, template_codes, creator=None):
        """template_codes should be a comma separated list
        of document template codes between single quotes,
        i.e : 'template1', 'template2', etc.
        """
        pool = Pool()
        Template = pool.get('report.template')
        Attachment = pool.get('ir.attachment')
        Report = pool.get('report.generate', type='report')
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
            report = Report()
            report.template_extension = 'odt'
            report.extension = 'pdf'
            _, data = Report.convert(report, filedata)

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
            attachment.origin = creator or self
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
