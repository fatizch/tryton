# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import Workflow, ModelView
from trytond.pyson import Eval, Or
from trytond.model.exceptions import ValidationError, AccessError
from trytond.i18n import gettext
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.coog_core import utils, fields, model
from trytond.modules.currency_cog.currency import DEF_CUR_DIG
from trytond.modules.report_engine import Printable

__all__ = [
    'ThirdPartyDebtAssignmentRequest',
    'ThirdPartyDebtAssignmentRequestInvoice',
    ]

REQUEST_STATES = [
    ('draft', 'Draft'),
    ('transmitted', 'Transmitted'),
    ('in_study', 'In study'),
    ('accepted', 'Accepted'),
    ('refused', 'Refused'),
    ('paid', 'Paid'),
    ]
DEBT_ASSIGNMENT_LEVEL = [
    ('', ''),
    ('full', 'Full'),
    ('partial', 'Partial'),
    ]
LEVEL_STATES = Or(Eval('state') == 'draft', Eval('state') == 'transmitted',
    Eval('state') == 'in_study', Eval('state') == 'refused')
IN_STUDY_DATE_STATES = Or(Eval('state') == 'draft',
    Eval('state') == 'transmitted', Eval('state') == 'refused')


class ThirdPartyDebtAssignmentRequest(Workflow, model.CoogSQL, model.CoogView,
        Printable):
    'Third Party Debt Assignment Request'

    __name__ = 'debt_assignment_request'
    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='RESTRICT', states={'readonly': Eval('state') != 'draft'})
    third_party = fields.Many2One('party.party', 'Third Party', required=True,
        ondelete='RESTRICT', states={'readonly': Eval('state') != 'draft'})
    requested_amount = fields.Function(fields.Numeric(
        'Requested amount', digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits']), 'get_requested_amount')
    invoices = fields.Many2Many('debt_assignment_request-account.invoice',
        'debt_assignment_request', 'invoice', 'Invoices',
        domain=[('party', '=', Eval('party'))],
        depends=['party', 'state'], states={
            'readonly': Eval('state') != 'draft'})
    state = fields.Selection(REQUEST_STATES, 'State',
        required=True, readonly=True)
    transmission_date = fields.Date('Transmission date', states={
        'required': Eval('state') != 'draft',
        'invisible': Eval('state') == 'draft'}, readonly=True)
    debt_assignment_level = fields.Selection(DEBT_ASSIGNMENT_LEVEL,
        'Debt assignment level', states={'invisible': LEVEL_STATES,
        'readonly': Eval('state') == 'paid'})
    debt_assignment_amount = fields.Numeric('Debt assignment amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)), states={'required':
            Eval('debt_assignment_level') == 'partial',
            'invisible': Eval('debt_assignment_level') != 'partial',
            'readonly': Eval('state') == 'paid'}, domain=['OR',
            ('debt_assignment_amount', '=', None),
            ('debt_assignment_amount', '<=', Eval('requested_amount'))],
        depends=['requested_amount', 'currency_digits'])
    contract_to_terminate = fields.Selection([('', ''), ('yes', 'Yes'),
        ('no', 'No')], 'Contract to terminate', states={
        'invisible': Eval('state') != 'refused',
        'required': Eval('state') == 'refused'})
    refusal_date = fields.Date('Refusal date', states={
        'invisible': Eval('state') != 'refused',
        'required': Eval('state') == 'refused'}, readonly=True)
    acceptance_date = fields.Date('Acceptance date', states={
        'invisible': LEVEL_STATES,
        'required': Eval('state') == 'accepted'}, readonly=True)
    in_study_date = fields.Date('In study date', states={
        'invisible': IN_STUDY_DATE_STATES,
        'required': Eval('state') == 'in_study'}, readonly=True)
    is_paid = fields.Function(fields.Boolean('Is paid', help='If set, '
        'all the invoices of the request are paid'), 'get_is_paid',
        searcher='search_is_paid')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')

    @classmethod
    def __setup__(cls):
        super(ThirdPartyDebtAssignmentRequest, cls).__setup__()
        cls._transitions |= set((
            ('draft', 'transmitted'),
            ('transmitted', 'draft'),
            ('transmitted', 'refused'),
            ('transmitted', 'in_study'),
            ('in_study', 'accepted'),
            ('in_study', 'refused'),
            ('accepted', 'paid'),
            ('accepted', 'refused'),
            ))
        cls._buttons.update({
            'transmit': {
                'invisible': Eval('state') != 'draft',
                'icon': 'tryton-forward',
                'depends': ['state'],
                },
            'refuse': {
                'invisible': Or(Eval('state') == 'draft',
                    Eval('state') == 'refused', Eval('state') == 'paid'),
                'icon': 'tryton-cancel',
                'depends': ['state'],
                },
            'accept': {
                'invisible': Eval('state') != 'in_study',
                'icon': 'tryton-forward',
                'depends': ['state'],
                },
            'study': {
                'invisible': Eval('state') != 'transmitted',
                'icon': 'tryton-forward',
                'depends': ['state'],
                },
            'pay': {
                'invisible': Eval('state') != 'accepted',
                'icon': 'tryton-ok',
                'depends': ['state'],
                },
            'draft': {
                'invisible': Eval('state') != 'transmitted',
                'icon': 'tryton-back',
                'depends': ['state'],
                },
            })

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def delete(cls, debt_assignment_requests):
        for request in debt_assignment_requests:
            if request.state != 'draft':
                raise AccessError(gettext(
                    'third_party_debt_assignment.msg_request_delete_draft',
                    request=request.rec_name))
        super(ThirdPartyDebtAssignmentRequest, cls).delete(
            debt_assignment_requests)

    @classmethod
    @ModelView.button
    @Workflow.transition('transmitted')
    def transmit(cls, debt_assignment_requests):
        for request in debt_assignment_requests:
            if not request.invoices:
                raise ValidationError(gettext(
                    'third_party_debt_assignment.msg_empty_invoices'))
            request.transmission_date = utils.today()
            request.state = 'transmitted'
        cls.save(debt_assignment_requests)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, debt_assignment_requests):
        for request in debt_assignment_requests:
            request.transmission_date = None
            request.state = 'draft'
        cls.save(debt_assignment_requests)

    @classmethod
    @ModelView.button
    @Workflow.transition('refused')
    def refuse(cls, debt_assignment_requests):
        for request in debt_assignment_requests:
            request.refusal_date = utils.today()
            request.state = 'refused'
        cls.save(debt_assignment_requests)

    @classmethod
    @ModelView.button
    @Workflow.transition('in_study')
    def study(cls, debt_assignment_requests):
        for request in debt_assignment_requests:
            request.in_study_date = utils.today()
            request.state = 'in_study'
        cls.save(debt_assignment_requests)

    @classmethod
    @ModelView.button
    @Workflow.transition('accepted')
    def accept(cls, debt_assignment_requests):
        for request in debt_assignment_requests:
            request.acceptance_date = utils.today()
            request.state = 'accepted'
        cls.save(debt_assignment_requests)

    @classmethod
    @ModelView.button
    @Workflow.transition('paid')
    def pay(cls, debt_assignment_requests):
        for request in debt_assignment_requests:
            if not request.debt_assignment_level:
                raise ValidationError(gettext('third_party_debt_assignment.'
                    'msg_undefined_debt_assignment_level'))
            request.state = 'paid'
        cls.save(debt_assignment_requests)

    def get_requested_amount(self, name):
        return sum([invoice.total_amount for invoice in self.invoices])

    @classmethod
    def get_is_paid(cls, third_party_assignment_requests, name):
        is_paid = {}
        for request in third_party_assignment_requests:
            for invoice in request.invoices:
                if invoice.state != 'paid':
                    is_paid[request.id] = False
                    break
            else:
                is_paid[request.id] = True
        return is_paid

    @classmethod
    def search_is_paid(cls, name, clause):
        if clause[-1]:
            return ['invoices.state', 'not in',
                ['posted', 'validated', 'draft', 'cancel']]

        return ['invoices.state', '!=', 'paid']

    @classmethod
    def get_currency(cls, third_party_assignment_requests, name=None):
        return {x.id: x.invoices[0].currency.id if x.invoices else None
            for x in third_party_assignment_requests}

    @classmethod
    def get_currency_digits(cls, third_party_assignment_requests, name=None):
        return {x.id: x.currency.digits if x.currency else 2
            for x in third_party_assignment_requests}

    def get_doc_template_kind(self):
        res = super(ThirdPartyDebtAssignmentRequest,
            self).get_doc_template_kind()
        res.append('debt_assignement')
        return res

    def get_sender(self):
        pool = Pool()
        company_id = Transaction().context.get('company', None)
        if company_id:
            return pool.get('company.company')(company_id).party
        return None

    def get_contact(self):
        return self.party


class ThirdPartyDebtAssignmentRequestInvoice(model.CoogSQL, model.CoogView):
    'Third Party Debt Assignment Request Invoice'

    __name__ = 'debt_assignment_request-account.invoice'
    debt_assignment_request = fields.Many2One('debt_assignment_request',
        'Debt assignment request', ondelete='CASCADE')
    invoice = fields.Many2One('account.invoice',
        'Invoice', ondelete='RESTRICT')
