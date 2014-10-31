from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.wizard import StateTransition, StateView, Button, StateAction
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields, coop_string
from trytond.modules.offered import offered

__all__ = [
    'OptionSubscription',
    'OptionsDisplayer',
    'WizardOption',
    'OptionSubscriptionWizardLauncher',
    ]


class OptionSubscription(model.CoopWizard):
    'Option Subscription'

    __name__ = 'contract.wizard.option_subscription'

    options_displayer = StateView(
        'contract.wizard.option_subscription.options_displayer',
        'contract.options_displayer_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'update_options', 'tryton-go-next', default=True),
            ])
    update_options = StateTransition()
    start_state = 'options_displayer'

    @classmethod
    def init_default_options(cls, contract, subscribed_options):
        options = []
        excluded = []
        for option in subscribed_options:
            excluded += option.coverage.options_excluded
        for coverage in [x.coverage
                for x in contract.product.ordered_coverages]:
            existing_option = None
            for option in subscribed_options:
                if option.coverage == coverage:
                    existing_option = option
                    break
            selection = 'manual'
            if coverage.subscription_behaviour == 'mandatory':
                selection = 'mandatory'
            elif coverage in excluded:
                selection = 'automatic'
            option_dict = {
                'name': '%s [%s]' % (coverage.rec_name,
                    coop_string.translate_value(coverage,
                        'subscription_behaviour')),
                'is_selected': (bool(existing_option)
                    or coverage.subscription_behaviour != 'optional'),
                'coverage_behaviour': coverage.subscription_behaviour,
                'coverage': coverage.id,
                'selection': selection,
                'option': existing_option.id if existing_option else None,
                }
            options.append(option_dict)
            options += cls.init_default_childs(contract,
                coverage, existing_option, option_dict)
        return {
            'contract': contract.id,
            'options': options,
            }

    @classmethod
    def init_default_childs(cls, contract, coverage, option, parent_dict):
        return []

    def default_options_displayer(self, values):
        if Transaction().context.get('active_model') == 'contract':
            contract_id = Transaction().context.get('active_id')
        else:
            contract_id = Transaction().context.get('contract')
        if not contract_id:
            return {}
        Contract = Pool().get('contract')
        contract = Contract(contract_id)
        return self.init_default_options(contract, contract.options)

    def add_remove_options(self, options, lines):
        Option = Pool().get('contract.option')
        to_subscribe = set([x.coverage for x in lines if x.is_selected])
        to_delete = [x for x in options if x.coverage not in to_subscribe]
        options[:] = [x for x in options if x not in to_delete]
        Option.delete(to_delete)

        subscribed = set([x.coverage for x in options])
        for line in lines:
            if not line.is_selected:
                continue
            if line.coverage in subscribed:
                line.init_subscribed_option(self.options_displayer,
                    line.option)
                line.option.save()
                continue
            option = Option()
            line.init_subscribed_option(self.options_displayer, option)
            options.append(option)

    def transition_update_options(self):
        contract = self.options_displayer.contract
        contract.options = list(getattr(contract, 'options', []))
        self.add_remove_options(self, contract.options,
            self.options_displayer.options)
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
        'displayer', 'Options')

    @fields.depends('options')
    def on_change_options(self):
        selected = [elem for elem in self.options
            if (elem.is_selected and getattr(elem, 'coverage', None))]
        to_update = []
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
            to_update.append({
                    'id': x.id,
                    'is_selected': is_selected,
                    'selection': selection,
                    })
        return {'options': {'update': to_update}}


class WizardOption(model.CoopView):
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

    @fields.depends('coverage', 'coverage_behaviour')
    def on_change_with_name(self, name=None):
        if self.coverage:
            return '%s [%s]' % (self.coverage.rec_name,
                coop_string.translate_value(self, 'coverage_behaviour'))

    def init_subscribed_option(self, displayer, option):
        self.option = option
        option.product = displayer.contract.product
        option.init_from_coverage(self.coverage, option.product,
            displayer.contract.start_date)
        option.calculate()

    @staticmethod
    def default_selection():
        return 'manual'


class OptionSubscriptionWizardLauncher(model.CoopWizard):
    'Option Susbcription Wizard Launcher'

    __name__ = 'contract.wizard.option_subscription_launcher'

    start = StateTransition()
    start_wizard = StateAction('contract.option_subscription_wizard')

    def skip_wizard(self, contract):
        return bool(contract.options)

    def transition_start(self):
        Contract = Pool().get('contract')
        contract = Contract(Transaction().context.get('active_id'))
        if self.skip_wizard(contract):
            return 'end'
        else:
            return 'start_wizard'

    def do_start_wizard(self, action):
        return action, {
            'model': Transaction().context.get('active_model'),
            'id': Transaction().context.get('active_id'),
            'ids': [Transaction().context.get('active_id')],
            }
