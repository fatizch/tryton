# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import Pool
from trytond.pyson import Eval, Len, If, PYSONEncoder
from trytond.wizard import StateTransition, StateView, Button, StateAction
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields, coog_string, utils
from trytond.modules.offered import offered

__all__ = [
    'OptionSubscription',
    'PackageSelection',
    'OptionsDisplayer',
    'WizardOption',
    'ContractActivateConfirm',
    'ContractActivate',
    'ContractSelectDeclineReason',
    'ContractDecline',
    'ContractStopSelectContracts',
    'ContractStop',
    'ContractReactivateCheck',
    'ContractReactivate',
    'RelatedAttachments',
    ]


class OptionSubscription(model.CoogWizard):
    'Option Subscription'

    __name__ = 'contract.wizard.option_subscription'

    start = StateTransition()
    select_package = StateView(
        'contract.wizard.option_subscription.select_package',
        'contract.select_package_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'options_displayer', 'tryton-go-next',
                default=True),
            ])
    options_displayer = StateView(
        'contract.wizard.option_subscription.options_displayer',
        'contract.options_displayer_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'update_options', 'tryton-go-next', default=True),
            ])
    update_options = StateTransition()

    def get_contract(self):
        if Transaction().context.get('active_model') == 'contract':
            contract_id = Transaction().context.get('active_id')
        else:
            contract_id = Transaction().context.get('contract')
        if not contract_id:
            return
        Contract = Pool().get('contract')
        return Contract(contract_id)

    def default_select_package(self, values):
        contract = self.get_contract()
        if not contract:
            return {}
        return {
            'possible_packages': [x.id for x in contract.product.packages],
            }

    def default_options_displayer(self, values):
        contract = self.get_contract()
        if not contract:
            return {}
        package = getattr(self.select_package, 'package', None)
        return {
            'contract': contract.id,
            'package': package.id if package else None,
            }

    def add_remove_options(self, options, lines):
        Option = Pool().get('contract.option')
        to_subscribe = set([x.coverage for x in lines if x.is_selected])
        to_delete = [x for x in options if x.coverage not in to_subscribe]
        updated_options = [x for x in options if x not in to_delete]
        Option.delete(to_delete)

        subscribed = set([x.coverage for x in updated_options])
        for line in lines:
            if not line.is_selected or line.coverage in subscribed:
                continue
            option = Option.new_option_from_coverage(line.coverage,
                self.options_displayer.contract.product,
                self.options_displayer.contract.start_date)
            line.option = option
            updated_options.append(option)
        return updated_options

    def transition_start(self):
        Contract = Pool().get('contract')
        contract = Contract(Transaction().context.get('active_id'))
        if contract.product.packages:
            return 'select_package'
        else:
            return 'options_displayer'

    def transition_update_options(self):
        contract = self.options_displayer.contract
        contract.options = self.add_remove_options(
            list(getattr(contract, 'options', [])),
            self.options_displayer.options)
        contract.init_extra_data()
        contract.save()
        return 'end'


class PackageSelection(model.CoogView):
    'Select Package'

    __name__ = 'contract.wizard.option_subscription.select_package'

    package = fields.Many2One('offered.package', 'Package',
        domain=[('id', 'in', Eval('possible_packages'))],
        depends=['possible_packages'])
    possible_packages = fields.Many2Many('offered.package', None, None,
        'Possible Packages')


class OptionsDisplayer(model.CoogView):
    'Select Covered Element'

    __name__ = 'contract.wizard.option_subscription.options_displayer'

    contract = fields.Many2One('contract', 'Contract',
        states={'invisible': True}, ondelete='RESTRICT')
    options = fields.One2Many(
        'contract.wizard.option_subscription.options_displayer.option',
        'displayer', 'Options')
    package = fields.Many2One('offered.package', 'Package',
        states={'invisible': True})

    @fields.depends('contract', 'package', 'options')
    def on_change_contract(self):
        if not self.contract:
            return
        self.options = []
        self.update_options(self.contract.options, [x.coverage
            for x in self.contract.product.ordered_coverages])

    @fields.depends('options', 'package')
    def on_change_options(self):
        if self.package:
            return
        selected = [elem for elem in self.options
            if (elem.is_selected and getattr(elem, 'coverage', None))]
        excluded = []
        required = []
        for x in selected:
            excluded += x.coverage.options_excluded
            required += x.coverage.options_required
        for x in [x for x in self.options if getattr(x, 'coverage', None)]:
            if x.coverage in excluded:
                is_selected = False
                selection = 'automatic'
            elif x.coverage in required:
                is_selected = True
                selection = 'automatic'
            elif x.selection == 'automatic':
                is_selected = False
                selection = 'manual'
            elif x.selection != 'mandatory':
                is_selected = x.is_selected
                selection = 'manual'
            else:
                continue
            x.is_selected = is_selected
            x.selection = selection
        self.options = list(self.options)

    def update_options(self, initial_options, coverages):
        Displayer = Pool().get(
            'contract.wizard.option_subscription.options_displayer.option')
        options = []
        excluded = []
        for option in initial_options:
            excluded += option.coverage.options_excluded
        for coverage in coverages:
            existing_option = None
            for option in initial_options:
                if option.coverage == coverage:
                    existing_option = option
                    break
            selection = 'manual'
            if coverage.subscription_behaviour == 'mandatory':
                selection = 'mandatory'
            elif not self.package and coverage in excluded:
                selection = 'automatic'
            option = Displayer(
                name='%s [%s]' % (coverage.rec_name,
                    coog_string.translate_value(coverage,
                        'subscription_behaviour')),
                is_selected=((not self.package and (bool(existing_option) or
                            coverage.subscription_behaviour != 'optional'))
                    or (self.package and coverage in self.package.options)),
                coverage_behaviour=coverage.subscription_behaviour,
                coverage=coverage, selection=selection, option=existing_option,
                )
            options.append(option)
            options += self.update_sub_options(option)
        self.options = options

    def update_sub_options(self, new_option):
        return []


