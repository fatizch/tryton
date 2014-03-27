from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.wizard import StateTransition, StateView, Button
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields
from trytond.modules.offered import offered

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
        if Transaction().context.get('active_model') == 'contract':
            contract_id = Transaction().context.get('active_id')
        else:
            contract_id = Transaction().context.get('contract')
        if not contract_id:
            return {}
        Contract = Pool().get('contract')
        contract = Contract(contract_id)
        options = []
        excluded = []
        for option in contract.options:
            excluded += option.coverage.options_excluded
        for coverage in [x.coverage
                for x in contract.product.ordered_coverages]:
            if coverage.subscription_behaviour == 'mandatory':
                selection = 'mandatory'
            elif coverage in excluded:
                selection = 'excluded'
            else:
                selection = ''
            options.append({
                    'is_selected': (coverage.id in [x.product.id
                            for x in contract.options]
                        or coverage.subscription_behaviour != 'optional'),
                    'coverage_behaviour': coverage.subscription_behaviour,
                    'coverage': coverage.id,
                    'selection': selection,
                    })
        return {
            'contract': contract.id,
            'options': options,
            }

    def subscribe_option(self, coverage):
        Option = Pool().get('contract.option')
        option = Option()
        option.init_from_coverage(coverage,
            self.options_displayer.contract.start_date)
        self.options_displayer.contract.options = list(
            self.options_displayer.contract.options)
        self.options_displayer.contract.options.append(option)
        return option

    def transition_update_options(self):
        Option = Pool().get('contract.option')
        to_delete = []
        to_subscribe = [x.coverage for x in self.options_displayer.options
            if x.is_selected]
        contract = self.options_displayer.contract
        if contract.options:
            contract.options = list(contract.options)
        for option in contract.options:
            if option.coverage in to_subscribe:
                to_subscribe.remove(option.coverage)
            else:
                to_delete.append(option)
        for coverage in to_subscribe:
            self.subscribe_option(coverage)
        contract.options = list(contract.options)
        contract.options[:] = [x for x in contract.options
            if not x in to_delete]
        if to_delete:
            Option.delete(to_delete)
        contract.init_extra_data()
        contract.save()
        return 'end'


class OptionsDisplayer(model.CoopView):
    'Select Covered Element'

    __name__ = 'contract.wizard.option_subscription.options_displayer'

    contract = fields.Many2One('contract', 'Contract',
        states={'invisible': True}, ondelete='RESTRICT')
    options = fields.One2Many(
        'contract.wizard.option_subscription.options_displayer.option',
        None, 'Options')

    @fields.depends('options')
    def on_change_options(self):
        selected = [elem for elem in self.options
            if elem.is_selected and not elem.selection == 'automatic']
        to_update = []
        excluded = []
        required = []
        for x in selected:
            excluded += x.coverage.options_excluded
            required += x.coverage.options_required
        for x in self.options:
            if not x in selected or x.coverage in excluded:
                to_update.append({
                        'id': x.id,
                        'is_selected': False,
                        'selection': ('excluded'
                            if x.coverage in excluded else ''),
                        })
            if x.coverage in required:
                to_update.append({
                        'id': x.id,
                        'is_selected': True,
                        'selection': ('manual'
                            if x in selected else 'automatic'),
                        })
        return {'options': {'update': to_update}}


class WizardOption(model.CoopView):
    'Option'

    __name__ = 'contract.wizard.option_subscription.options_displayer.option'

    coverage = fields.Many2One('offered.option.description',
        'Option Description', readonly=True)
    coverage_behaviour = fields.Selection(offered.SUBSCRIPTION_BEHAVIOUR,
        'Subscription Behaviour', sort=False, readonly=True)
    is_selected = fields.Boolean('Selected?', states={'readonly':
            Eval('selection').in_(['automatic', 'mandatory', 'excluded'])})
    selection = fields.Selection([
            ('', ''),
            ('mandatory', 'Mandatory'),
            ('automatic', 'Automatic'),
            ('manual', 'Manual'),
            ('excluded', 'Excluded')], 'Selection')
