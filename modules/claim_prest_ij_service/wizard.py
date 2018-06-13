# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from collections import defaultdict

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction, StateTransition, StateView, \
    Button

from trytond.modules.coog_core import model, fields, utils

__all__ = [
    'FindPartySubscription',
    'CoveredPersonIjSubscriptionSelectDate',
    'CreateCoveredPersonIjSubscription',
    'RelaunchPartySubscription',
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
            Button('Create', 'create_request', 'tryton-next', default=True),
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