class WizardOption(model.CoogView):
    'Option'

    __name__ = 'contract.wizard.option_subscription.options_displayer.option'

    displayer = fields.Many2One(
        'contract.wizard.option_subscription.options_displayer', 'Displayer')
    name = fields.Function(
        fields.Char('Name'),
        'on_change_with_name')
    coverage = fields.Many2One('offered.option.description',
        'Option Description', readonly=True)
    coverage_behaviour = fields.Selection(offered.SUBSCRIPTION_BEHAVIOUR,
        'Subscription Behaviour', sort=False, readonly=True)
    is_selected = fields.Boolean('Selected?', states={'readonly':
            Eval('selection').in_(['automatic', 'mandatory'])})
    selection = fields.Selection([
            ('manual', 'Manual'),
            ('automatic', 'Automatic'),
            ('mandatory', 'Mandatory'),
            ], 'Selection')
    option = fields.Many2One('contract.option', 'Option')

    @classmethod
    def view_attributes(cls):
        return super(WizardOption, cls).view_attributes() + [
            ('/tree', 'colors', If(~Eval('loan'), 'black', 'blue')),
            ]

    @fields.depends('coverage', 'coverage_behaviour')
    def on_change_with_name(self, name=None):
        if self.coverage:
            return '%s [%s]' % (self.coverage.rec_name,
                coog_string.translate_value(self, 'coverage_behaviour'))

    @staticmethod
    def default_selection():
        return 'manual'


class ContractActivateConfirm(model.CoogView):
    'Confirm Contract Activation View'
    __name__ = 'contract.activate.confirm'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    termination_reason = fields.Many2One('contract.sub_status',
        'Current termination reason', readonly=True,
        states={'invisible': ~Eval('termination_reason')})
    clear_termination_reason = fields.Boolean('Clear termination reason',
        states={'invisible': ~Eval('termination_reason')},
        help='If true, the current termination reason will be erased after '
        'reactivation', depends=['termination_reason'])


