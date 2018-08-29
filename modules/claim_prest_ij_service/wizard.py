# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from collections import defaultdict

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.server_context import ServerContext
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction, StateTransition, StateView, \
    Button

from trytond.modules.coog_core import model, fields, utils, coog_string, \
    coog_date


__all__ = [
    'FindPartySubscription',
    'CoveredPersonIjSubscriptionSelectDate',
    'CreateCoveredPersonIjSubscription',
    'RelaunchPartySubscription',
    'TreatIjPeriod',
    'TreatIjPeriodSelect',
    'TreatIjPeriodSelectLine',
    'CreateIndemnification',
    'IndemnificationDefinition',
    ]


class FindPartySubscription(Wizard):
    'Find Party Subscription'
    __name__ = 'party_subscription.find'

    start = StateAction(
        'claim_prest_ij_service.act_claim_ij_subscription_relate_form')

    @classmethod
    def __setup__(cls):
        super(FindPartySubscription, cls).__setup__()
        cls._error_messages.update({
                'no_prest_ij_subscription': 'The selection does not have '
                'related subscription. %(selection)s',
                })

    def do_start(self, action):
        pool = Pool()
        model = Transaction().context.get('active_model')
        Model = pool.get(model)
        ActWindow = pool.get('ir.action.act_window')
        Action = pool.get('ir.action')
        possible_actions = ActWindow.search([
                ('res_model', '=', 'claim.ij.subscription')])
        good_action = possible_actions[0]
        selection_id = Transaction().context.get('active_id')
        selection = Model(selection_id)
        Subscription = pool.get('claim.ij.subscription')
        if model == 'party.party':
            covered = selection
            domain = [
                ('ssn', '=', None if not covered.is_person
                    else covered.ssn)]
            if not covered.is_person:
                domain.append(('siren', '=', covered.siren))
        elif model == 'claim':
            if not selection.losses or not selection.losses[0].services:
                self.raise_user_error('no_prest_ij_subscription', {
                        'selection': selection.rec_name
                        })
            covered = selection.losses[0].covered_person
            domain = [
                ('ssn', '=', covered.ssn),
                ('siren', '=',
                    selection.losses[0].services[0].contract.subscriber.siren),
                ]
        else:
            assert False, 'Model must be a claim or a party'
        subscriptions = Subscription.search(domain)
        if not subscriptions:
            self.raise_user_error('no_prest_ij_subscription', {
                    'selection': selection.rec_name
                    })
        good_values = Action.get_action_values(
            'ir.action.act_window', [good_action.id])
        good_values[0]['views'] = [
            view for view in good_values[0]['views'] if view[1] in
            (['form'] if len(subscriptions) == 1 else ['tree'])]
        return good_values[0], {
            'res_id': subscriptions[0].id,
            'res_ids': [x.id for x in subscriptions],
            }


class CoveredPersonIjSubscriptionSelectDate(model.CoogView):
    'Covered Person IJ Susbscription Select Date'
    __name__ = 'covered_person.ij_subscription_create.select_date'

    period_start = fields.Date('Period Start', required=True)
    period_end = fields.Date('Period End')
    retro_date = fields.Date('Retroactive Date', required=True)
    subscription = fields.Many2One('claim.ij.subscription', 'Subscription',
        required=True, readonly=True)


