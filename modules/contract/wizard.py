from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.wizard import StateTransition, StateView, Button
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, fields

__all__ = [
    'OptionSubscription',
    'OptionsDisplayer',
    'WizardOption'
    ]


class OptionSubscription(model.CoopWizard):
    'Option Subscription'

    __name__ = 'contract.wizard.option_subscription'

    options_displayer = StateView(
        'contract.wizard.option_subscription.options_displayer',
        'contract.options_displayer_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'update_options', 'tryton-go-next'),
            ])
    update_options = StateTransition()
    start_state = 'options_displayer'

    def default_options_displayer(self, values):
        Contract = Pool().get('contract.contract')
        contract = Contract(Transaction().context.get('active_id'))
        options = []
        for coverage in contract.offered.coverages:
            options.append({
                    'is_selected': (
                        coverage.subscription_behaviour != 'optional'),
                    'coverage_behaviour': coverage.subscription_behaviour,
                    'coverage': coverage.id
                    })
        return {
            'contract': contract.id,
            'options': options
            }

    def subscribe_option(self, coverage):
        Option = Pool().get('contract.subscribed_option')
        option = Option()
        option.init_from_offered(coverage,
            self.options_displayer.contract.start_date)
        self.options_displayer.contract.options.append(option)
        return option

    def transition_update_options(self):
        Option = Pool().get('contract.subscribed_option')
        to_delete = []
        to_subscribe = [x.coverage for x in self.options_displayer.options
            if x.is_selected]
        contract = self.options_displayer.contract
        if contract.options:
            contract.options = list(contract.options)
        for option in contract.options:
            if option.offered in to_subscribe:
                to_subscribe.remove(option.offered)
            else:
                to_delete.append(option)
        for coverage in to_subscribe:
            self.subscribe_option(coverage)
        contract.options = list(contract.options)
        contract.options[:] = [x for x in contract.options
            if not x in to_delete]
        if to_delete:
            Option.delete(to_delete)
        contract.save()
        return 'end'


class OptionsDisplayer(model.CoopView):
    'Select Covered Element'

    __name__ = 'contract.wizard.option_subscription.options_displayer'

    contract = fields.Many2One('contract.contract', 'Contract')
    options = fields.One2Many(
        'contract.wizard.option_subscription.options_displayer.option',
        None, 'Options')


class WizardOption(model.CoopView):
    'Option'

    __name__ = 'contract.wizard.option_subscription.options_displayer.option'

    coverage = fields.Many2One('offered.coverage', 'Coverage')
    coverage_behaviour = fields.Function(
        fields.Char('Behaviour'), 'get_coverage_behaviour')
    is_selected = fields.Boolean('Selected?', states={
            'readonly': Eval('coverage_behaviour') == 'mandatory'})

    def get_coverage_behaviour(self, name):
        return self.coverage.subscription_behaviour if self.coverage else ''