class ContractActivate(model.CoogWizard):
    'Activate Contract Wizard'

    __name__ = 'contract.activate'
    start_state = 'check_status'
    check_status = StateTransition()
    confirm = StateView(
        'contract.activate.confirm',
        'contract.activate_confirm_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next', default=True),
            ])
    apply = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ContractActivate, cls).__setup__()
        cls._error_messages.update({
                'not_quote_hold': 'You cannot activate a contract '
                'that is not in quote or hold status !',
                })

    def default_confirm(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        active_id = Transaction().context.get('active_id')
        selected_contract = Contract(active_id)
        termination_reason = selected_contract.termination_reason
        return {
            'contract': selected_contract.id,
            'termination_reason': termination_reason.id
            if termination_reason else None,
            }

    def transition_check_status(self):
        pool = Pool()
        Contract = pool.get('contract')
        active_id = Transaction().context.get('active_id')
        selected_contract = Contract(active_id)
        if (selected_contract.status != 'quote' and
                selected_contract.status != 'hold'):
            self.raise_user_error('not_quote_hold')
            return 'end'
        else:
            return 'confirm'

    def transition_apply(self):
        pool = Pool()
        Contract = pool.get('contract')
        active_id = Transaction().context.get('active_id')
        selected_contract = Contract(active_id)
        selected_contract.activate_contract()
        if (self.confirm.termination_reason and
                self.confirm.clear_termination_reason):
            selected_contract.activation_history[-1].termination_reason = None
            selected_contract.activation_history[-1].save()
        return 'end'


class ContractSelectDeclineReason(model.CoogView):
    'Reason selector to decline contract'
    __name__ = 'contract.decline.select_reason'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    reason = fields.Many2One('contract.sub_status', 'Reason', required=True,
        domain=[('status', '=', 'declined')])


class ContractDecline(model.CoogWizard):
    'Decline Contract Wizard'

    __name__ = 'contract.decline'
    start_state = 'select_reason'
    select_reason = StateView(
        'contract.decline.select_reason',
        'contract.select_decline_reason_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next', default=True),
            ])
    apply = StateTransition()

    def default_select_reason(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        active_id = Transaction().context.get('active_id')
        selected_contract = Contract(active_id)
        return {
            'contract': selected_contract.id,
            }

    def transition_apply(self):
        pool = Pool()
        Contract = pool.get('contract')
        reason = self.select_reason.reason
        active_id = Transaction().context.get('active_id')
        selected_contract = Contract(active_id)
        Contract.decline_contract([selected_contract], reason)
        return 'end'


class ContractStopSelectContracts(model.CoogView):
    'Select Contract to stop'

    __name__ = 'contract.stop.select_contracts'

    status = fields.Selection([
            ('terminated', 'Terminated'),
            ('void', 'Void'),
            ], 'Status', required=True)
    at_date = fields.Date('At this date', states={
            'invisible': Eval('status') != 'terminated',
            'required': Eval('status') == 'terminated',
            }, depends=['status'])
    sub_status = fields.Many2One('contract.sub_status', 'Sub Status',
        domain=[('status', '=', Eval('status'))], depends=['status'],
        required=True)
    contracts = fields.Many2Many('contract', None, None, 'Contracts to stop',
        required=True, states={'invisible': Len(Eval('contracts', [])) >= 1})

    @classmethod
    def view_attributes(cls):
        return super(ContractStopSelectContracts, cls).view_attributes() + [(
                '/form/group[@id="warning_void"]',
                'states',
                {'invisible': Eval('status') != 'void'}
                )]


class ContractStop(model.CoogWizard):
    'Stop Contract'

    __name__ = 'contract.stop'

    start_state = 'select_contracts'
    select_contracts = StateView('contract.stop.select_contracts',
        'contract.stop_select_contracts_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'stop', 'tryton-go-next', default=True),
            ])
    stop = StateTransition()

    def default_select_contracts(self, name):
        if not Transaction().context.get('active_model') == 'contract':
            return {}
        return {
            'contracts': Transaction().context.get('active_ids', []),
            }

    def transition_stop(self):
        if self.select_contracts.status == 'void':
            Pool().get('contract').void(list(self.select_contracts.contracts),
                self.select_contracts.sub_status)
        elif self.select_contracts.status == 'terminated':
            Pool().get('contract').terminate(
                list(self.select_contracts.contracts),
                self.select_contracts.at_date,
                self.select_contracts.sub_status)
        return 'end'


class ContractReactivateCheck(model.CoogView):
    'Contract Reactivate Check'

    __name__ = 'contract.reactivate.check_contracts'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    previous_end_date = fields.Date('Previous End Date', readonly=True)
    new_end_date = fields.Date('New End Date', readonly=True)
    termination_reason = fields.Many2One('contract.sub_status',
        'Termination Reason', readonly=True)
    will_be_terminated = fields.Boolean('Will be terminated', readonly=True,
        states={'invisible': True})

    @classmethod
    def view_attributes(cls):
        return super(ContractReactivateCheck, cls).view_attributes() + [(
                '/form/group[@id="check_today"]',
                'states',
                {'invisible': ~Eval('will_be_terminated')}
                )]


class ContractReactivate(model.CoogWizard):
    'Reactivate Contract'

    __name__ = 'contract.reactivate'

    start_state = 'validate_reactivation'
    validate_reactivation = StateView('contract.reactivate.check_contracts',
        'contract.reactivate_check_contracts_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'reactivate', 'tryton-go-next', default=True),
            ])
    reactivate = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ContractReactivate, cls).__setup__()
        cls._error_messages.update({
                'need_contract': 'No contract found',
                })

    def default_validate_reactivation(self, name):
        Contract = Pool().get('contract')
        if Transaction().context.get('active_model') != 'contract':
            self.raise_user_error('need_contract')
        contract = Contract(Transaction().context.get('active_id'))
        new_end_date = contract.get_reactivation_end_date()
        result = {
            'contract': contract.id,
            'previous_end_date': contract.end_date,
            'new_end_date': new_end_date,
            'termination_reason': contract.sub_status.id,
            'will_be_terminated': ((new_end_date or datetime.date.max)
                < utils.today()),
            }
        return result

    def transition_reactivate(self):
        Pool().get('contract').reactivate(
            [self.validate_reactivation.contract])
        return 'end'


class RelatedAttachments(model.CoogWizard):
    'Related Attachments'

    __name__ = 'contract.related_attachments'

    start_state = 'display_attachments'
    display_attachments = StateAction('ir.act_attachment_form')

    def do_display_attachments(self, action):
        pool = Pool()
        Contract = pool.get('contract')
        Attachment = pool.get('ir.attachment')
        contract = Contract(Transaction().context.get('active_id'))
        res = Attachment.search([('resource', 'in',
                contract.related_attachments_resources())])
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode([('id', 'in',
                    [x.id for x in res])])
        return action, {}
