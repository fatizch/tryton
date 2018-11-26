# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.model import ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import PYSONEncoder, Bool, Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils, coog_date

__all__ = [
    'Agent',
    'CreateInvoicePrincipal',
    'CreateInvoicePrincipalAsk',
    ]


class Agent(metaclass=PoolMeta):
    __name__ = 'commission.agent'

    insurer = fields.Many2One('insurer', 'Insurer', ondelete='RESTRICT',
        states={
            'invisible': ~Eval('is_for_insurer'),
            'required': Bool(Eval('is_for_insurer')),
            }, domain=[('party', '=', Eval('party'))],
        depends=['is_for_insurer', 'party'])
    is_for_insurer = fields.Function(
        fields.Boolean('For insurer'), 'on_change_with_is_for_insurer')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        handler = TableHandler(cls, module_name)
        to_migrate = not handler.column_exist('insurer')

        super(Agent, cls).__register__(module_name)

        # Migration from 1.10 : Store insurer
        if to_migrate:
            pool = Pool()
            to_update = cls.__table__()
            insurer = pool.get('insurer').__table__()
            party = pool.get('party.party').__table__()
            update_data = party.join(insurer, condition=(
                    insurer.party == party.id)
                ).select(insurer.id.as_('insurer_id'), party.id)
            cursor.execute(*to_update.update(
                    columns=[to_update.insurer],
                    values=[update_data.insurer_id],
                    from_=[update_data],
                    where=update_data.id == to_update.party))

    @fields.depends('party')
    def on_change_with_is_for_insurer(self, name=None):
        return self.party.is_insurer if self.party else False


class CreateInvoicePrincipal(Wizard):
    'Create Invoice Principal'

    __name__ = 'commission.create_invoice_principal'

    start_state = 'ask'
    ask = StateView('commission.create_invoice_principal.ask',
        'commission_insurer.commission_create_invoice_principal_ask_view_form',
        [Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('account_invoice.act_invoice_form')

    def create_insurers_notice(self):
        pool = Pool()
        Insurer = pool.get('insurer')
        Slip = pool.get('account.invoice.slip.configuration')

        parameters = Insurer.generate_slip_parameters(self.ask.notice_kind,
            parties=self.ask.insurers)

        if not parameters:
            return []

        for parameter in parameters:
            parameter['date'] = self.ask.until_date
            parameter['journal'] = self.ask.journal
        return Slip.generate_slips(parameters)

    def do_create_(self, action):
        Invoice = Pool().get('account.invoice')
        invoices = self.create_insurers_notice()

        if self.ask.post_invoices:
            Invoice.post(invoices)
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', [x.id for x in invoices])])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}


class CreateInvoicePrincipalAsk(ModelView):
    'Create Invoice Principal'
    __name__ = 'commission.create_invoice_principal.ask'
    company = fields.Many2One('company.company', 'Company', required=True)
    insurers = fields.Many2Many('party.party', None, None, 'Insurers',
        required=True, domain=[('is_insurer', '=', True)])
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    post_invoices = fields.Boolean('Post Invoices')
    until_date = fields.Date('Until Date')
    notice_kind = fields.Selection([('all', 'All'), ('options', 'Premiums')],
        'Notice Kind')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_journal():
        pool = Pool()
        Journal = pool.get('account.journal')
        journals = Journal.search([
                ('type', '=', 'commission'),
                ], limit=1)
        if journals:
            return journals[0].id

    @staticmethod
    def default_until_date():
        return coog_date.get_last_day_of_last_month(utils.today())

    @staticmethod
    def default_notice_kind():
        return 'options'
