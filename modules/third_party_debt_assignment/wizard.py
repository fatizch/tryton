# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby

from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.pool import Pool
from trytond.i18n import gettext
from trytond.transaction import Transaction
from trytond.model.exceptions import ValidationError

from trytond.modules.coog_core import model

__all__ = [
    'DebtAssignmentCreateRequests',
    'DebtAssignmentRequestsChangeState',
    ]


class DebtAssignmentCreateRequestsView(model.CoogView):
    'Debt Assignment Create Requests View'
    __name__ = 'debt_assignment_request.create_requests.view'


class DebtAssignmentCreateRequests(Wizard):
    'Debt Assignment Create Requests'
    __name__ = 'debt_assignment_request.create_requests'

    start_state = 'start'
    start = StateView(
        'debt_assignment_request.create_requests.view',
        'third_party_debt_assignment.'
        'debt_assignment_request_creation_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create requests', 'create_requests',
                'tryton-go-next', default=True), ])
    create_requests = StateTransition()

    @classmethod
    def get_third_party(cls, date, contracts):
        for contract in contracts:
            for option in contract.get_all_options():
                if (option.coverage.allow_third_party_assignment and
                        option.is_active_at_date(date)):
                    return option.coverage.insurer.party

    def transition_create_requests(self):
        pool = Pool()
        DebtAssignmentRequest = pool.get('debt_assignment_request')
        DunningLevel = pool.get('account.dunning.level')
        level_names = [level.name for level in DunningLevel.search([
            ('ask_for_third_party_take_care', '=', True)])]
        en_level_names = [fr_name.src for fr_name in
            pool.get('ir.translation').search([('value', 'in', level_names)])]
        contracts = pool.get('contract').search([('status', '=', 'active'),
            ('dunning_status', 'in', en_level_names)])
        debt_assignment_requests = []
        sorted_contracts = sorted(contracts, key=lambda x: x.subscriber)
        for subscriber, contracts in groupby(sorted_contracts,
                lambda x: x.subscriber):
            invoices = []
            contracts = list(contracts)
            for contract in contracts:
                invoices.extend([invoice for invoice in
                    contract.account_invoices if invoice.state == 'posted'])
            invoices_ids = [i.id for i in invoices]
            min_invoice_date = min(
                [i.start or i.invoice_date for i in invoices])
            third_party = self.__class__.get_third_party(min_invoice_date,
                contracts)
            if not third_party:
                continue

            exist = False
            request_to_add = None
            request_invoices = []

            for request in DebtAssignmentRequest.search(
                    [('invoices', 'in', invoices_ids)]):
                if {x.id for x in request.invoices} == set(invoices_ids):
                    exist = True
                    break
                else:
                    request_invoices.extend([x.id for x in request.invoices])
                    if request.state == 'draft':
                        request_to_add = request
            left_invoices = list(filter(
                lambda x: x not in request_invoices, invoices_ids))
            if request_to_add:
                exist = True
                request_to_add.invoices = list(request_to_add.invoices) + \
                    left_invoices
                debt_assignment_requests.append(request_to_add)

            if invoices_ids and third_party and not exist:
                debt_assignment_request = DebtAssignmentRequest(
                    party=subscriber,
                    third_party=third_party,
                    invoices=left_invoices or invoices_ids)
                debt_assignment_requests.append(debt_assignment_request)
        if debt_assignment_requests:
            DebtAssignmentRequest.save(debt_assignment_requests)
        return 'end'


class DebtAssignmentRequestsChangeState(Wizard):
    'Debt Assignment Requests Change State'

    __name__ = 'debt_assignment_request.change_state'

    start_state = 'start'
    start = StateTransition()

    def transition_start(self):
        pool = Pool()
        DebtAssignment = pool.get('debt_assignment_request')
        ctx = Transaction().context
        requests = DebtAssignment.browse(ctx.get('active_ids'))
        action = pool.get('ir.action')(ctx.get('action_id'))
        action_name = pool.get('ir.translation').search([
            ('value', '=', action.name),
            ('name', '=', 'ir.action,name')])[0].src
        allowed_op = self._get_allowed_operations(requests[0].state)
        if not allowed_op or action_name not in allowed_op:
            raise ValidationError(gettext(
                'third_party_debt_assignment.msg_disallowed_operation'))
        getattr(DebtAssignment, action_name.lower())(requests)
        return 'end'

    @staticmethod
    def _get_allowed_operations(state):
        allowed_op = {
            'draft': ['Transmit'],
            'transmitted': ['Draft', 'Refuse', 'Study'],
            'in_study': ['Refuse', 'Accept'],
            'accepted': ['Pay', 'Refuse']
            }
        return allowed_op.get(state)
