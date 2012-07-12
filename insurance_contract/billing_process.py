#from trytond.modules.coop_utils import WithAbstract
from trytond.modules.coop_utils import WithAbstract, get_descendents
from trytond.modules.coop_utils import convert_ref_to_obj

from trytond.modules.insurance_process import CoopProcess
from trytond.modules.insurance_process import ProcessState, CoopStepView
from trytond.model import fields
from trytond.modules.insurance_contract import GenericContract
from trytond.modules.insurance_process import CoopStep, CoopStateView
from trytond.transaction import Transaction

from trytond.pool import Pool

__all__ = [
    'BillingProcessState',
    'BillingProcess',
    'BillParameters',
    'BillLineForDisplay',
    'BillDisplay',
    ]


class BillParameters(CoopStep):
    'Bill Parameters'

    __name__ = 'ins_contract.billing_process.bill_parameters'

    start_date = fields.Date(
        'Start Date',
        required=True)

    end_date = fields.Date(
        'End Date',
        required=True)

    @staticmethod
    def before_step_init(wizard):
        if Transaction().context['active_model'] \
                                in get_descendents(GenericContract, True):
            wizard.process_state.for_contract = '%s,%s' % (
                Transaction().context['active_model'],
                Transaction().context['active_id'])
        else:
            return (False, ['Could not find a contract to bill'])
        contract = wizard.process_state.get_contract()
        bill_dates = contract.billing_manager[0].next_billing_dates()
        wizard.bill_parameters.start_date = bill_dates[0]
        wizard.bill_parameters.end_date = bill_dates[1]
        return (True, [])

    @staticmethod
    def check_step_valid_interval(wizard):
        if wizard.bill_parameters.start_date > wizard.bill_parameters.end_date:
            return (False, ['Start date must be greater than End date'])
        return (True, [])

    @staticmethod
    def post_step_calculate_bill(wizard):
        contract = wizard.process_state.get_contract()
        billing_manager = contract.billing_manager[0]
        start_date = wizard.bill_parameters.start_date
        end_date = wizard.bill_parameters.end_date
        the_bill = billing_manager.bill(start_date, end_date)
        WithAbstract.save_abstract_objects(wizard, ('the_bill', the_bill))
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Bill Parameters'


class BillLineForDisplay(CoopStepView):
    'Bill Line'

    __name__ = 'ins_contract.billing_process.bill_line_view'

    line_amount_ht = fields.Numeric('Amount HT')

    line_amount_ttc = fields.Numeric('Amount TTC')

    line_start_date = fields.Date('Start Date')

    line_end_date = fields.Date('End Date')

    line_name = fields.Char('Short Description')

    line_base_price = fields.Numeric('Base Price')

    def init_from_bill_line(self, line):
        self.line_amount_ht = line.amount_ht
        self.line_amount_ttc = line.amount_ttc
        self.line_start_date = line.start_date
        self.line_end_date = line.end_date
        self.line_name = line.get_rec_name('')
        self.line_base_price = line.base_price


class BillDisplay(CoopStep):
    'Bill Displayer'

    __name__ = 'ins_contract.billing_process.bill_display'

    bill_amount_ht = fields.Numeric('Amount HT')

    bill_amount_ttc = fields.Numeric('Amount TTC')

    bill_start_date = fields.Date('Start Date')

    bill_end_date = fields.Date('End Date')

    bill_lines = fields.One2Many(
        'ins_contract.billing_process.bill_line_view',
        None,
        'Bill Lines'
        )

    @staticmethod
    def before_step_init(wizard):
        BillLineViewer = Pool().get(
            'ins_contract.billing_process.bill_line_view')
        bill = WithAbstract.get_abstract_objects(wizard, 'the_bill')
        wizard.bill_display.bill_amount_ht = bill.amount_ht
        wizard.bill_display.bill_amount_ttc = bill.amount_ttc
        wizard.bill_display.bill_start_date = bill.start_date
        wizard.bill_display.bill_end_date = bill.end_date
        wizard.bill_display.bill_lines = []
        for line in bill.lines:
            bill_line = BillLineViewer()
            bill_line.init_from_bill_line(line)
            wizard.bill_display.bill_lines.append(bill_line)
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Bill Display'


class BillingProcessState(ProcessState, WithAbstract):
    'Billing Process State'

    __abstracts__ = [('the_bill', 'ins_contract.billing.bill')]
    __name__ = 'ins_contract.billing_process.process_state'

    for_contract = fields.Reference(
        'Contract',
        'get_contract_models')

    @staticmethod
    def get_contract_models():
        return get_descendents(GenericContract)

    def get_contract(self):
        if self.for_contract:
            return convert_ref_to_obj(self.for_contract)
        return None


class BillingProcess(CoopProcess):
    'Billing Process'

    __name__ = 'ins_contract.billing_process'

    config_data = {
        'process_state_model': 'ins_contract.billing_process.process_state'
        }

    bill_parameters = CoopStateView(
        'ins_contract.billing_process.bill_parameters',
        'insurance_contract.parameters_view')

    bill_display = CoopStateView(
        'ins_contract.billing_process.bill_display',
        'insurance_contract.bill_view')

    def do_complete(self):
        the_bill = WithAbstract.get_abstract_objects(self, 'the_bill')
        the_bill.save()
        return (True, [])

    @staticmethod
    def coop_process_name():
        return 'Billing Process'
