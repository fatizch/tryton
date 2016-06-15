from trytond.pool import PoolMeta, Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button, \
    StateAction
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'OptionSubscription',
    'OptionsDisplayer',
    'ExtraPremiumSelector',
    'OptionSelector',
    'ExtraPremiumDisplay',
    'ManageExtraPremium',
    'CreateExtraPremium',
    'CreateExtraPremiumOptionSelector',
    'ExclusionSelector',
    'ExclusionDisplay',
    'ManageExclusion',
    'WizardOption',
    ]


class OptionSubscription:
    'Option Subscription'

    __name__ = 'contract.wizard.option_subscription'

    def default_options_displayer(self, values):
        pool = Pool()
        covered_element = None
        if Transaction().context.get('active_model') == 'contract':
            Contract = pool.get('contract')
            contract = Contract(Transaction().context.get('active_id'))
            if len(contract.covered_elements) == 1:
                covered_element = contract.covered_elements[0]
        elif (Transaction().context.get('active_model') ==
                'contract.covered_element'):
            CoveredElement = pool.get('contract.covered_element')
            covered_element = CoveredElement(Transaction().context.get(
                    'active_id'))
            contract = covered_element.contract
        if covered_element:
            res = self.init_default_options(contract, covered_element.options,
                self.select_package.package)
            res['covered_element'] = covered_element.id
            res['party'] = (covered_element.party.id
                if covered_element.party else None)
            res['hide_covered_element'] = True
        else:
            res = {'contract': contract.id}
        res['possible_covered_elements'] = [
            x.id for x in contract.covered_elements]
        return res

    def transition_update_options(self):
        cov_element = self.options_displayer.covered_element
        cov_element.options = self.add_remove_options(
            list(getattr(cov_element, 'options', [])),
            self.options_displayer.options)
        cov_element.save()
        return 'end'


class OptionsDisplayer:
    'Select Covered Element'

    __name__ = 'contract.wizard.option_subscription.options_displayer'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element',
        domain=[('id', 'in', Eval('possible_covered_elements'))],
        states={'invisible': Bool(Eval('hide_covered_element'))},
        depends=['possible_covered_elements', 'hide_covered_element'],
        required=True)
    hide_covered_element = fields.Boolean('Hide Covered Element',
        states={'invisible': True})
    possible_covered_elements = fields.Many2Many(
        'contract.covered_element', None, None, 'Covered Elements',
        states={'invisible': True})
    party = fields.Function(
        fields.Many2One('party.party', 'Party'),
        'on_change_with_party')

    @fields.depends('contract', 'covered_element', 'options')
    def on_change_covered_element(self):
        if not self.covered_element or not self.contract:
            self.options = []
        pool = Pool()
        Subscribor = pool.get('contract.wizard.option_subscription',
            type='wizard')
        Option = pool.get(
            'contract.wizard.option_subscription.options_displayer.option')
        self.options = [Option(**x)
            for x in Subscribor.init_default_options(self.contract,
                self.covered_element.options, None).get('options', None)]

    @fields.depends('covered_element')
    def on_change_with_party(self):
        return (self.covered_element.party.id
            if self.covered_element and self.covered_element.party else None)


class WizardOption:
    __name__ = 'contract.wizard.option_subscription.options_displayer.option'

    def init_subscribed_option(self, displayer, option):
        option.item_desc = displayer.covered_element.item_desc
        option.covered_element = displayer.covered_element
        super(WizardOption, self).init_subscribed_option(displayer, option)


class ExtraPremiumSelector(model.CoopView):
    'Extra Premium'

    __name__ = 'contract.manage_extra_premium.select.extra'

    extra_premium = fields.Many2One('contract.option.extra_premium',
        'Extra Premium')
    extra_premium_name = fields.Char('Extra Premium', readonly=True)
    selected = fields.Boolean('Selected')


class OptionSelector(model.CoopView):
    'Option'

    __name__ = 'contract.manage_extra_premium.select.option'

    option = fields.Many2One('contract.option', 'Option', readonly=True)
    option_name = fields.Char('Option', readonly=True)
    selected = fields.Boolean('Selected')
    extra_premiums = fields.Char('Existing Extra Premiums')


