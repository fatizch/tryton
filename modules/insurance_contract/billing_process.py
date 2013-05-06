#from trytond.modules.coop_utils import WithAbstract
from trytond.modules.coop_utils import fields, model
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.transaction import Transaction

from trytond.pool import Pool

__all__ = [
    'BillingProcess',
    'BillParameters',
    'BillDisplay',
]


class BillParameters(model.CoopView):
    'Bill Parameters'

    __name__ = 'ins_contract.billing_process.bill_parameters'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    contract = fields.Many2One(
        'ins_contract.contract', 'Contract', states={'invisible': True})


class BillDisplay(model.CoopView):
    'Bill Displayer'

    __name__ = 'ins_contract.billing_process.bill_display'

    bills = fields.One2Many(
        'ins_contract.billing.bill', None, 'Bill', states={'readonly': True})


class BillingProcess(Wizard):
    'Billing Process'

    __name__ = 'ins_contract.billing_process'

    start_state = 'bill_parameters'
    bill_parameters = StateView(
        'ins_contract.billing_process.bill_parameters',
        'insurance_contract.bill_parameters_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Preview', 'bill_display', 'tryton-go-next')])
    bill_display = StateView(
        'ins_contract.billing_process.bill_display',
        'insurance_contract.bill_display_form', [
            Button('Cancel', 'cancel_bill', 'tryton-cancel'),
            Button('Accept', 'accept_bill', 'tryton-go-next')])
    cancel_bill = StateTransition()
    accept_bill = StateTransition()

    def default_bill_parameters(self, values):
        ContractModel = Pool().get(Transaction().context.get('active_model'))
        contract = ContractModel(Transaction().context.get('active_id'))
        bill_dates = contract.billing_manager[0].next_billing_dates()
        return {
            'contract': contract.id,
            'start_date': bill_dates[0],
            'end_date': bill_dates[1]}

    def default_bill_display(self, values):
        if self.bill_parameters.end_date < self.bill_parameters.start_date:
            self.raise_user_error('bad_dates')
        contract = self.bill_parameters.contract
        if self.bill_parameters.start_date < contract.start_date:
            self.raise_user_error('start_date_too_old')
        billing_manager = contract.billing_manager[0]
        start_date = self.bill_parameters.start_date
        end_date = self.bill_parameters.end_date
        the_bill = billing_manager.bill(start_date, end_date)
        the_bill.contract = None
        the_bill.save()
        return {'bills': [the_bill.id]}

    def transition_cancel_bill(self):
        Bill = Pool().get('ins_contract.billing.bill')
        the_bill = self.bill_display.bills[0]
        Bill.delete([the_bill])
        return 'end'

    def transition_accept_bill(self):
        the_bill = self.bill_display.bills[0]
        the_bill.contract = self.bill_parameters.contract
        the_bill.save()
        return 'end'
