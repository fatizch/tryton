# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from decimal import Decimal
from sql.aggregate import Max
from dateutil.relativedelta import relativedelta
from itertools import groupby

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or, Bool, In, Not, Len
from trytond.model import ModelView
from trytond.transaction import Transaction
from trytond.rpc import RPC
from trytond.tools import grouped_slice

from trytond.modules.coog_core import fields, model, coog_string, utils, \
    coog_date
from trytond.modules.account.tax import TaxableMixin
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.claim_indemnification.benefit import \
    INDEMNIFICATION_DETAIL_KIND
from trytond.modules.claim_indemnification.benefit import INDEMNIFICATION_KIND
from trytond.modules.currency_cog.currency import DEF_CUR_DIG
from trytond.modules.rule_engine import get_rule_mixin
from trytond.modules.coog_core.coog_date import FREQUENCY_CONVERSION_TABLE
from trytond.modules.coog_core.extra_details import WithExtraDetails

from .benefit import ANNUITY_FREQUENCIES

__all__ = [
    'Claim',
    'Loss',
    'ClaimService',
    'Indemnification',
    'IndemnificationDetail',
    'IndemnificationControlRule',
    ]


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    invoices = fields.Function(
        fields.One2Many('account.invoice', None, 'Invoices'),
        'get_invoices')
    indemnifications_details = fields.Function(
        fields.One2Many('claim.indemnification.detail', None,
            'Indemnifications Details'),
        'get_indemnifications_details')
    is_services_deductible = fields.Function(fields.Boolean(
            'Is Services Deductible'),
        'get_is_services_deductible')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._buttons.update({
                'button_calculate': {
                    'invisible': Eval('status').in_(['closed']),
                    },
                'create_indemnification': {
                    'invisible': Eval('status').in_(['closed']),
                    },
                'schedule_all': {
                    'invisible': Eval('status').in_(['closed']),
                    },
                })

    def get_is_services_deductible(self, name=None):
        return (self.indemnifications_details and all([x.kind == 'deductible'
                    for x in self.indemnifications_details]))

    def get_indemnifications_details(self, name):
        pool = Pool()
        IndemnificationDetail = pool.get('claim.indemnification.detail')
        config = pool.get('claim.configuration').get_singleton()
        domain_ = [('indemnification.service.claim', '=', self.id)]
        if config.show_indemnification_limit:
            Indemnification = pool.get('claim.indemnification')
            indemnifications = [x.id for x in Indemnification.search(
                    [('service.claim', '=', self.id)], order=[(
                                'start_date', config.sorting_method)],
                    limit=config.show_indemnification_limit)]
            domain_.append(('indemnification', 'in', indemnifications))
        return [i.id for i in IndemnificationDetail.search(domain_)]

    def calculate(self):
        for loss in self.losses:
            for service in loss.services:
                if service.status == 'calculating':
                    service.calculate()
            loss.services = loss.services
        self.losses = self.losses

    @classmethod
    @ModelView.button
    def button_calculate(cls, claims):
        for claim in claims:
            claim.calculate()
        cls.save(claims)

    def get_invoices(self, name):
        pool = Pool()
        Detail = pool.get('account.invoice.line.claim_detail')
        details = Detail.search([('claim', '=', self.id)])
        invoices = [detail.invoice_line.invoice for detail in details]
        invoices = list(set(invoices))
        return [invoice.id for invoice in invoices]

    def validate_indemnifications(self):
        Indemnification = Pool().get('claim.indemnification')
        to_validate = []
        for loss in self.losses:
            for service in loss.services:
                for indemnification in service.indemnifications:
                    if indemnification.status == 'controlled':
                        to_validate.append(indemnification)
        if not to_validate:
            return
        Indemnification.validate_indemnification(to_validate)
        Indemnification.invoice(to_validate)

    @classmethod
    @ModelView.button_action(
        'claim_indemnification.act_create_claim_indemnification_wizard')
    def create_indemnification(cls, services):
        pass

    @classmethod
    @ModelView.button
    def schedule_all(cls, claims):
        if not claims:
            return
        Indemnification = Pool().get('claim.indemnification')
        Indemnification.schedule(claims[0].indemnifications_to_schedule)


