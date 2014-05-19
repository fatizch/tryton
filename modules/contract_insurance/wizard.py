from trytond.pool import PoolMeta, Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
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
    'ExclusionSelector',
    'ExclusionDisplay',
    'ManageExclusion',
    'ExtraPremiumDisplayer',
    'WizardOption',
    'CreateExtraPremium',
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
            res = self.init_default_options(contract, covered_element.options)
            res['covered_element'] = covered_element.id
            res['party'] = covered_element.party.id
            res['hide_covered_element'] = True
        else:
            res = {}
        res['possible_covered_elements'] = [
            x.id for x in contract.covered_elements]
        return res

    def transition_update_options(self):
        cov_element = self.options_displayer.covered_element
        cov_element.options = list(getattr(cov_element, 'options', []))
        self.add_remove_options(cov_element.options)
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

    @fields.depends('covered_element')
    def on_change_with_party(self):
        return (self.covered_element.party.id
            if self.covered_element and self.covered_element.party else None)

    @fields.depends('covered_element', 'options')
    def on_change_covered_element(self):
        Wizard = Pool().get('contract.wizard.option_subscription',
            type='wizard')
        if self.covered_element:
            res = Wizard.init_default_options(self.covered_element.contract,
                self.covered_element.options)
            res['options'] = {'add': [(-1, x) for x in res['options']]}
        else:
            res = {}
        if self.options:
            res.setdefault('options', {})
            res['options']['remove'] = [x.id for x in self.options]
        return res


class WizardOption:
    __name__ = 'contract.wizard.option_subscription.options_displayer.option'

    def init_subscribed_option(self, displayer, option):
        option.item_desc = displayer.covered_element.item_desc
        super(WizardOption, self).init_subscribed_option(displayer, option)


class ExtraPremiumSelector(model.CoopView):
    'Extra Premium'

    __name__ = 'contract.manage_extra_premium.select.extra'

    extra_premium = fields.Many2One('contract.option.extra_premium',
        'Extra Premium')
    extra_premium_name = fields.Char('Extra Premium')
    selected = fields.Boolean('Selected')


