# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import PYSONEncoder

from trytond.modules.coog_core import model, fields, coog_date, utils


__all__ = [
    'CreateSlip',
    'InvoiceSlipParameters',
    ]


class CreateSlip(Wizard):
    'Create Slip'
    __name__ = 'account.invoice.create.slip'

    start = StateView('account.invoice.slip.parameters',
        'account_invoice_slip.create_slip_parameters_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate', 'open_slip', 'tryton-ok', default=True)])
    open_slip = StateAction('account_invoice.act_invoice_form')

    @classmethod
    def __setup__(cls):
        super(CreateSlip, cls).__setup__()
        cls._error_messages.update({
                'missing_required_inputs': 'All fields must be set before '
                'proceeding',
                })

    def default_start(self, name):
        active_model = Transaction().context.get('active_model', None)
        if active_model != 'account.invoice.slip.configuration':
            return {}
        config = Pool().get(active_model)(
            Transaction().context.get('active_id'))
        return {
            'party': config.party.id,
            'accounts': [x.id for x in config.accounts],
            'journal': config.journal.id,
            'slip_kind': config.slip_kind,
            'name': config.name,
            }

    def do_open_slip(self, action):
        self.check_inputs()
        slips = self.generate_slips()
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', slips[::])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}

    def check_inputs(self):
        if not all(getattr(self.start, x, None)
                for x in self._check_input_fields()):
            self.raise_user_error('missing_required_inputs')

    def _check_input_fields(self):
        return {'party', 'accounts', 'slip_date', 'journal', 'slip_kind'}

    def generate_slips(self):
        Slip = Pool().get('account.invoice.slip.configuration')
        slips = Slip.generate_slips(self.get_slip_parameters())
        return [x.id for x in slips]

    def get_slip_parameters(self):
        return [{
                'party': self.start.party,
                'accounts': list(self.start.accounts),
                'slip_kind': self.start.slip_kind,
                'journal': self.start.journal,
                'date': self.start.slip_date,
                'name': self.start.name,
                }]


class InvoiceSlipParameters(model.CoogView):
    'Invoice Slip Parameters'
    __name__ = 'account.invoice.slip.parameters'

    party = fields.Many2One('party.party', 'Party')
    accounts = fields.Many2Many('account.account', None, None, 'Accounts')
    slip_kind = fields.Selection([('slip', 'Slip')], 'Slip Kind')
    slip_date = fields.Date('Slip Date')
    journal = fields.Many2One('account.journal', 'Journal')
    name = fields.Char('Name')

    @staticmethod
    def default_slip_date():
        return coog_date.get_last_day_of_last_month(utils.today())
