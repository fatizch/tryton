from trytond.wizard import Wizard, StateView, Button
from trytond.pool import Pool
from trytond.pyson import Eval

from trytond.modules.coop_utils import fields, model

__all__ = [
    'RenewalStart',
    'RenewalResult',
    'RenewalWizard'
]


class RenewalStart(model.CoopView):
    'Renewal Start'

    __name__ = 'ins_contract.renewal_start'

    renewal_date = fields.Date('Renewal Date', on_change=['renewal_date',
        'renew_what'])
    renew_what = fields.Boolean('All contracts', on_change=['renewal_date',
        'renew_what'])
    will_be_renewed = fields.One2Many('contract.contract', None,
        'Will be renewed', states={'readonly': True,
            'invisible': ~Eval('renew_what')})
    this_contract = fields.Many2One(
        'contract.contract', 'Renew this contract', domain=[
            ('next_renewal_date', '<=', Eval('renewal_date'))],
        depends=['renew_what', 'renewal_date'],
        states={'invisible': ~~Eval('renew_what')})

    def on_change_renewal_date(self):
        if not (hasattr(self, 'renew_what') and self.renew_what):
            return {'will_be_renewed': []}
        Contract = Pool().get('contract.contract')
        to_renew = Contract.search([
            ('next_renewal_date', '<=', self.renewal_date)])
        return {'will_be_renewed': [x.id for x in to_renew],
            'this_contract': None}

    on_change_renew_what = on_change_renewal_date

    def get_contracts_to_renew(self):
        if self.renew_what:
            return self.will_be_renewed
        if self.this_contract:
            return [self.this_contract]
        return []

    @classmethod
    def default_renew_what(cls):
        return True

    @classmethod
    def default_renewal_date(cls):
        Date = Pool().get('ir.date')
        return Date.today()


class RenewalResult(model.CoopView):
    'Renewal Result'

    __name__ = 'ins_contract.renewal_result'

    renewal_log_success = fields.Text('Succeeded', states={'readonly': True})
    renewal_log_failure = fields.Text('Failed', states={'readonly': True})


class RenewalWizard(Wizard):
    'Renewal Wizard'

    __name__ = 'ins_contract.renewal_wizard'

    start_state = 'renewal_start'
    renewal_start = StateView('ins_contract.renewal_start',
        'insurance_contract.renewal_start_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Start', 'renewal_result', 'tryton-go-next')])
    renewal_result = StateView('ins_contract.renewal_result',
        'insurance_contract.renewal_result_form', [
            Button('End', 'end', 'tryton-cancel')])

    def default_renewal_result(self, name):
        to_treat = self.renewal_start.get_contracts_to_renew()
        log = {'Success': [], 'Failed': []}
        for contract in to_treat:
            print contract
            result = contract.renew()
            if result:
                log['Success'].append(contract.rec_name)
            else:
                log['Failed'].append(contract.rec_name)
        res = {}
        res['renewal_log_success'] = '\n'.join(log['Success'])
        res['renewal_log_failure'] = '\n'.join(log['Failed'])
        return res