class CreateCoveredPersonIjSubscription(Wizard):
    'Create Covered Person Ij Subscription'
    __name__ = 'covered_person.subscription.create_request'

    start_state = 'select_date'
    select_date = StateView(
        'covered_person.ij_subscription_create.select_date',
        'claim_prest_ij_service.create_subscription_select_date_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_request', 'tryton-go-next', default=True),
            ])
    create_request = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CreateCoveredPersonIjSubscription, cls).__setup__()
        cls._error_messages.update({
                'already_manual':
                'There is already a manual period',
                'no_company_confirmed':
                'There are no IJ Subscription confirmed for '
                'this person\'s companies',
                'not_covered': 'This person is not covered at this date',
                'date_anterior_to_max_loss_end': 'The chosen date is anterior'
                ' to the end of the last short term disability which is: [%s]',
                })

    def default_select_date(self, name):
        context = Transaction().context
        assert context.get('active_model') == 'claim.ij.subscription'
        subscription = context.get('active_id')
        if not subscription:
            return 'end'
        return {'subscription': subscription}

    def transition_create_request(self):
        pool = Pool()
        Request = pool.get('claim.ij.subscription_request')
        Group = pool.get('claim.ij.subscription_request.group')
        Loss = Pool().get('claim.loss')
        Contract = Pool().get('contract')
        Subscription = pool.get('claim.ij.subscription')
        CoveredElement = pool.get('contract.covered_element')

        subscription = self.select_date.subscription
        if any([x.method == 'manual' and x.state == 'unprocessed'
                for x in subscription.requests]):
            self.raise_user_error('already_manual')

        person = subscription.parties[0]

        company_subs = Subscription.search([
                ('siren', '=', subscription.siren),
                ('ssn', '=', None),
                ('state', '=', 'declaration_confirmed'),
                ('activated', '=', True),
                ])
        if not company_subs:
            self.raise_user_error('no_company_confirmed')

        date = self.select_date.period_start

        siren_contracts = Contract.search([
                'OR', [
                    [('end_date', '<=', date)],
                    [('end_date', '=', None)]],
                ('subscriber', 'in', [x.parties[0].id for x in company_subs])])
        parent_covereds = CoveredElement.search(
            [('contract', 'in', [x.id for x in siren_contracts])])
        person_covered = CoveredElement.search(
            [('parent', 'in', [x.id for x in parent_covereds]),
                ('party', '=', person.id)])

        if not person_covered:
            self.raise_user_error('not_covered')

        losses = [x for x in
            Loss.search([
                    ('covered_person', '=', person.id),
                    ('loss_desc.loss_kind', '=', 'std')])]

        if losses:
            max_end = max(x.end_date or datetime.date.min for x in losses)
            if date < max_end:
                Date = Pool().get('ir.date')
                self.raise_user_warning('date_anterior_to_max_loss_end_%s'
                    % str(subscription), 'date_anterior_to_max_loss_end',
                    Date.date_as_string(max_end))

        Request.create([{
                    'date': utils.today(),
                    'period_start': self.select_date.period_start,
                    'period_end': self.select_date.period_end,
                    'retro_date': self.select_date.retro_date,
                    'subscription': subscription,
                    'method': 'manual',
                    'period_identification':
                    Group.generate_identification(kind='period'),
                    'operation': 'cre',
                    }])
        return 'end'


class RelaunchPartySubscription(Wizard):
    'Relanch Party Subscription'
    __name__ = 'party_subscription.relaunch'

    start_state = 'relaunch_subscription'
    relaunch_subscription = StateTransition()

    def transition_relaunch_subscription(self):
        context = Transaction().context
        assert context.get('active_model') == 'claim.ij.subscription'
        Subscription = Pool().get('claim.ij.subscription')
        selection = Subscription.browse(context.get('active_ids'))
        to_write_per_state = defaultdict(list)
        for sub in selection:
            err_requests = [x for x in sub.requests if x.state == 'failed']
            if not err_requests:
                continue
            last_err = err_requests[0]
            if last_err.operation == 'cre':
                to_write_per_state['undeclared'].append(sub)
            else:
                to_write_per_state['declaration_confirmed'].append(sub)
        to_write = []
        for state, subscriptions in to_write_per_state.items():
            to_write.extend([subscriptions, {'state': state}])
        if to_write:
            Subscription.write(*to_write)
        return 'end'


