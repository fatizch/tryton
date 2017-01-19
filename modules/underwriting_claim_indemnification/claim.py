# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.wizard import Button, StateView
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields, coog_string, coog_date

__all__ = [
    'BenefitRule',
    'Service',
    'Indemnification',
    'IndemnificationDefinition',
    'CreateIndemnification',
    'CreateIndemnificationUnderwritings',
    ]


class BenefitRule:
    __metaclass__ = PoolMeta
    __name__ = 'benefit.rule'

    @classmethod
    def __setup__(cls):
        super(BenefitRule, cls).__setup__()
        cls._error_messages.update({
                'applied_reduction_decision': 'Applied %(reduction)s %% '
                'reduction after underwriting',
                })

    @classmethod
    def calculation_dates(cls, indemnification, start_date, end_date):
        dates = super(BenefitRule, cls).calculation_dates(indemnification,
            start_date, end_date)
        if not indemnification.apply_underwriting_reduction:
            return dates
        for elem in indemnification.service.underwritings_at_date(
                start_date, end_date):
            if elem.get_decision().decision != 'reduce_indemnification':
                continue
            dates.add(elem.effective_decision_date)
        return dates

    def do_calculate_indemnification_rule(self, args):
        periods = super(BenefitRule, self).do_calculate_indemnification_rule(
            args)
        if not args['indemnification'].apply_underwriting_reduction:
            return periods
        service = args['service']
        for period in periods:
            for elem in service.underwritings_at_date(period['start_date'],
                    period['end_date']):
                decision = elem.get_decision()
                if decision.decision != 'reduce_indemnification':
                    continue
                period['amount'] = service.currency.round(period['amount']
                    * (1 - decision.reduction_percentage))
                period['amount_per_unit'] = service.currency.round(
                    period['amount_per_unit'] * (
                        1 - decision.reduction_percentage))
                period['description'] = period.get('description', '') + \
                    '\n' + self.raise_user_error('applied_reduction_decision',
                        {'reduction': decision.reduction_percentage * 100},
                        raise_exception=False).encode('utf-8')
        return periods


class Service:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    @classmethod
    def __setup__(cls):
        super(Service, cls).__setup__()
        cls._error_messages.update({
                'blocked_indemnifications': 'An underwriting decision '
                'blocked indemnifications for this service starting '
                '%(decision_date)s',
                })

    def underwritings_at_date(self, start, end):
        for elem in self.underwritings:
            if not start:
                yield elem
                continue
            if end and (start <= elem.effective_decision_date <= end):
                yield elem
            elif not end and not elem.effective_decision_date and (
                    elem.effective_decision_date <= start):
                yield elem
            elif elem.effective_decision_end and (
                    elem.effective_decision_date <= start
                    <= elem.effective_decision_end):
                yield elem
            elif end and elem.effective_decision_end and (
                    elem.effective_decision_date <= end
                    <= elem.effective_decision_end):
                yield elem
            elif not elem.effective_decision_end and (
                    elem.effective_decision_date <= end):
                yield elem

    def check_underwritings(self, start, end):
        blocking_decision = self.get_underwriting_blocking_decision(start, end)
        if blocking_decision is not None:
            self.append_functional_error('blocked_indemnifications',
                {'decision_date': coog_string.translate_value(
                        blocking_decision, 'effective_decision_date')})

    def get_underwriting_blocking_decision(self, start, end):
        for elem in self.underwritings_at_date(start, end):
            decision = elem.get_decision()
            if decision.decision == 'block_indemnification':
                return elem


class Indemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    apply_underwriting_reduction = fields.Boolean(
        'Apply underwriting reduction')

    @classmethod
    def check_schedulability(cls, indemnifications):
        super(Indemnification, cls).check_schedulability(indemnifications)
        for indemnification in indemnifications:
            indemnification.service.check_underwritings(
                indemnification.start_date, indemnification.end_date)


class IndemnificationDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    underwritings = fields.Many2Many('underwriting.result', None, None,
        'Underwritings', readonly=True, states={
            'invisible': ~Eval('underwritings')})
    underwriting_reduction = fields.Boolean('Underwriting Reduction',
        readonly=True)
    accept_underwriting_reduction = fields.Boolean(
        'Accept underwriting reduction', states={
            'invisible': ~Eval('underwriting_reduction')},
        depends=['underwriting_reduction'])

    @fields.depends('accept_underwriting_reduction', 'service',
        'underwriting_reduction', 'underwritings')
    def on_change_service(self):
        super(IndemnificationDefinition, self).on_change_service()
        self.underwritings = []
        self.underwriting_reduction = False
        self.accept_underwriting_reduction = False
        if self.service:
            self.underwritings = [x.id for x in self.service.underwritings]
            for elem in self.underwritings:
                if elem.get_decision().decision == 'reduce_indemnification':
                    self.underwriting_reduction = True
                    self.accept_underwriting_reduction = True


class CreateIndemnification(model.FunctionalErrorMixIn):
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    activated_underwritings = StateView(
        'claim.create_indemnification.underwritings',
        'underwriting_claim_indemnification.'
        'create_indemnification_underwritings_view_form', [
            Button('Exit', 'end', 'tryton-cancel'),
            Button('Previous', 'definition', 'tryton-go-previous'),
            Button('Continue', 'calculate', 'tryton-go-next', default=True)])

    def check_input(self):
        result = super(CreateIndemnification, self).check_input()
        input_start_date = self.definition.start_date
        input_end_date = self.definition.end_date
        service = self.definition.service
        to_warn = None
        with model.error_manager():
            service.check_underwritings(input_start_date,
                input_end_date)
            if self.pop_functional_error('blocked_indemnifications'):
                to_warn = service.get_underwriting_blocking_decision(
                    input_start_date, input_end_date)
        # Exit the manager to raise other errors
        if to_warn:
            service.raise_user_warning('blocked_indemnification_warning_%s' %
                str(service.id), 'blocked_indemnifications', (
                    {'decision_date': coog_string.translate_value(to_warn,
                            'effective_decision_date')}))
            if self.definition.start_date < to_warn.effective_decision_date:
                self.definition.end_date = coog_date.add_day(
                    to_warn.effective_decision_date, -1)
                return self.check_input()
        return result

    def init_indemnification(self, indemnification):
        super(CreateIndemnification, self).init_indemnification(
            indemnification)
        if not self.definition.underwriting_reduction:
            indemnification.apply_underwriting_reduction = False
        else:
            indemnification.apply_underwriting_reduction = \
                self.definition.accept_underwriting_reduction

    def transition_calculate(self):
        input_end_date = self.definition.end_date
        underwritings = Pool().get('claim').activate_underwritings_if_needed(
            [self.definition.service.claim], input_end_date)
        if underwritings:
            self.activated_underwritings.underwritings = underwritings
            return 'activated_underwritings'
        return super(CreateIndemnification, self).transition_calculate()

    def default_activated_underwritings(self, name):
        return {
            'underwritings': [x.id
                for x in self.activated_underwritings.underwritings],
            }


class CreateIndemnificationUnderwritings(model.CoogView):
    'Create Indemnification Underwritings'

    __name__ = 'claim.create_indemnification.underwritings'

    underwritings = fields.Many2Many('underwriting', None, None,
        'Underwritings')