class OptionSelector(model.CoopView):
    'Option'

    __name__ = 'contract.manage_extra_premium.select.option'

    option = fields.Many2One('contract.option', 'Option')
    option_name = fields.Char('Option')
    selected = fields.Boolean('Selected')


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

    @classmethod
    def get_extra_premium_name(cls, extra_premium):
        return '%s (%s) : %s' % (extra_premium.motive.rec_name,
            extra_premium.option.rec_name,
            extra_premium.get_rec_name(None))

    @classmethod
    def get_option_name(cls, option):
        return '%s' % option.coverage.name

    @fields.depends('covered_element', 'extra_premiums', 'coverages')
    def on_change_covered_element(self):
        extra_to_delete = [x.id for x in self.extra_premiums]
        options_to_delete = [x.id for x in self.options]
        result = {
            'extra_premiums': {'remove': extra_to_delete},
            'options': {'remove': options_to_delete},
            }
        if not self.covered_element:
            return result
        existing_extras = []
        existing_options = []
        for option in self.covered_element.options:
            for extra_premium in option.extra_premiums:
                existing_extras.append((-1, {
                            'selected': False,
                            'extra_premium': extra_premium.id,
                            'extra_premium_name': self.get_extra_premium_name(
                                extra_premium),
                            }))
            existing_options.append((-1, {
                        'selected': False,
                        'option': option.id,
                        'option_name': self.get_option_name(option),
                        }))
        result['extra_premiums']['add'] = existing_extras
        result['coverages']['add'] = existing_options
        return result


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
        Selector = pool.get('contract.manage_extra_premium.select')
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        if active_model == 'contract':
            kind = 'contract'
            contract = Contract(active_id)
            covered_element = contract.covered_elements[0]
            selected_option = None
            existing_extras = []
            existing_options = []
            for option in covered_element.option:
                for extra_premium in option.extra_premiums:
                    existing_extras.append({
                            'selected': False,
                            'extra_premium': extra_premium.id,
                            'extra_premium_name':
                            Selector.get_extra_premium_name(extra_premium)})
                existing_options.append({
                        'selected': False,
                        'option': option.id,
                        'option_name': Selector.get_option_name(option)})
        elif active_model == 'contract.option':
            kind = 'option'
            selected_option = Option(active_id)
            covered_element = selected_option.covered_element
            contract = selected_option.parent_contract
            existing_extras = []
            existing_options = []
            for extra_premium in selected_option.extra_premiums:
                existing_extras.append({
                        'selected': True,
                        'extra_premium': extra_premium.id,
                        'extra_premium_name':
                        Selector.get_extra_premium_name(extra_premium)})
            for option in covered_element.options:
                if option == selected_option:
                    continue
                existing_options.append({
                        'selected': True,
                        'option': option.id,
                        'option_name': Selector.get_option_name(option)})
        elif active_model == 'contract.option.extra_premium':
            kind = 'extra_premium'
            source_extra = ExtraPremium(active_id)
            selected_option = source_extra.option
            covered_element = selected_option.covered_element
            contract = selected_option.parent_contract
            existing_extras = [{
                    'selected': True,
                    'extra_premium': source_extra.id,
                    'extra_premium_name': Selector.get_extra_premium_name(
                        source_extra)}]
            existing_options = []
            for option in covered_element.option:
                if option == selected_option:
                    continue
                existing_options.append({
                        'selected': True,
                        'option': option.id,
                        'option_name': Selector.get_option_name(option)})
        return {
            'contract': contract.id,
            'covered_element': covered_element.id,
            'kind': kind,
            'option': selected_option.id,
            'extra_premiums': existing_extras,
            'options': existing_options,
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


class ExtraPremiumDisplayer(model.CoopView):
    'Extra Premium Displayer'

    __name__ = 'contract.create_extra_premium.create'

    contract = fields.Many2One('contract', 'Contract')
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', domain=[('contract', '=', Eval('contract'))],
        depends=['contract'])
    option = fields.Many2One('contract.option', 'Option',
        domain=[('covered_element', '=', Eval('covered_element'))],
        states={'invisible': ~Eval('covered_element')},
        depends=['covered_element'])
    extra_premium = fields.One2Many('contract.option.extra_premium',
        None, 'Extra Premium', domain=[
            ('option', '=', Eval('option'))], states={
                'invisible': ~Eval('option')},
        depends=['option'])

    @fields.depends('covered_element', 'extra_premium')
    def on_change_covered_element(self):
        result = {}
        if not self.covered_element:
            result = {'covered_data': None}
        else:
            result = {
                'option': self.covered_element.options[0].id,
                'extra_premium': {'update': [{
                            'id': self.extra_premium[0].id,
                            'option': self.covered_element.option[0].id}]}}
        return result

    @fields.depends('option', 'extra_premium')
    def on_change_option(self):
        result = {'extra_premium': {'remove':
                [x.id for x in self.extra_premium]}}
        if not self.option:
            return result
        result['extra_premium']['add'] = [(-1, {
                    'option': self.option.id,
                    'calculation_kind': 'rate',
                    'rate': 0,
                    'flat_amount': 0})]
        return result


class CreateExtraPremium(Wizard):
    'Create Extra Premium'

    __name__ = 'contract.create_extra_premium'

    start_state = 'extra_premium'
    extra_premium = StateView('contract.create_extra_premium.create',
        'contract_insurance.create_extra_premium_create_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_extra', 'tryton-ok', states={
                    'readonly': ~Eval('covered_data')})])
    create_extra = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CreateExtraPremium, cls).__setup__()
        cls._error_messages.update({
                'no_option': 'Please select an option to continue',
                })

    def default_extra_premium(self, name):
        assert Transaction().context.get('active_model') == 'contract'
        pool = Pool()
        contract = pool.get('contract')(Transaction().context.get('active_id'))
        covered_element = contract.covered_elements[0]
        option = covered_element.option[0]
        return {
            'contract': contract.id,
            'covered_element': covered_element.id,
            'option': option.id,
            'extra_premium': [{
                    'option': option.id,
                    'calculation_kind': 'rate',
                    'rate': 0,
                    'flat_amount': 0}]}

    def transition_create_extra(self):
        if not self.extra_premium.option:
            self.raise_user_error('no_option')
        self.extra_premium.extra_premium[0].save()
        return 'end'
