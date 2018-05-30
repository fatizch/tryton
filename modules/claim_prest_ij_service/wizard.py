# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction, StateTransition


__all__ = [
    'FindPartySubscription',
    'RelaunchPartySubscription',
    ]


class FindPartySubscription(Wizard):
    'Fnd Party Subscription'
    __name__ = 'party_subscription.find'

    start = StateAction(
        'claim_prest_ij_service.act_claim_ij_subscription_relate_form')

    @classmethod
    def __setup__(cls):
        super(FindPartySubscription, cls).__setup__()
        cls._error_messages.update({
                'benefit_no_ij_service': 'The benefit(s) configuration(s) '
                'associated to the party "%(party)s" does not handle IJ '
                'service'
                })

    def _benefit_handle_prest_ij(self, subscriber):
        return any(o.benefits[0].prest_ij
               for c in subscriber.contracts
               for o in c.covered_element_options
               if o.benefits)

    def do_start(self, action):
        pool = Pool()
        Party = pool.get('party.party')
        ActWindow = pool.get('ir.action.act_window')
        Action = pool.get('ir.action')
        possible_actions = ActWindow.search([
                ('res_model', '=', 'claim.ij.subscription')])
        good_action = possible_actions[0]
        good_values = Action.get_action_values(
            'ir.action.act_window', [good_action.id])
        good_values[0]['views'] = [
            view for view in good_values[0]['views'] if view[1] == 'form']
        party_id = Transaction().context.get('active_id')
        party = Party(party_id)
        Subscription = pool.get('claim.ij.subscription')
        subscription = Subscription.search([('party', '=', party_id)], limit=1)
        if not subscription:
            if self._benefit_handle_prest_ij(party):
                subscription, = Subscription.create([{'party': party_id}])
            else:
                self.raise_user_error('benefit_no_ij_service', {
                        'party': party.full_name
                        })
        else:
            subscription = subscription[0]
        return good_values[0], {'res_id': subscription.id}


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