class ExtraPremiumDisplay(model.CoopView):
    'Extra Premium Display'

    __name__ = 'contract.manage_extra_premium.select'

    contract = fields.Many2One('contract', 'Contract')
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', domain=[('contract', '=', Eval('contract'))],
        states={'invisible': Eval('kind', '') != 'contract'},
        depends=['contract', 'kind'])
    extra_premiums = fields.One2Many(
        'contract.manage_extra_premium.select.extra', None,
        'Extra Premiums', states={
            'readonly': Eval('kind', '') == 'extra_premium'},
        depends=['kind'])
    kind = fields.Selection([
            ('contract', 'Contract'),
            ('option', 'Option'),
            ('extra_premium', 'Extra Premium'),
            ], 'Kind')
    option = fields.Many2One('contract.option', 'Option')
    options = fields.One2Many('contract.manage_extra_premium.select.option',
        None, 'Options')
    extra_premium = fields.Many2One('contract.option.extra_premium',
        'Extra Premium')

    @classmethod
    def get_extra_premium_name(cls, extra_premium):
        return '%s (%s) : %s' % (extra_premium.motive.rec_name,
            extra_premium.option.rec_name,
            extra_premium.get_rec_name(None))

    @classmethod
    def get_option_name(cls, option):
        return '%s' % option.coverage.name

    @classmethod
    def get_extra_premiums(cls, option):
        return ", ".join([x.rec_name for x in option.extra_premiums])

    @fields.depends('covered_element', 'extra_premiums',
        'options', 'option', 'extra_premium')
    def on_change_covered_element(self):
        pool = Pool()
        Extra = pool.get('contract.manage_extra_premium.select.extra')
        Option = pool.get('contract.manage_extra_premium.select.option')
        if self.covered_element:
            new_extra_premiums = list(self.extra_premiums)
            for option in self.covered_element.options:
                if self.option and self.option != option:
                    continue
                for extra_premium in option.extra_premiums:
                    if (self.extra_premium and
                            self.extra_premium != extra_premium):
                        continue
                    new_extra_premiums.append(Extra(**{
                            'selected': (self.extra_premium
                                and self.extra_premium == extra_premium),
                            'extra_premium': extra_premium.id,
                            'extra_premium_name': self.get_extra_premium_name(
                                extra_premium),
                            }))
            self.extra_premiums = new_extra_premiums

            new_options = list(self.options)
            for option in self.covered_element.options:
                if not self.option or self.option == option:
                    continue
                new_options.append(Option(**{
                            'selected': False,
                            'option': option.id,
                            'option_name': self.get_option_name(option),
                            'extra_premiums': self.get_extra_premiums(option),
                            }))

            self.options = new_options


