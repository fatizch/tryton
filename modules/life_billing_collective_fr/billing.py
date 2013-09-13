from trytond.pyson import Eval
from trytond.wizard import StateTransition, StateView, Button

from trytond.modules.coop_utils import model, fields, utils
__all__ = [
    'RateLine',
    ]


class RateLine(model.CoopSQL, model.CoopView):
    'Rate Line'

    __name__ = 'billing.rate_line'

    contract = fields.Many2One('contract.contract', 'Contract',
        ondelete='CASCADE',
        states={'invisible': ~~Eval('parent')})
    covered_element = fields.Many2One('ins_contract.covered_element',
        'Covered Element', ondelete='CASCADE')
    option = fields.Many2One('contract.subscribed_option', 'Option',
        ondelete='CASCADE')
    tranche = fields.Many2One('tranche.tranche', 'Tranche',
        ondelete='RESTRICT', states={'invisible': ~Eval('tranche')})
    fare_class = fields.Many2One('collective.fare_class', 'Fare Class',
        states={'invisible': ~Eval('fare_class_group')})
    index = fields.Many2One('table.table_def', 'Index',
        states={'invisible': ~Eval('index')}, ondelete='RESTRICT')
    parent = fields.Many2One('billing.rate_line', 'Parent', ondelete='CASCADE')
    childs = fields.One2Many('billing.rate_line', 'parent', 'Childs',
        states={'invisible': ~~Eval('tranche')})
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    rate = fields.Numeric('Rate')
    sum_rate = fields.Function(
        fields.Numeric('Sum Rate', digits=(16, 4)),
        'get_sum_rate')
    reference_value = fields.Function(
        fields.Char('Reference Value'),
        'get_reference_value')

    def add_child(self):
        if utils.is_none(self, 'childs'):
            self.childs = []
        child_line = self.__class__()
        self.childs.append(child_line)
        return child_line

    def add_main_rate_line(self, tranche=None, fare_class=None, index=None):
        child_line = self.add_child()
        child_line.tranche = tranche
        child_line.fare_class = fare_class
        child_line.index = index
        return child_line

    def add_option_rate_line(self, option, rate):
        child_line = self.add_child()
        child_line.option = option
        child_line.rate = rate
        return child_line

    def get_rec_name(self, name):
        if self.covered_element:
            return self.covered_element.rec_name
        elif self.option:
            return self.option.rec_name
        elif self.tranche:
            return self.tranche.rec_name
        elif self.fare_class:
            return self.fare_class.rec_name
        elif self.index:
            return self.index.rec_name

    def get_sum_rate(self, name):
        if self.contract:
            return None
        return (self.rate if self.rate else 0) + sum(
            map(lambda x: x.sum_rate, self.childs))


class RateNote(model.CoopSQL, model.CoopView):
    'Rate Note'

    __name__ = 'billing.rate_note'

    client = fields.Many2One('party.party', 'Client', ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    status = fields.Selection([
            ('draft', 'Draft'),
            ('ready_to_be_sent', 'Ready to be sent'),
            ('sent', 'sent'),
            ('completed_by_client', 'Completed by Client'),
            ('validated', 'Validated'),
            ], 'Status', sort=False)
    lines = fields.One2Many('billing.rate_note_line', 'rate_note', 'Lines')


class RateNoteLine(model.CoopSQL, model.CoopView):
    'Rate Note Line'

    __name__ = 'billing.rate_note_line'

    rate_note = fields.Many2One('billing.rate_note', 'Rate Note',
        ondelete='CASCADE')
    quantity = fields.Numeric('Quantity')
    rate_line = fields.Many2One('billing.rate_line', 'Rate Line')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)))
    currency = fields.Function(fields.Many2One('currency.currency', 'Currency',
            on_change_with=['journal']), 'on_change_with_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
            on_change_with=['journal']), 'on_change_with_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')
    parent = fields.Many2One('billing.rate_note_line', 'Parent',
        ondelete='CASCADE')
    childs = fields.One2Many('billing.rate_note_line', 'parent', 'Childs')


class RateNoteParameters(model.CoopView):
    'Rate Note Parameters'

    __name__ = 'billing.rate_note_process_parameters'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    clients = fields.Many2Many('billing.rate_note_process_parameters-clients',
        'parameters_view', 'client', 'Clients')


class RateNoteParametersClientsRelation(model.CoopView):
    'Rate Note Parameters Clients Relation'

    __name__ = 'billing.rate_note_process_parameters-clients'

    parameters_view = fields.Many2One('billing.rate_note_process_parameters',
        'Parameter View')
    client = fields.Many2One('party.party', 'Client')


class RateNoteProcess(model.CoopWizard):
    'Rate Note Process'

    __name__ = 'billing.rate_note_process'

    start_state = 'parameters'