class TreatIjPeriod(Wizard):
    'Treat IJ Period'

    __name__ = 'claim.ij.period.treat'

    start_state = 'check_context'

    check_context = StateTransition()
    to_treat = StateView('claim.ij.period.treat.select',
        'claim_prest_ij_service.period_to_treat_select_view_form', [
            Button('Exit', 'end', 'tryton-cancel'),
            Button('Treat Manually', 'manual', 'tryton-refresh',
                states={'readonly': ~Eval('manual_treatment')}),
            Button('Treat', 'automatic', 'tryton-go-next',
                states={'readonly': ~Eval('automatic_treatment')}),
            Button('Cancel Indemnifications', 'cancel', 'tryton-delete',
                states={'readonly': ~Eval('cancellation')}),
            ])
    manual = StateTransition()
    automatic = StateAction(
        'claim_indemnification.act_create_indemnification_wizard')
    cancel = StateTransition()

    @classmethod
    def __setup__(cls):
        super(TreatIjPeriod, cls).__setup__()
        cls._error_messages.update({
                'nothing_to_do': 'All periods are already treated, '
                'nothing to do',
                'inconsistent_daily_amount': 'Selected periods have different '
                'daily amounts',
                'changing_daily_amount': 'Daily amount is changing, going '
                'from %(prev)s to %(new)s',
                'no_claim_found': 'Could not find a matching claim, one may '
                'have to be created',
                'no_service_mixin': 'Cannot treat periods for different '
                'services',
                'period_hole': 'No indemnification found between %(last_end)s '
                ' and %(new_start)s',
                'non_matching_types': 'Multiple types found when trying to '
                'treat: %(type1)s and %(type2)s',
                })

    def transition_check_context(self):
        pool = Pool()
        context = Transaction().context
        if context.get('active_model') == 'claim.ij.subscription':
            instance = pool.get('claim.ij.subscription')(context['active_id'])
            if not instance.periods_to_treat:
                self.raise_user_error('nothing_to_do')
            if all(not x.claim for x in instance.periods_to_treat):
                self.raise_user_error('no_claim_found')
        elif context.get('active_model') == 'claim.ij.period':
            instances = pool.get('claim.ij.period').browse(
                context['active_ids'])
            if not any(x for x in instances if x.state != 'treated'):
                self.raise_user_error('nothing_to_do')
            if all(not x.claim for x in instances):
                self.raise_user_error('no_claim_found')
        else:
            raise NotImplementedError

        return 'to_treat'

    def default_to_treat(self, name):
        pool = Pool()
        context = Transaction().context
        if context['active_model'] == 'claim.ij.subscription':
            periods = pool.get('claim.ij.subscription')(
                Transaction().context['active_id']).periods_to_treat
        elif context['active_model'] == 'claim.ij.period':
            periods = pool.get('claim.ij.period').browse(
                context['active_ids'])
        else:
            raise NotImplementedError
        # order based on start_date else automatic algorithme will not work
        periods = sorted(periods, key=lambda x: (x.start_date, x.create_date),
            reverse=True)
        dictionarize_fields = {
            'claim.ij.period': [
                'sign', 'period_kind', 'start_date', 'end_date', 'main_kind',
                'number_of_days', 'indemnification_amount', 'taxes_amount',
                'total_amount', 'beneficiary_kind', 'accounting_date', 'state',
                'automatic_action', 'lines', 'currency_symbol', 'id',
                'total_per_day_amount'],
            'claim.ij.period.line': ['kind', 'number_of_days', 'amount',
                'total_amount', 'currency_symbol'],
            }

        values = [model.dictionarize(x, dictionarize_fields,
                set_rec_names=True) for x in periods]

        for value in values:
            value['selected'] = False
            value['prev_selected'] = False
            value['period_id'] = value.pop('id')

        return {'values': values, 'manual_treatment': False}

    def transition_manual(self):
        assert self.to_treat.manual_treatment

        Period = Pool().get('claim.ij.period')
        selected = Period.browse(
            [x.period_id for x in self.to_treat.values if x.selected])

        Period.mark_as_treated(selected)
        if len(selected) == len(self.to_treat.values):
            return 'end'
        return 'to_treat'

    def do_automatic(self, action):
        assert self.to_treat.manual_treatment
        Period = Pool().get('claim.ij.period')
        selected = Period.browse(
            [x.period_id for x in self.to_treat.values if x.selected])

        assert all(x.state != 'treated' and x.service for x in selected)
        amounts = {x.total_per_day_amount
            for x in selected if x.total_per_day_amount}
        if len(amounts) > 1:
            self.raise_user_warning('inconsistent_daily_amount',
                'inconsistent_daily_amount')

        if len({x.service.id for x in selected}) != 1:
            self.raise_user_error('no_service_mixin')
        service = selected[0].service

        date = min(x.start_date for x in selected)
        if (service.paid_until_date and
                coog_date.add_day(service.paid_until_date, 1) < date):
            self.raise_user_error('period_hole', {
                    'last_end': coog_string.translate_value(service,
                        'paid_until_date'),
                    'new_start': coog_string.translate_value(selected[-1],
                        'start_date'),
                    })
        try:
            cur_ijss_value = service.find_extra_data_value('ijss', date=date)
        except KeyError:
            cur_ijss_value = None

        new_ijss_value = max([x for x in amounts if x] or [None])
        if (new_ijss_value and cur_ijss_value and
                cur_ijss_value != new_ijss_value):
            self.raise_user_warning('changing_daily_amount_%s' % str(date),
                'changing_daily_amount', {
                    'prev': str(cur_ijss_value), 'new': str(new_ijss_value),
                    })

        if service.loss.event_desc:
            event_desc = service.loss.event_desc
            types = {event_desc.prest_ij_type} | {
                x.period_kind for x in selected}
            if len(types) > 1:
                self.raise_user_error('non_matching_types', {
                        'type1': coog_string.translate_value(event_desc,
                            'prest_ij_type'),
                        'type2': coog_string.translate_value(
                            [x for x in selected if x.period_kind !=
                                event_desc.prest_ij_type][0], 'period_kind'),
                        })

        prev_end = None
        for start, end in sorted(
                {(x.start_date, x.end_date) for x in selected}):
            if prev_end is not None:
                if not end:
                    continue
                if start < prev_end:
                    continue
                if start > coog_date.add_day(prev_end, 1):
                    self.raise_user_error('period_hole', {
                            'last_end': coog_string.translate_value(
                                [x for x in selected if x.end_date ==
                                    prev_end][0], 'end_date'),
                            'new_start': coog_string.translate_value(
                                [x for x in selected if x.start_date ==
                                    start][0], 'end_date'),
                            })
                prev_end = end if not prev_end else max(end, prev_end)
            else:
                prev_end = end
        return action, {
            'extra_context': {
                'prestij_periods': [x.id for x in selected],
                }}

    def transition_cancel(self):
        pool = Pool()
        Service = pool.get('claim.service')
        Indemnification = pool.get('claim.indemnification')
        Period = pool.get('claim.ij.period')
        periods = Period.browse(
            [x.period_id for x in self.to_treat.values if x.selected])
        assert all(x.automatic_action == 'cancel_period' for x in periods)
        assert len({x.service.id for x in periods}) == 1

        service = periods[0].service
        indemnifications = list(service.indemnifications)
        Period.add_to_indemnifications(periods, indemnifications)
        Indemnification.save(indemnifications)

        Service.cancel_indemnification([service],
            min(x.start_date for x in periods),
            max(x.end_date for x in periods))

        return 'end'


