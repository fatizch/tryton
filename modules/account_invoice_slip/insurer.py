# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.model import ModelView
from trytond.model.exceptions import ValidationError
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import PYSONEncoder

from trytond.modules.coog_core import fields, coog_date, utils

__all__ = [
    'Insurer',
    'InsurerSlipConfiguration',
    'CreateInsurerSlip',
    'CreateInsurerSlipParameters',
    ]


class Insurer(metaclass=PoolMeta):
    __name__ = 'insurer'

    group_insurer_invoices = fields.Boolean('Group Insurer Invoices',
        help='If True, all insurer related invoices (premiums / claims / etc) '
        'will be grouped in one')

    @classmethod
    def generate_slip_parameters(cls, notice_kind, parties=None):
        insurers = cls._get_insurers_from_notice_kind(notice_kind, parties)
        return [x._generate_slip_parameter(notice_kind) for x in insurers]

    @classmethod
    def _get_insurers_from_notice_kind(cls, notice_kind, parties):
        domain = cls._get_domain_from_notice_kind(notice_kind)
        if parties:
            domain = [domain, [('party', 'in', parties)]]
        else:
            if notice_kind == 'all':
                domain = [domain, [('group_insurer_invoices', '=', True)]]
            else:
                domain = [domain, [
                        ('group_insurer_invoices', 'in', (False, None))]]
        insurers = cls.search(domain)
        if not insurers:
            return []
        grouped = {bool(x.group_insurer_invoices) for x in insurers}
        if len(grouped) != 1:
            raise ValidationError(gettext(
                    'account_invoice_slip.msg_mixed_insurer_configuration'))
        if bool(grouped.pop()) != (notice_kind == 'all'):
            raise ValidationError(gettext(
                    'account_invoice_slip.msg_bad_insurer_configuration'))
        return insurers

    @classmethod
    def _get_domain_from_notice_kind(cls, notice_kind):
        return []

    @classmethod
    def get_journal_from_notice_kind(cls, notice_kind):
        return None

    def _generate_slip_parameter(self, notice_kind):
        accounts = self._get_slip_accounts(notice_kind)
        return {
            'insurer': self,
            'party': self.party,
            'accounts': list(accounts),
            'slip_kind': self._get_slip_business_kind(notice_kind),
            'journal': self.get_journal_from_notice_kind(notice_kind),
            }

    def _get_slip_accounts(self, notice_kind):
        return set()

    @classmethod
    def _get_slip_business_kind(cls, notice_kind):
        return 'all_insurer_invoices'


class InsurerSlipConfiguration(metaclass=PoolMeta):
    __name__ = 'account.invoice.slip.configuration'

    @classmethod
    def _get_new_slip(cls, parameters):
        invoice = super()._get_new_slip(parameters)
        invoice.insurer_role = parameters.get('insurer', None)
        return invoice


class CreateInsurerSlip(Wizard):
    'Create Insurer Slip'

    __name__ = 'account.invoice.create.insurer_slip'

    start_state = 'ask'
    ask = StateView('account.invoice.create.insurer_slip.ask',
        'account_invoice_slip.create_insurer_slip_parameters_view_form',
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


class CreateInsurerSlipParameters(ModelView):
    'Create Insurer Slip Parameters'

    __name__ = 'account.invoice.create.insurer_slip.ask'

    company = fields.Many2One('company.company', 'Company', required=True)
    insurers = fields.Many2Many('party.party', None, None, 'Insurers',
        required=True, domain=[('is_insurer', '=', True)])
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    post_invoices = fields.Boolean('Post Invoices')
    until_date = fields.Date('Until Date')
    notice_kind = fields.Selection([('all', 'All')], 'Notice Kind')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_journal():
        return None

    @staticmethod
    def default_until_date():
        return coog_date.get_last_day_of_last_month(utils.today())

    @staticmethod
    def default_notice_kind():
        return 'all'