class ManageExtraPremium(Wizard):
    'Manage Extra Premiums'

    __name__ = 'contract.manage_extra_premium'

    start_state = 'existing'
    existing = StateView('contract.manage_extra_premium.select',
        'contract_insurance.manage_extra_premium_select_view_form', [
            Button('End', 'end', 'tryton-cancel'),
            Button('Delete Selected', 'delete_selected', 'tryton-clear',
                states={'invisible': Eval('kind', '') == 'extra_premium'}),
            Button('Propagate Selected', 'propagate_selected',
                'tryton-fullscreen', default=True),
            ])
    propagate_selected = StateTransition()
    delete_selected = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ManageExtraPremium, cls).__setup__()
        cls._error_messages.update({
                'no_extra_selected': 'At least one extra premium must be '
                'selected',
                '1_coverage_selected': 'There may be only one coverage '
                'selected for this action',
                })

    def default_existing(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        Option = pool.get('contract.option')
        ExtraPremium = pool.get('contract.option.extra_premium')
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        extra_premium = None
        if active_model == 'contract':
            kind = 'contract'
            selected_option = None
            contract = Contract(active_id)
            covered_element = contract.covered_elements[0]
        elif active_model == 'contract.option':
            kind = 'option'
            selected_option = Option(active_id)
            covered_element = selected_option.covered_element
            contract = selected_option.parent_contract
        elif active_model == 'contract.option.extra_premium':
            kind = 'extra_premium'
            extra_premium = ExtraPremium(active_id)
            selected_option = extra_premium.option
            covered_element = selected_option.covered_element
            contract = selected_option.parent_contract
        return {
            'contract': contract.id,
            'covered_element': covered_element.id,
            'kind': kind,
            'option': selected_option.id if selected_option else None,
            'extra_premium': extra_premium.id if extra_premium else None,
            }

    def transition_propagate_selected(self):
        selected = [x for x in self.existing.extra_premiums if x.selected]
        if len(selected) == 0:
            self.raise_user_error('no_extra_selected')
        for cur_selected in selected:
            selected_extra = cur_selected.extra_premium
            for option in self.existing.options:
                if not option.selected:
                    continue
                new_extra = selected_extra.copy([selected_extra])[0]
                new_extra.option = option.option
                new_extra.save()
        return 'end'

    def transition_delete_selected(self):
        selected = [x for x in self.existing.extra_premiums if x.selected]
        if len(selected) == 0:
            self.raise_user_error('no_extra_selected')
        selected[0].extra_premium.delete([x.extra_premium for x in selected])
        return 'existing'


class CreateExtraPremium(Wizard):
    'Create Extra Premium'

    __name__ = 'contract.option.extra_premium.create'

    start_state = 'extra_premium_data'
    extra_premium_data = StateView('contract.option.extra_premium',
        'contract_insurance.extra_premium_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Select Options', 'select_options', 'tryton-go-next',
                default=True)])
    select_options = StateView(
        'contract.option.extra_premium.create.option_selector',
        'contract_insurance.extra_premium_create_option_selector_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Modify Extra Premium', 'extra_premium_data',
                'tryton-go-previous'),
            Button('Apply', 'apply', 'tryton-go-next', default=True),
            Button('Apply & New', 'apply_and_relaunch', 'tryton-refresh')])
    apply = StateTransition()
    apply_and_relaunch = StateTransition()
    re_launch = StateAction('contract_insurance.act_create_extra_premium')

    @classmethod
    def __setup__(cls):
        super(CreateExtraPremium, cls).__setup__()
        cls._error_messages.update({
                'option_required': 'An option must be subscribed on the '
                'contract before going on',
                })

    def default_extra_premium_data(self, name):
        if self.extra_premium_data._default_values:
            return self.extra_premium_data._default_values
        contract_id = Transaction().context.get('active_id')
        Contract = Pool().get('contract')
        contract = Contract(contract_id)
        all_options = contract.options + contract.covered_element_options
        if not all_options:
            self.raise_user_error('option_required')
        return {
            'start_date': contract.start_date,
            # Set one random option to bypass the "required" attribute
            'option': all_options[0].id,
            }

    def default_select_options(self, name):
        if self.select_options._default_values:
            return self.select_options._default_values
        contract_id = Transaction().context.get('active_id')
        Contract = Pool().get('contract')
        contract = Contract(contract_id)
        covered_element = None
        hide_covered_element = len(contract.covered_elements) == 1
        if hide_covered_element:
            covered_element = contract.covered_elements[0].id
        return {
            'contract': contract.id,
            'covered_element': covered_element,
            'hide_covered_element': hide_covered_element,
            }

    def apply_(self):
        ExtraPremium = Pool().get('contract.option.extra_premium')
        to_create = []
        for option in self.select_options.options:
            if not option.selected:
                continue
            new_extra_premium = self.extra_premium_data._default_values
            new_extra_premium['option'] = option.option
            to_create.append(new_extra_premium)
        ExtraPremium.create(to_create)

    def transition_apply(self):
        self.apply_()
        return 'end'

    def transition_apply_and_relaunch(self):
        self.apply_()
        return 're_launch'

    def do_re_launch(self, action):
        return action, {
            'model': Transaction().context.get('active_model'),
            'id': Transaction().context.get('active_id'),
            'ids': [Transaction().context.get('active_id')],
            }