class TreatIjPeriodSelect(model.CoogView):
    'Treat Ij Period Select'

    __name__ = 'claim.ij.period.treat.select'

    values = fields.One2Many('claim.ij.period.treat.select.line', None,
        'Periods to treat', readonly=True)
    manual_treatment = fields.Boolean('Manual Treatment')
    automatic_treatment = fields.Boolean('Automatic Treatment')
    cancellation = fields.Boolean('Cancellation')

    @fields.depends('values')
    def on_change_values(self):
        lines, changed, selected = [], None, []
        for idx, line in enumerate(self.values):
            if line.selected != line.prev_selected:
                changed = idx
                break

        for idx, line in enumerate(self.values):
            if changed is not None and idx > changed:
                line.selected = True
            elif changed is not None and idx < changed:
                line.selected = False
            lines.append(line)
            line.prev_selected = line.selected
            if line.selected:
                selected.append(line)
        self.values = lines
        self.manual_treatment = bool(selected)
        self.cancellation = bool(all(x.automatic_action == 'cancel_period'
                for x in selected) and selected)
        self.automatic_treatment = bool(any(x.automatic_action == 'new_period')
                for x in selected)


class TreatIjPeriodSelectLine(model.view_only('claim.ij.period')):
    'Treat Ij Period Lines'

    __name__ = 'claim.ij.period.treat.select.line'

    selected = fields.Boolean('Selected')
    prev_selected = fields.Boolean('Previously Selected')
    period_id = fields.Integer('Period Id')


class CreateIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    @classmethod
    def __setup__(cls):
        super(CreateIndemnification, cls).__setup__()
        button = None
        for btn in cls.definition.buttons:
            if btn.state == 'select_service':
                button = btn
                break
        if button:
            states = button.states
            new_invisible = Bool(Eval('prestij_periods'))
            if 'invisible' in states:
                states &= new_invisible
            else:
                states['invisible'] = new_invisible

    def transition_select_service_needed(self):
        if 'prestij_periods' not in Transaction().context:
            return super(CreateIndemnification,
                self).transition_select_service_needed()

        periods = Pool().get('claim.ij.period').browse(
            Transaction().context.get('prestij_periods'))

        assert periods[0].service

        service = periods[0].service
        self.definition.service = service
        self.definition.start_date = min(x.start_date for x in periods)
        self.definition.end_date = max(x.end_date for x in periods)
        return 'definition'

    def transition_calculate(self):
        # We need to create this list to hold the periods linked to deleted
        # indemnifications, so that they can be linked to other created periods
        cancelled = []
        with ServerContext().set_context(deleted_prestij_periods=cancelled):
            return super(CreateIndemnification, self).transition_calculate()

    def init_indemnifications(self):
        indemnifications = super(CreateIndemnification,
            self).init_indemnifications()

        Period = Pool().get('claim.ij.period')
        periods = {}
        if 'prestij_periods' in Transaction().context:
            periods.update({x.id: x
                    for x in Period.browse(Transaction().context.get(
                        'prestij_periods'))})
        cancelled = ServerContext().get('deleted_prestij_periods', None)
        if cancelled is not None:
            periods.update({x.id: x for x in cancelled})

        Period.add_to_indemnifications(periods.values(), indemnifications)

        return indemnifications


class IndemnificationDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    prestij_periods = fields.Many2Many('claim.ij.period', None, None,
        'Prest IJ Periods', states={'invisible': ~Eval('prestij_periods')})

    @fields.depends('extra_data', 'prestij_periods')
    def on_change_service(self):
        super(IndemnificationDefinition, self).on_change_service()
        if 'prestij_periods' not in Transaction().context:
            return

        periods = Pool().get('claim.ij.period').browse(
            Transaction().context.get('prestij_periods'))

        assert periods[0].service and (periods[0].state != 'treated'
            or all(x.indemnification and x.indemnification.status ==
                'calculated' for x in periods))

        self.start_date = min(x.start_date for x in periods)
        self.end_date = max(x.end_date for x in periods)
        if 'ijss' in self.extra_data:
            new_data = dict(self.extra_data)
            new_data['ijss'] = periods[0].total_per_day_amount
            self.extra_data = new_data
        self.prestij_periods = periods

    def period_definitions_dates(self):
        result = super(IndemnificationDefinition,
            self).period_definitions_dates()
        if getattr(self, 'prestij_periods', None):
            result += [x.start_date for x in self.prestij_periods[:-1]]
        return result
