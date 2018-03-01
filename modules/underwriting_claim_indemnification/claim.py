# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields, coog_string

__all__ = [
    'BenefitRule',
    'Service',
    'Indemnification',
    'IndemnificationDefinition',
    'CreateIndemnification',
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
                for data in ('amount', 'base_amount', 'amount_per_unit'):
                    if data not in period:
                        continue
                    period[data] = service.currency.round(period[data]
                        * (1 - decision.reduction_percentage))
                period['description'] = period.get('description', '') + \
                    '\n' + self.raise_user_error('applied_reduction_decision',
                        {'reduction': decision.reduction_percentage * 100},
                        raise_exception=False).encode('utf-8') + '\n'
        return periods


class Service:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    @classmethod
    def __setup__(cls):
        super(Service, cls).__setup__()
        cls._error_messages.update({
                'blocked_indemnifications': 'An underwriting decision '
                'blocks indemnifications for this service starting '
                '%(decision_date)s.',
                'blocked_indemnifications_split': 'An underwriting decision '
                'blocks indemnifications for this service starting '
                '%(decision_date)s. The period you entered will be split.',
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

    def clone_last_indemnifications(self, start, end):
        res = []
        for indemnification in super(Service, self).clone_last_indemnifications(
                start, end):
            indemnification.apply_underwriting_reduction = \
                self.indemnifications[-1].apply_underwriting_reduction
            res.append(indemnification)
        return res


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

    def _get_detailed_status(self):
        status = super(Indemnification, self)._get_detailed_status()
        blocking = self.service.get_underwriting_blocking_decision(
            self.start_date, self.end_date)
        if not blocking:
            return status
        return status + ' - ' + blocking.rec_name


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

    def period_definitions_dates(self):
        dates = super(IndemnificationDefinition,
            self).period_definitions_dates()
        blocking = self.service.get_underwriting_blocking_decision(
            self.start_date, self.end_date)
        if not blocking:
            return dates
        return dates + [blocking.effective_decision_date]


class CreateIndemnification(model.FunctionalErrorMixIn):
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

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
            service.raise_user_warning(
                'blocked_indemnification_split_warning_%s' %
                str(service.id), 'blocked_indemnifications_split', (
                    {'decision_date': coog_string.translate_value(to_warn,
                            'effective_decision_date')}))
        return result

    def update_indemnification(self, indemnification):
        super(CreateIndemnification, self).update_indemnification(
            indemnification)
        if not self.definition.underwriting_reduction:
            indemnification.apply_underwriting_reduction = False
        else:
            indemnification.apply_underwriting_reduction = \
                self.definition.accept_underwriting_reduction

    def transition_calculate(self):
        input_end_date = self.definition.end_date
        Pool().get('claim').activate_underwritings_if_needed(
            [self.definition.service.claim], input_end_date)
        return super(CreateIndemnification, self).transition_calculate()