class CreateExtraPremiumOptionSelector(model.CoopView):
    'Create Extra Premium Option Selector'

    __name__ = 'contract.option.extra_premium.create.option_selector'

    contract = fields.Many2One('contract', 'Contract')
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', domain=[('contract', '=', Eval('contract'))],
        states={'invisible': Eval('hide_covered_element', False)},
        depends=['contract', 'hide_covered_element'])
    hide_covered_element = fields.Boolean('Hide Covered Element')
    options = fields.One2Many('contract.manage_extra_premium.select.option',
        None, 'Options')

    @classmethod
    def get_option_name(cls, option):
        return '[%s] %s' % (option.covered_element.rec_name,
            option.coverage.name)

    @fields.depends('contract', 'options', 'covered_element')
    def on_change_with_options(self):
        to_create = []
        existing_options = dict([(x.option, x) for x in self.options])
        for option in (
                self.covered_element.options if self.covered_element else []):
            if option in existing_options:
                del existing_options[option]
                continue
            to_create.append({
                    'option': option.id,
                    'selected': False,
                    'option_name': self.get_option_name(option),
                    })
        if len(to_create) == 1:
            to_create[0]['selected'] = True
        result = {'add': [(-1, x) for x in to_create]}
        if existing_options:
            result['remove'] = [x.id for x in existing_options.itervalues()]
        return result


class ExclusionSelector(model.CoopView):
    'Exclusion'

    __name__ = 'contract.manage_exclusion.select.exclusion'

    selected = fields.Boolean('Selected')
    exclusion = fields.Many2One('offered.exclusion', 'Exclusion')


class ExclusionDisplay(model.CoopView):
    'Exclusion Display'

    __name__ = 'contract.manage_exclusion.select'

    options = fields.One2Many('contract.manage_extra_premium.select.option',
        None, 'Options')
    exclusions = fields.One2Many('contract.manage_exclusion.select.exclusion',
        None, 'Exclusions')


class ManageExclusion(Wizard):
    'Manage Exclusions'

    __name__ = 'contract.manage_exclusion'

    start_state = 'existing'
    existing = StateView('contract.manage_exclusion.select',
        'contract_insurance.manage_exclusion_select_view_form', [
            Button('End', 'end', 'tryton-cancel'),
            Button('Propagate Selected', 'propagate_selected',
                'tryton-fullscreen', default=True),
            ])
    propagate_selected = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ManageExclusion, cls).__setup__()
        cls._error_messages.update({
                'no_exclusion_selected': 'At least one exclusion must be '
                'selected',
                'no_option': 'No opion found in the context, '
                'please report this',
                })

    def default_existing(self, name):
        pool = Pool()
        Option = pool.get('contract.option')
        Selector = pool.get('contract.manage_extra_premium.select')
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        if active_model != 'contract.option':
            self.raise_user_error('no_option')
        selected_option = Option(active_id)
        covered_element = selected_option.covered_element
        existing_exclusions = []
        existing_options = []
        for exclusion in selected_option.exclusions:
            existing_exclusions.append({
                    'selected': True,
                    'exclusion': exclusion.id})
        for option in covered_element.options:
            if option == selected_option:
                continue
            existing_options.append({
                    'selected': True,
                    'option': option.id,
                    'option_name': Selector.get_option_name(option)})
        return {
            'exclusions': existing_exclusions,
            'options': existing_options,
            }

    def transition_propagate_selected(self):
        selected = [x for x in self.existing.exclusions if x.selected]
        if len(selected) == 0:
            self.raise_user_error('no_exclusion_selected')
        exclusions = set([x.exclusion for x in selected])
        for option in self.existing.options:
            if not option.selected:
                continue
            values = list(option.option.exclusions)
            values.extend(list(exclusions - set(option.option.exclusions)))
            option.option.exclusions = values
            option.option.save()
        return 'end'