class Loss:
    __metaclass__ = PoolMeta
    __name__ = 'claim.loss'

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls._error_messages.update({
                'indemnized_losses': 'Some draft losses have active '
                'indemnifications, they may have to be reevaluated:\n\n%s',
                'bad_indemnification_shares': 'Total share amount for service '
                '%(service)s should be 100: %(total_share).2f',
                'missing_end_date': 'The end date is missing on the loss',
                'missing_closing_reason': 'The closing reason is missing on the'
                ' loss',
                'unpaid_indemnification': '%s indemnification(s) remains '
                'unpaid',
                'gap_found_in_period': 'A gap has been detected from %s to %s',
                'no_indemnifications': 'No indemnification has been found',
                })

    def check_indemnification_gaps(self, service):
        pool = Pool()
        Date = pool.get('ir.date')
        lang = pool.get('res.user')(Transaction().user).language
        indemnifications = [x
            for x in service.indemnifications
            if x.status in ('scheduled', 'controlled', 'validated',
                'rejected', 'paid')]
        indemnifications = sorted(indemnifications, key=lambda x: x.start_date)
        indemn = None
        for index, indemn in enumerate(indemnifications[1:]):
            previous_indemn = indemnifications[index - 1]
            if (previous_indemn.end_date and indemn.start_date -
                    previous_indemn.end_date > datetime.timedelta(0)):
                self.__class__.raise_user_warning('gap_found_in_period_%s' %
                    '-'.join([previous_indemn.id, indemn.id]),
                    'gap_found_in_period',
                    (Date.date_as_string(previous_indemn.end_date, lang),
                        Date.date_as_string(indemn.start_date, lang)))
        if indemnifications and indemn and indemn.end_date < self.end_date:
            self.__class__.raise_user_warning('gap_found_in_period_%s' %
                '-'.join([indemn.id, self.id]),
                'gap_found_in_period', (
                    Date.date_as_string(indemn.end_date, lang),
                    Date.date_as_string(self.end_date, lang)))

    def close(self, sub_status, date=None):
        super(Loss, self).close(sub_status, date)
        if self.with_end_date and not self.end_date:
            self.__class__.raise_user_error('missing_end_date')
        if self.with_end_date and not self.closing_reason:
            self.__class__.raise_user_error('missing_closing_reason')
        for service in self.services:
            if not service.indemnifications:
                self.__class__.raise_user_warning(
                    'no_indemnifications_%s' % service.id,
                    'no_indemnifications')
                continue
            unpaid = [x for x in service.indemnifications
                if x.status == 'calculated']
            if unpaid:
                self.__class__.raise_user_error(
                    'unpaid_indemnification', len(unpaid))
            if not self.end_date:
                return
            self.check_indemnification_gaps(service)
        for service in self.services:
            if service.benefit.indemnification_kind != 'capital':
                continue
            total_share = sum(x.share for x in service.indemnifications)
            service_delegation = service.option.coverage.insurer. \
                get_delegation(service.option.coverage.insurance_kind)
            if not service_delegation:
                continue
            if total_share != 1:
                if service_delegation.claim_create_indemnifications or \
                        service_delegation.claim_pay_indemnifications:
                    self.append_functional_error('bad_indemnification_shares', {
                            'service': self.rec_name,
                            'total_share': str(int(total_share * 100))})
                else:
                    self.raise_user_warning('bad_indemnification_shares_%s'
                        % str(self.id), 'bad_indemnification_shares', {
                            'service': self.rec_name,
                            'total_share': str(int(total_share * 100))}
                        )

    @classmethod
    def activate(cls, losses):
        indemnized_losses = []
        for loss in losses:
            if loss.state == 'active':
                continue
            for service in loss.services:
                if any(x.status in ['validated', 'paid', 'calculated',
                            'scheduled', 'controlled']
                        for x in service.indemnifications):
                    indemnized_losses.append(loss)
                    break
        if indemnized_losses:
            cls.raise_user_warning('indemnized_' + ','.join(
                    str(x.id) for x in indemnized_losses), 'indemnized_losses',
                ('\n'.join(x.rec_name for x in indemnized_losses),))
        super(Loss, cls).activate(losses)


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    indemnifications = fields.One2Many('claim.indemnification',
        'service', 'Indemnifications', delete_missing=True)
    multi_level_view = fields.One2Many('claim.indemnification',
        'service', 'Indemnifications', delete_missing=True)
    paid_until_date = fields.Function(fields.Date('Paid Until Date',
            readonly=True,
            states={'invisible': ~Eval(
                    'has_automatic_period_calculation')},
            depends=['has_automatic_period_calculation']),
        getter='get_paid_until_date', searcher='search_paid_until_date')
    has_automatic_period_calculation = fields.Function(
        fields.Boolean('has_automatic_period_calculation'),
        getter='getter_has_automatic_period_calculation')
    payment_accepted_until_date = fields.Date('Payments Accepted Until:',
          states={'invisible': ~Eval(
                'has_automatic_period_calculation')},
          depends=['has_automatic_period_calculation'])
    annuity_frequency = fields.Selection(ANNUITY_FREQUENCIES,
        'Annuity Frequency', states={
            'invisible': ~(Eval('has_automatic_period_calculation'))},
          depends=['has_automatic_period_calculation'])
    deductible_end_date = fields.Function(
        fields.Date('Deductible End Date'),
        'get_deductible_end_date')
    last_indemnification_date = fields.Function(
        fields.Date('Last Indemnification Date'),
        'get_last_indemnification_date')
    indemnification_start_date = fields.Function(
        fields.Date('Indemnification Start Date'),
        'get_indemnification_start_date')

    @classmethod
    def __setup__(cls):
        super(ClaimService, cls).__setup__()
        cls._buttons.update({
                'create_indemnification': {},
                'fill_extra_datas': {},
                })
        cls._error_messages.update({
                'overlap_date': 'Are you sure you want to cancel '
                'the periods between %s and %s?',
                'offset_date': 'The date is not equal to the cancelled date',
                'multiple_capital_indemnifications': 'There may not be '
                'multiple capital indemnifications for a given beneficiary, '
                'the current one will be cancelled',
                })

    @classmethod
    def _export_skips(cls):
        return super(ClaimService, cls)._export_skips() | {'multi_level_view'}

    @classmethod
    def copy(cls, services, default=None):
        default = default.copy() if default else {}
        if 'indemnification' not in default:
            default['indemnifications'] = []
            default['multi_level_view'] = []
        return super(ClaimService, cls).copy(services, default)

    @classmethod
    def get_paid_until_date(cls, services, name):
        indemnification = Pool().get('claim.indemnification').__table__()
        cursor = Transaction().connection.cursor()
        result = {x.id: None for x in services}
        for sub_services in grouped_slice(services):
            cursor.execute(*indemnification.select(indemnification.service,
                    Max(indemnification.end_date),
                    where=indemnification.service.in_(
                        [x.id for x in sub_services]),
                    group_by=[indemnification.service]))
            for service_id, max_date in cursor.fetchall():
                result[service_id] = max_date
        return result

    def get_last_indemnification_date(self, name):
        indemnifications = [x for x in self.indemnifications
            if x.status == 'paid']
        if indemnifications:
            return max(x.end_date or x.start_date for x in indemnifications)
        return None

    def get_indemnification_start_date(self, name):
        if self.deductible_end_date:
            return self.deductible_end_date + datetime.timedelta(days=1)
        return None

    @classmethod
    def search_paid_until_date(cls, name, clause):
        _, operator, value = clause
        indemnification = Pool().get('claim.indemnification').__table__()
        Operator = fields.SQL_OPERATORS[operator]
        query_table = indemnification.select(indemnification.service,
            group_by=[indemnification.service],
            having=Operator(Max(indemnification.end_date), value))
        return [('id', 'in', query_table)]

    def calculate(self):
        cur_dict = {}
        self.init_dict_for_rule_engine(cur_dict)
        cur_dict['date'] = self.loss.start_date
        cur_dict['currency'] = self.get_currency()
        self.func_error = None
        self.status = 'calculated'
        self.create_indemnification(cur_dict)

    @classmethod
    def calculate_services(cls, instances):
        for instance in instances:
            res, errs = instance.calculate()

    def getter_has_automatic_period_calculation(self, name):
        return self.benefit.has_automatic_period_calculation() \
            if self.benefit else False

    def get_deductible_end_date(self, name=None, args=None):
        if not args:
            args = {}
            self.init_dict_for_rule_engine(args)
        if 'date' not in args:
            args['date'] = self.loss.start_date
        return self.benefit.calculate_deductible(args)

    def is_deductible(self):
        details = [x for indemn in self.indemnifications for x
            in indemn.details]
        if not details and self.loss.end_date:
            deductible_end_date = self.get_deductible_end_date() or \
                coog_date.add_day(self.loss.start_date, -1)
            return self.loss.end_date < deductible_end_date
        if not self.loss.end_date:
            return False
        return all([x.kind == 'deductible' for x in details])

    def init_from_loss(self, loss, benefit):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')
        super(ClaimService, self).init_from_loss(loss, benefit)
        if benefit.benefit_rules:
            self.annuity_frequency = benefit.benefit_rules[0].annuity_frequency
        self.indemnifications = []
        if self.loss.start_date and self.loss.end_date:
            deductible_end_date = self.get_deductible_end_date() or \
                coog_date.add_day(self.loss.start_date, -1)
            if self.loss.end_date < deductible_end_date:
                beneficiary = self.get_beneficiaries_data(self.loss.start_date)
                if len(beneficiary) == 1 and beneficiary[0][1] == 1:
                    indemnification = Indemnification(
                        start_date=self.loss.start_date,
                        end_date=self.loss.end_date
                        )
                    indemnification.init_from_service(self)
                    indemnification.beneficiary = beneficiary[0]
                    indemnification.save()
                    Indemnification.calculate([indemnification])
                    self.indemnifications = [indemnification]

    def regularize_indemnification(self, indemnification, details_dict,
            currency):
        amount = sum([x.amount for x in self.indemnifications
            if x.status == 'paid' and x.currency == currency])
        if amount:
            details_dict['regularisation'] = [
                {
                    'amount_per_unit': amount,
                    'nb_of_unit': -1,
                }]

    @classmethod
    def cancel_indemnification(cls, services, from_date, to_date=None,
            beneficiary=None):
        # We cancel / delete all indemnifications whose period overstep
        # the given `at_date` parameter. For capitals, we only check the
        # `beneficiary` parameter, `None` will clear all
        Date = Pool().get('ir.date')
        to_cancel = []
        to_delete = []
        ClaimIndemnification = Pool().get('claim.indemnification')
        for service in services:
            for indemn in service.indemnifications:
                if indemn.status in ('cancelled', 'cancel_paid'):
                    continue
                if (service.benefit.indemnification_kind != 'capital' and
                        ((not to_date or indemn.start_date <= to_date) and
                            from_date < indemn.end_date)) or (
                        service.benefit.indemnification_kind == 'capital' and
                        (beneficiary is None or
                            indemn.beneficiary == beneficiary)):
                    if indemn.status == 'paid':
                        to_cancel.append(indemn)
                    elif indemn.status != 'rejected':
                        to_delete.append(indemn)
        if to_cancel:
            if (service.benefit.indemnification_kind != 'capital' and
                    (from_date > to_cancel[0].start_date or
                        to_date < to_cancel[-1].end_date)):
                cls.raise_user_error('offset_date')
            if service.benefit.indemnification_kind != 'capital':
                cls.raise_user_warning('overlap_date', 'overlap_date',
                    (Date.date_as_string(to_cancel[0].start_date),
                        Date.date_as_string(to_cancel[-1].end_date)))
            else:
                cls.raise_user_warning('multiple_capital_indemnifications_%s' %
                    str([x.id for x in services]),
                    'multiple_capital_indemnifications')
            ClaimIndemnification.cancel_indemnification(to_cancel)
        if to_delete:
            ClaimIndemnification.delete(to_delete)

    @classmethod
    @ModelView.button_action(
        'claim_indemnification.act_create_indemnification_wizard')
    def create_indemnification(cls, services):
        pass

    @classmethod
    @ModelView.button_action(
        'claim_indemnification.act_fill_extra_data_wizard')
    def fill_extra_datas(cls, services):
        pass

    @classmethod
    def create_indemnifications(cls, services, until=None):
        Indemnification = Pool().get('claim.indemnification')
        if until is None:
            until = utils.today()
        indemnifications = []
        for service in services:
            indemnifications += service.create_missing_indemnifications(until)
        if not indemnifications:
            return
        Indemnification.calculate(indemnifications)
        Indemnification.save(indemnifications)

    def create_missing_indemnifications(self, until):
        if self.paid_until_date >= until:
            return []
        if not self.indemnifications:
            return []
        if self.benefit.indemnification_kind != 'annuity':
            return []
        periods = []
        for period in self.get_new_indemnification_periods(until):
            periods.append(self.clone_last_indemnification(*period))
        return periods

    def get_full_period(self, from_date):
        nb_month = FREQUENCY_CONVERSION_TABLE[self.annuity_frequency]
        period_start_date = from_date + relativedelta(day=1,
            month=((from_date.month - 1) // nb_month) * nb_month + 1)
        if self.annuity_frequency:
            period_end_date = period_start_date + \
                relativedelta(months=nb_month, days=-1)
            return (period_start_date, period_end_date)
        elif self.loss.end_date:
            return (period_start_date, self.loss.end_date)

    def get_new_indemnification_periods(self, until):
        periods = []
        end_date = self.paid_until_date
        while end_date < until:
            base_date = coog_date.add_day(end_date, 1)
            start_date, end_date = self.get_full_period(base_date)
            if end_date <= until:
                periods.append((base_date, end_date))
        return periods

    def clone_last_indemnification(self, start, end):
        Indemnification = Pool().get('claim.indemnification')
        indemnification = Indemnification(start_date=start, end_date=end)
        indemnification.beneficiary = self.indemnifications[-1].beneficiary
        indemnification.status = 'calculated'
        indemnification.service = self
        indemnification.product = self.indemnifications[-1].product
        indemnification.share = self.indemnifications[-1].share
        return indemnification

    def calculate_annuity_periods(self, from_date, to_date):
        '''
            This method calculate annuity period between two dates.
            It return a list of tuples with
            start date,
            end date,
            full_period to know if the period is a full period,
            prorata represents the period number of month if is a full period
            else the number of days,
            unit represent the time unit 'days', 'month' ...
        '''
        nb_month = FREQUENCY_CONVERSION_TABLE[self.annuity_frequency]
        period_start_date, period_end_date = self.get_full_period(from_date)
        res = []
        while period_start_date <= to_date:
            full_period = True
            cur_period_start = max(period_start_date, from_date)
            cur_period_end = min(period_end_date, to_date)
            if (cur_period_start == from_date and
                    from_date != period_start_date):
                full_period = False
            if (cur_period_end == to_date and
                    to_date != period_end_date):
                full_period = False
            if full_period:
                res.append((cur_period_start, cur_period_end, full_period,
                        nb_month, self.annuity_frequency[0:-2]))
            else:
                res.append((cur_period_start, cur_period_end, full_period,
                    (cur_period_end - cur_period_start).days + 1, 'day'))
            period_start_date, period_end_date = self.get_full_period(
                period_end_date + relativedelta(days=1))
        return res


class Indemnification(model.CoogView, model.CoogSQL, ModelCurrency,
        TaxableMixin):
    'Indemnification'

    __name__ = 'claim.indemnification'

    beneficiary = fields.Many2One('party.party', 'Beneficiary',
        ondelete='RESTRICT',
        states={'readonly': Eval('status') != 'calculated'},
        depends=['status'])
    service = fields.Many2One('claim.service', 'Claim Service',
        ondelete='CASCADE', select=True, required=True,
        states={'readonly': Eval('status') == 'paid'}, depends=['status'])
    kind = fields.Function(
        fields.Selection(INDEMNIFICATION_KIND, 'Kind', sort=False),
        'get_kind')
    kind_string = kind.translated('kind')
    start_date = fields.Date('Start Date', states={
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid'),
            'invisible': ~Eval('service.loss.with_end_date')
            }, depends=['manual', 'status', 'kind'], required=True)
    end_date = fields.Date('End Date', states={
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid'),
            'invisible': ~Eval('service.loss.with_end_date')
            }, depends=['manual', 'status', 'kind'])
    product = fields.Many2One('product.product', 'Product', states={
            'invisible': Bool(Eval('product', False)) &
            (Len(Eval('possible_products', [])) == 1),
            'required': Eval('status', '') != 'calculated',
            }, domain=[('id', 'in', Eval('possible_products'))],
        ondelete='RESTRICT', depends=['possible_products', 'status'])
    possible_products = fields.Function(
        fields.Many2Many('product.product', None, None, 'Possible Products'),
        'get_possible_products')
    taxes_included = fields.Function(
        fields.Boolean('Taxes included'),
        'on_change_with_taxes_included')
    status = fields.Selection([
            ('calculated', 'Calculated'),
            ('scheduled', 'Scheduled'),
            ('controlled', 'Controlled'),
            ('validated', 'Validated'),
            ('rejected', 'Rejected'),
            ('paid', 'Paid'),
            ('cancelled', 'Annule'),
            ('cancel_paid', 'Paid & Cancelled'),
            ('cancel_scheduled', 'Schedule Cancelled'),
            ('cancel_validated', 'Validate Cancelled'),
            ('cancel_controlled', 'Control Cancelled'),
            ], 'Status', sort=False,
        states={'readonly': Eval('status') == 'paid'}, depends=['status'])
    status_string = status.translated('status')
    amount = fields.Function(
        fields.Numeric('Amount',
            digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
            states={'readonly': ~Eval('manual') | (Eval('status') == 'paid')
                | Eval('taxes_included')},
            depends=['currency_digits', 'status', 'manual', 'taxes_included']),
        'get_amount', 'setter_void')
    total_amount = fields.Numeric('Total Amount',
            digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
            states={'readonly': ~Eval('manual') | (Eval('status') == 'paid')
                | ~Eval('taxes_included')},
            depends=['currency_digits', 'status', 'manual', 'taxes_included'])
    tax_amount = fields.Function(
        fields.Numeric('Tax Amount',
            digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
            depends=['currency_digits']),
        'on_change_with_tax_amount')
    local_currency_amount = fields.Numeric('Local Currency Amount',
        digits=(16, Eval('local_currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': ~Eval('local_currency'),
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid')},
        depends=['local_currency_digits', 'status', 'manual'])
    local_currency = fields.Many2One('currency.currency', 'Local Currency',
        ondelete='RESTRICT', states={
            'invisible': ~Eval('local_currency'),
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid')},
        depends=['status', 'manual'])
    local_currency_digits = fields.Function(
        fields.Integer('Local Currency Digits', states={'invisible': True}),
        'on_change_with_local_currency_digits')
    details = fields.One2Many('claim.indemnification.detail',
        'indemnification', 'Details',
        states={'readonly': Or(~Eval('manual'), Eval('status') == 'paid')},
        depends=['status', 'manual'], delete_missing=True)
    manual = fields.Boolean('Manual Calculation',
        states={'readonly': Eval('status') == 'paid'}, depends=['status'])
    benefit_description = fields.Function(
        fields.Char('Benefit Description'),
        'get_benefit_description')
    control_reason = fields.Char('Control Reason')
    payback_method = fields.Selection([
            ('continuous', 'Continuous'),
            ('immediate', 'Immediate'),
            ('planned', 'Planned'),
            ('', ''),
            ], 'Repayment Method', states={
                'invisible': Not(In(Eval('status'),
                        ['cancelled', 'cancel_paid'])),
                'readonly': Eval('status') == 'cancel_paid'
            })
    payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Payment Term', states={
            'invisible': Not(In(Eval('status'),
                    ['cancelled', 'cancel_paid'])),
            'readonly': Eval('status') == 'cancel_paid'
            }, ondelete='RESTRICT', depends=['status'])
    is_paid = fields.Function(fields.Boolean('Paid'), 'get_is_paid')
    share = fields.Numeric('Share', domain=['OR', [('share', '=', None)],
            [('share', '>', 0), ('share', '<=', 1)]])
    note = fields.Char('Note', states={
            'invisible': ~Bool(Eval('note'))},
        readonly=True, depends=['note'])
    journal = fields.Many2One('account.payment.journal', 'Journal',
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(Indemnification, cls).__setup__()
        cls.__rpc__.update({
                'validate_indemnification': RPC(instantiate=0, readonly=False),
                'reject_indemnification': RPC(instantiate=0, readonly=False),
                })
        cls._buttons.update({
                'calculate': {
                    'invisible': Eval('status') != 'calculated'},
                'validate_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
                'reject_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
                'cancel_indemnification': {
                    'invisible': Eval('status') != 'paid'},
                'modify_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
                'schedule': {
                    'invisible': Eval('status') != 'calculated'},
                })
        cls._error_messages.update({
                'cannot_create_indemnifications': 'The insurer %(insurer)s '
                'did not allow to create indemnifications.',
                'cannot_pay_indemnifications': 'The insurer %(insurer)s '
                'did not allow to pay indemnifications.',
                'cannot_schedule_draft_loss': 'Cannot schedule '
                'indemnifications for draft loss %(loss)s',
                'no_bank_account': 'No bank account found for the beneficiary '
                '%s on loss %s',
                })
        cls._order = [('start_date', 'ASC')]

    @classmethod
    def __register__(cls, module):
        TableHandler = backend.get('TableHandler')
        handler = TableHandler(cls, module)

        # Migrate from 1.8 : rename 'amount' to 'total_amount'
        if handler.column_exist('amount'):
            handler.column_rename('amount', 'total_amount')

        super(Indemnification, cls).__register__(module)

    @classmethod
    def validate(cls, indemnifications):
        super(Indemnification, cls).validate(indemnifications)
        with model.error_manager():
            cls.check_insurer_delegation(indemnifications)

    @classmethod
    def check_insurer_delegation(cls, indemnifications):
        coverages = {x.service.option.coverage for x in indemnifications}
        for coverage in coverages:
            if not coverage.get_insurer_flag(coverage,
                    'claim_create_indemnifications'):
                cls.append_functional_error('cannot_create_indemnifications',
                    {'insurer': coverage.insurer.rec_name})

    @property
    def tax_date(self):
        return self.start_date

    @property
    def taxable_lines(self):
        return [(self.product.supplier_taxes, self.amount, 1)]

    def get_is_paid(self, name):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        AccountInvoice = pool.get('account.invoice')
        invoice_detail = pool.get(
            'account.invoice.line.claim_detail').__table__()
        invoice_line = pool.get('account.invoice.line').__table__()
        query_table = invoice_detail.join(invoice_line, condition=(
                invoice_detail.invoice_line == invoice_line.id))
        cursor.execute(*query_table.select(invoice_line.invoice, where=(
                    invoice_detail.indemnification == self.id)))
        ids = cursor.fetchall()
        invoices = AccountInvoice.search([('id', 'in', list(ids))])
        for invoice in invoices:
            if invoice.state == 'paid' and invoice.reconciliation_date:
                return True
        return False

    def get_benefit_description(self, name):
        if self.service and self.service.benefit:
            return self.service.benefit.rec_name
        return ''

    def get_possible_products(self, name):
        return [x.id for x in self.service.benefit.products]

    def update_product(self):
        Product = Pool().get('product.product')
        products = self.get_possible_products(None)
        self.product = getattr(self, 'product', None)
        if self.product and self.product.id not in products:
            self.product = None
        if len(products) == 1:
            self.product = Product(products[0])
        if products:
            self.possible_products = Product.browse(products)
        else:
            self.possible_products = []
        if self.product:
            self.taxes_included = self.product.taxes_included
        else:
            self.taxes_included = False

    def init_from_service(self, service):
        self.status = 'calculated'
        self.service = service
        self.update_product()

    def get_kind(self, name=None):
        if self.service:
            return self.service.benefit.indemnification_kind
        return ''

    def calculate_amount_and_end_date_from_details(self, del_service,
            currency):
        self.amount = 0
        self.local_currency_amount = 0
        if not hasattr(self, 'details'):
            return
        main_currency = del_service.get_currency()
        for detail in self.details:
            detail.calculate_amount()
            if currency == main_currency:
                self.amount += detail.amount
            else:
                self.local_currency_amount += detail.amount
                self.local_currency = currency
            if hasattr(detail, 'end_date'):
                self.end_date = detail.end_date
        if self.local_currency_amount > 0:
            Currency = Pool().get('currency.currency')
            self.amount = Currency.compute(self.local_currency,
                self.local_currency_amount, main_currency)
        self.amount = main_currency.round(self.amount)

    def get_currency(self):
        if self.service:
            return self.service.get_currency()

    def require_control(self):
        pool = Pool()
        ClaimConfiguration = pool.get('claim.configuration')
        config = ClaimConfiguration.get_singleton()
        ctx = {}
        self.init_dict_for_rule_engine(ctx)
        ctx['date'] = self.start_date
        if not config.control_rule:
            return False, ''
        return config.control_rule.calculate_rule(ctx)

    def init_dict_for_rule_engine(self, cur_dict):
        self.service.init_dict_for_rule_engine(cur_dict)
        cur_dict['indemnification'] = self

    @fields.depends('local_currency')
    def on_change_with_local_currency_digits(self, name=None):
        if self.local_currency:
            return self.local_currency.digits
        return DEF_CUR_DIG

    @fields.depends('product')
    def on_change_with_taxes_included(self, name=None):
        if not self.product:
            return False
        return self.product.taxes_included

    def get_amount(self, name):
        if not self.product.supplier_taxes:
            return self.total_amount
        pool = Pool()
        Tax = pool.get('account.tax')
        amount = Tax.reverse_compute(self.total_amount,
            self.product.supplier_taxes, self.start_date)
        amount = amount.quantize(Decimal(1) / 10 ** self.currency_digits)
        return amount

    @fields.depends('amount', 'total_amount')
    def on_change_with_tax_amount(self, name=None):
        return (self.total_amount or 0) - (self.amount or 0)

    @fields.depends('amount', 'currency_digits', 'product', 'start_date',
        'total_amount')
    def on_change_amount(self):
        self.update_amounts()

    @fields.depends('amount', 'currency_digits', 'product', 'start_date',
        'total_amount')
    def on_change_total_amount(self):
        self.update_amounts()

    def update_amounts(self):
        if not self.product:
            return
        if not self.product.supplier_taxes:
            if self.product.taxes_included:
                self.amount = self.total_amount
            else:
                self.total_amount = self.amount
            return
        if self.product.taxes_included:
            self.amount = self.get_amount(None)
        else:
            self.total_amount = self.amount + sum(x['amount']
                for x in self._get_taxes().values())

    def get_rec_name(self, name):
        return u'%s - %s: %s [%s]' % (
            coog_string.translate_value(self, 'start_date')
            if self.start_date else '',
            coog_string.translate_value(self, 'end_date')
            if self.end_date else '',
            self.get_currency().amount_as_string(self.amount)
            if self.amount else '',
            coog_string.translate_value(self, 'status') if self.status else '',
            )

    def is_pending(self):
        return self.amount > 0 and self.status not in ['paid', 'rejected']

    @classmethod
    def check_schedulability(cls, indemnifications):
        for indemnification in indemnifications:
            if indemnification.service.loss.state == 'draft':
                cls.append_functional_error('cannot_schedule_draft_loss',
                    {'loss': indemnification.service.loss.rec_name})
            journal = indemnification.journal
            if (journal and journal.needs_bank_account() and
                    not indemnification.beneficiary.get_bank_account(
                        indemnification.start_date)):
                cls.append_functional_error('no_bank_account', (
                        indemnification.beneficiary.rec_name,
                        indemnification.service.claim.name))

    @classmethod
    @ModelView.button
    def schedule(cls, indemnifications):
        Event = Pool().get('event')
        schedule = []
        schedule_cancel = []
        control = []
        control_cancel = []
        with model.error_manager():
            cls.check_schedulability(indemnifications)
        for indemnification in indemnifications:
            do_control, reason = indemnification.require_control()
            if do_control is True:
                if indemnification.status == 'cancelled':
                    schedule_cancel.append(indemnification)
                else:
                    schedule.append(indemnification)
            else:
                if indemnification.status == 'cancelled':
                    control_cancel.append(indemnification)
                else:
                    control.append(indemnification)
        cls.write(
            schedule, {
                'status': 'scheduled', 'control_reason': reason
                },
            schedule_cancel, {
                'status': 'cancel_scheduled', 'control_reason': reason
                },
            control, {'status': 'controlled'},
            control_cancel, {'status': 'cancel_controlled'})
        Event.notify_events(indemnifications, 'schedule_indemnification')

    def get_claim_sub_status(self):
        if self.status == 'calculated':
            return 'waiting_validation'
        elif self.status == 'validated':
            return 'validated'
        elif self.status == 'paid':
            return 'paid'
        else:
            return 'instruction'

    @classmethod
    @ModelView.button
    def calculate(cls, indemnifications):
        pool = Pool()
        IndemnificationDetail = pool.get('claim.indemnification.detail')
        Indemnification = pool.get('claim.indemnification')
        with model.error_manager():
            cls.check_calculable(indemnifications)
        to_save = []
        for indemnification in indemnifications:
            cur_dict = {}
            indemnification.service.init_dict_for_rule_engine(cur_dict)
            cur_dict['indemnification'] = indemnification
            cur_dict['date'] = cur_dict['loss'].start_date
            cur_dict['start_date'] = indemnification.start_date
            cur_dict['end_date'] = indemnification.end_date
            cur_dict['currency'] = indemnification.service.get_currency()
            details = indemnification.service.benefit.calculate_benefit(
                cur_dict)
            details = [IndemnificationDetail(**detail) for detail in details]
            indemnification.details = details
            amount = sum([getattr(d, 'amount', 0) for d in details])
            if indemnification.product.taxes_included:
                indemnification.total_amount = amount
            else:
                indemnification.amount = amount
                indemnification.update_amounts()
            to_save.append(indemnification)
        Indemnification.save(to_save)

    @classmethod
    def check_calculable(cls, indemnifications):
        pass

    @classmethod
    @ModelView.button
    def validate_indemnification(cls, indemnifications):
        if not indemnifications:
            return
        validate = []
        cancelled = []
        for indemn in indemnifications:
            if indemn.status == 'cancelled':
                cancelled.append(indemn)
            else:
                validate.append(indemn)
        cls.write(
            validate, {'status': 'validated'},
            cancelled, {'status': 'cancel_validated'})
        Event = Pool().get('event')
        Event.notify_events(indemnifications, 'validate_indemnification')

    @classmethod
    def reject_indemnification(cls, indemnifications_with_values):
        """
        This method takes a dictionnary with indemnifications a keys and
        dictionnary of new values (mainly the note field) as values.
        """
        if not indemnifications_with_values:
            return
        to_write = []
        for indemnification, values in indemnifications_with_values.items():
            values.update({'status': 'rejected'})
            to_write.extend([[indemnification], values])
        cls.write(*to_write)
        Event = Pool().get('event')
        Event.notify_events(indemnifications_with_values.keys(),
            'reject_indemnification')

    @classmethod
    @ModelView.button
    def cancel_indemnification(cls, indemnifications):
        if not indemnifications:
            return
        pool = Pool()
        cls.write(indemnifications, {'status': 'cancelled'})
        Event = pool.get('event')
        Event.notify_events(indemnifications, 'cancel_indemnification')

    @classmethod
    def control_indemnification(cls, indemnifications):
        control = []
        cancelled = []
        for indemn in indemnifications:
            if indemn.status == 'cancelled':
                cancelled.append(indemn)
            else:
                control.append(indemn)
        cls.write(control, {'status': 'controlled'},
                  cancelled, {'status': 'cancel_controlled'})

    @classmethod
    def get_journal(cls):
        pool = Pool()
        Journal = pool.get('account.journal')

        journals = Journal.search([
                ('type', '=', 'claim'),
                ], limit=1)
        if journals:
            return journals[0]

    @classmethod
    def _get_invoice(cls, key):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        party = key['party']
        if 'payment_term' in key:
            payment_term = key['payment_term']
        elif party.supplier_payment_term:
            payment_term = party.supplier_payment_term
        else:
            config = pool.get('claim.configuration').get_singleton()
            payment_term = config.claim_default_payment_term
        return Invoice(
            company=key['company'],
            type='in',
            business_kind='claim_invoice',
            journal=cls.get_journal(),
            party=party,
            invoice_address=party.address_get(type='invoice'),
            currency=key['currency'],
            account=party.account_payable,
            payment_term=payment_term,
            invoice_date=utils.today(),
            currency_date=utils.today(),
            description='%s' % (party.full_name),
            )

    def invoice_line_description(self):
        return u'%s - %s- %s - %s' % (
            self.service.loss.claim.claimant.rec_name,
            self.service.loss.rec_name,
            coog_string.translate_value(self, 'start_date')
            if self.start_date else '',
            coog_string.translate_value(self, 'end_date')
            if self.end_date else '')

    @classmethod
    def _get_invoice_line(cls, key, invoice, indemnification):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Tax = pool.get('account.tax')
        LineDetail = pool.get('account.invoice.line.claim_detail')
        invoice_line = InvoiceLine()
        invoice_line.invoice = invoice
        invoice_line.type = 'line'
        invoice_line.product = key['product']
        invoice_line.quantity = 1
        invoice_line.description = indemnification.invoice_line_description()
        invoice_line.party = invoice.party
        invoice_line.on_change_product()
        if invoice_line.product.taxes_included:
            invoice_line.unit_price = Tax.reverse_compute(
                indemnification.total_amount,
                invoice_line.product.supplier_taxes,
                indemnification.start_date)
            invoice_line.unit_price = invoice_line.unit_price.quantize(
                Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1])
        else:
            invoice_line.unit_price = indemnification.amount
        if indemnification.status == 'cancel_validated':
            invoice_line.unit_price = -invoice_line.unit_price
        detail = LineDetail()
        detail.service = indemnification.service
        detail.indemnification = indemnification
        detail.claim = indemnification.service.loss.claim
        invoice_line.claim_details = [detail]
        return invoice_line

    def _group_to_claim_invoice_key(self):
        return {
            'party': self.beneficiary,
            'product': self.product,
            'company': self.service.contract.company,
            'currency': self.currency,
            'journal': self.journal,
            }

    @classmethod
    def invoice(cls, indemnifications):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoices = []
        paid = []
        cancelled = []

        with model.error_manager():
            cls.check_invoicable(indemnifications)

        def group_key(x):
            return x._group_to_claim_invoice_key()

        indemnifications.sort(key=group_key)
        for key, group_indemnification in groupby(indemnifications,
                key=group_key):
            invoice = cls._get_invoice(key)
            lines = []
            for indemnification in group_indemnification:
                if indemnification.status == 'cancel_validated':
                    cancelled.append(indemnification)
                    if indemnification.payback_method == 'immediate':
                        # do something special here, discuss with Fred
                        pass
                    elif indemnification.payback_method == 'planned':
                        key.update({'payment_term':
                                indemnification.payment_term})
                else:
                    paid.append(indemnification)
                lines.extend([cls._get_invoice_line(key, invoice,
                        indemnification)])
            invoice.lines = lines
            invoices.append(invoice)
        Invoice.save(invoices)
        Invoice.post(invoices)
        cls.write(paid, {'status': 'paid'},
            cancelled, {'status': 'cancel_paid'})

    @classmethod
    def check_invoicable(cls, indemnifications):
        coverages = {x.service.option.coverage for x in indemnifications}
        for coverage in coverages:
            if not coverage.get_insurer_flag(coverage,
                    'claim_pay_indemnifications'):
                cls.append_functional_error('cannot_pay_indemnifications',
                    {'insurer': coverage.insurer.rec_name})

    @classmethod
    @ModelView.button_action(
        'claim_indemnification.act_create_claim_indemnification_wizard')
    def modify_indemnification(cls, indemnifications):
        pass


class IndemnificationDetail(model.CoogSQL, model.CoogView, ModelCurrency,
        WithExtraDetails):
    'Indemnification Detail'

    __name__ = 'claim.indemnification.detail'

    indemnification = fields.Many2One('claim.indemnification',
        'Indemnification', ondelete='CASCADE', required=True, select=True)
    start_date = fields.Date('Start Date',
        states={'invisible': Eval('indemnification_kind') == 'capital'},
        depends=['indemnification_kind'])
    end_date = fields.Date('End Date',
        states={'invisible': Eval('indemnification_kind') == 'capital'},
        depends=['indemnification_kind'])
    indemnification_kind = fields.Function(
        fields.Selection(INDEMNIFICATION_KIND, 'Indemnification Kind',
            sort=False),
        'get_indemnification_kind')
    kind = fields.Selection(INDEMNIFICATION_DETAIL_KIND, 'Kind', sort=False)
    kind_string = kind.translated('kind')
    amount_per_unit = fields.Numeric('Amount per Unit',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])
    nb_of_unit = fields.Numeric('Nb of Unit')
    unit = fields.Selection(coog_date.DAILY_DURATION, 'Unit')
    unit_string = unit.translated('unit')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])
    description = fields.Text('Description')
    duration_description = fields.Function(
        fields.Char('Duration'),
        'get_duration_description')
    status = fields.Function(
        fields.Char('Status'), 'get_status_string')
    base_amount = fields.Numeric('Base Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])
    benefit_description = fields.Function(
        fields.Char('Prestation'),
        'get_benefit_description')
    indemnification_note = fields.Function(
        fields.Char('Note'),
        'get_indemnification_note')
    indemnification_beneficiary = fields.Function(
        fields.Many2One('party.party', 'Beneficiary'),
        'getter_indemnification_beneficiary')

    @classmethod
    def __setup__(cls):
        super(IndemnificationDetail, cls).__setup__()
        cls._error_messages.update({
                'capital_string': 'Capital',
                })
        cls._order = [('start_date', 'ASC')]

    def get_indemnification_note(self, name):
        return self.indemnification.note

    def get_indemnification_kind(self, name):
        return self.indemnification.kind

    def getter_indemnification_beneficiary(self, name):
        if self.indemnification.beneficiary:
            return self.indemnification.beneficiary.id

    def get_duration_description(self, name):
        if self.indemnification.kind == 'capital':
            return self.raise_user_error('capital_string',
                raise_exception=False)
        return '%s %s(s)' % (self.nb_of_unit, self.unit_string)

    def get_benefit_description(self, name):
        if self.indemnification:
            return self.indemnification.benefit_description
        return ''

    def calculate_amount(self):
        self.amount = self.amount_per_unit * self.nb_of_unit

    def get_currency(self):
        # If a local currency is used details are stored with the local
        # currency to make only one conversion at the indemnification level
        if self.indemnification.local_currency:
            return self.indemnification.local_currency
        else:
            return self.indemnification.currency

    @classmethod
    def create_details_from_dict(cls, details_dict, currency):
        details = []
        for key, fancy_name in INDEMNIFICATION_DETAIL_KIND:
            if key not in details_dict:
                continue
            for detail_dict in details_dict[key]:
                detail = cls(**detail_dict)
                details.append(detail)
                detail.kind = key
        return details

    def get_status_string(self, name):
        return '%s - [%s]' % (
            self.kind_string, self.indemnification.status_string)


class IndemnificationControlRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoogSQL, model.CoogView):
    'Indemnification Control Rule'

    __name__ = 'claim.indemnification.control.rule'

    @classmethod
    def __setup__(cls):
        super(IndemnificationControlRule, cls).__setup__()
        cls.rule.required = True
