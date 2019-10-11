# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button, \
    StateAction
from trytond.pyson import Eval, Bool, Len
from trytond.transaction import Transaction

from trytond.modules.party.exceptions import EraseError
from trytond.modules.coog_core import fields, model, utils

__all__ = [
    'PackageSelection',
    'PackageSelectionPerCovered',
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
    'ExclusionOptionSelector',
    'PartyErase',
    ]


class PackageSelectionPerCovered(model.CoogView):
    'Select Package Per Covered'
    __name__ = 'contract.wizard.option_subscription.select_package_per_covered'

    covered = fields.Many2One('contract.covered_element', 'Covered Element',
        readonly=True)
    package = fields.Many2One('offered.package', 'Package',
        domain=[('id', 'in', Eval('possible_packages'))],
        depends=['possible_packages'])
    possible_packages = fields.Many2Many('offered.package', None, None,
        'Possible Packages')
    main_selection_screen = fields.Many2One(
        'contract.wizard.option_subscription.select_package',
        'Main Selection Screen')


class PackageSelection(metaclass=PoolMeta):
    __name__ = 'contract.wizard.option_subscription.select_package'

    select_package_per_covered = fields.Boolean('Select Package Per Covered')
    covereds_package = fields.One2Many(
        'contract.wizard.option_subscription.select_package_per_covered',
        'main_selection_screen', 'Package per Covered',
        states={'invisible': ~Eval('select_package_per_covered')},
        depends=['select_package_per_covered'])

    @classmethod
    def __setup__(cls):
        super(PackageSelection, cls).__setup__()
        cls.package.states['invisible'] = Eval('select_package_per_covered')
        cls.package.depends.append('select_package_per_covered')


class OptionSubscription(metaclass=PoolMeta):
    'Option Subscription'
    __name__ = 'contract.wizard.option_subscription'

    def get_contract(self):
        if (Transaction().context.get('active_model') ==
                'contract.covered_element'):
            CoveredElement = Pool().get('contract.covered_element')
            covered_element = CoveredElement(Transaction().context.get(
                'active_id'))
            contract = covered_element.contract
        else:
            contract = super().get_contract()

        return contract

    def default_select_package(self, values):
        contract = self.get_contract()
        if not contract:
            return {}
        if not contract.product.packages_defined_per_covered:
            res = super(OptionSubscription, self).default_select_package(values)
            res['select_package_per_covered'] = False
            return res
        covereds_package = []
        for covered in contract.covered_elements:
            covereds_package.append({
                    'covered': covered.id,
                    'possible_packages': [x.id for x in
                        contract.product.packages]
                    })
        return {
            'select_package_per_covered': True,
            'covereds_package': covereds_package,
            }

    def apply_package(self):
        contract = self.get_contract()
        if not contract.product.packages_defined_per_covered:
            super(OptionSubscription, self).apply_package()
        else:
            new_covereds = []
            for covered_displayer in self.select_package.covereds_package:
                if covered_displayer.package:
                    new_covereds.append(
                        covered_displayer.package.apply_package_on_covered(
                            covered_displayer.covered))
                else:
                    new_covereds.append(covered_displayer.covered)
            contract.covered_elements = new_covereds
            contract.save()

    def default_options_displayer(self, values):
        res = super(OptionSubscription, self).default_options_displayer(values)
        pool = Pool()
        covered_element = None
        if (Transaction().context.get('active_model') ==
                'contract.covered_element'):
            CoveredElement = pool.get('contract.covered_element')
            covered_element = CoveredElement(Transaction().context.get(
                    'active_id'))
            contract = covered_element.contract
        else:
            contract = self.get_contract()
            if contract.covered_elements:
                covered_element = contract.covered_elements[0]
        if contract:
            res['contract'] = contract.id
        if covered_element:
            res['covered_element'] = covered_element.id
            res['party'] = (covered_element.party.id
                if covered_element.party else None)
        res['possible_covered_elements'] = [
            x.id for x in contract.covered_elements]
        return res

    def transition_update_options(self):
        cov_element = self.options_displayer.covered_element
        if not cov_element:
            return super(OptionSubscription, self).transition_update_options()
        cov_element.options = self.add_remove_options(
            list(getattr(cov_element, 'options', [])),
            self.options_displayer.options)
        cov_element.save()
        return 'end'


class OptionsDisplayer(metaclass=PoolMeta):
    'Select Covered Element'
    __name__ = 'contract.wizard.option_subscription.options_displayer'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element',
        domain=[('id', 'in', Eval('possible_covered_elements'))],
        states={'invisible': ~Bool(Eval('possible_covered_elements'))},
        depends=['possible_covered_elements'])
    possible_covered_elements = fields.Many2Many(
        'contract.covered_element', None, None, 'Covered Elements',
        states={'invisible': True})
    party = fields.Function(
        fields.Many2One('party.party', 'Party'),
        'on_change_with_party')

    @fields.depends('covered_element')
    def on_change_contract(self):
        if not self.covered_element:
            super(OptionsDisplayer, self).on_change_contract()

    @fields.depends('contract', 'covered_element', 'options', 'package')
    def on_change_covered_element(self):
        self.options = []
        if self.covered_element:
            self.update_options(self.covered_element.options,
                [x for x in self.covered_element.contract.product.coverages
                    if not x.is_contract_option()])
        elif self.contract:
            self.update_options(self.contract.options,
                [x for x in self.contract.product.coverages
                    if x.is_contract_option()])

    @fields.depends('covered_element')
    def on_change_with_party(self):
        return (self.covered_element.party.id
            if self.covered_element and self.covered_element.party else None)


class WizardOption(metaclass=PoolMeta):
    __name__ = 'contract.wizard.option_subscription.options_displayer.option'

    def init_subscribed_option(self, displayer, option):
        option.item_desc = displayer.covered_element.item_desc
        option.covered_element = displayer.covered_element
        super(WizardOption, self).init_subscribed_option(displayer, option)


class ExtraPremiumSelector(model.CoogView):
    'Extra Premium'

    __name__ = 'contract.manage_extra_premium.select.extra'

    extra_premium = fields.Many2One('contract.option.extra_premium',
        'Extra Premium')
    extra_premium_name = fields.Char('Extra Premium', readonly=True)
    selected = fields.Boolean('Selected')


class OptionSelector(model.CoogView):
    'Option'

    __name__ = 'contract.manage_extra_premium.select.option'

    option = fields.Many2One('contract.option', 'Option', readonly=True)
    option_name = fields.Char('Option', readonly=True)
    selected = fields.Boolean('Selected')
    extra_premiums = fields.Char('Existing Extra Premiums')


class ExtraPremiumDisplay(model.CoogView):
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
            raise ValidationError(gettext(
                    'contract_insurance.msg_no_extra_selected'))
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
            raise ValidationError(gettext(
                    'contract_insurance.msg_no_extra_selected'))
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

    def default_extra_premium_data(self, name):
        if self.extra_premium_data._default_values:
            return self.extra_premium_data._default_values
        contract_id = Transaction().context.get('active_id')
        Contract = Pool().get('contract')
        contract = Contract(contract_id)
        all_options = contract.options + contract.covered_element_options
        if not all_options:
            raise ValidationError(gettext(
                    'contract_insurance.msg_option_required'))
        return {
            'manual_start_date': contract.start_date,
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
            if (new_extra_premium['manual_start_date'] ==
                    self.select_options.contract.start_date):
                del new_extra_premium['manual_start_date']
            for fname, field_ in ExtraPremium._fields.items():
                if isinstance(field_, fields.Function) and not \
                        field_.setter and fname in new_extra_premium:
                    del new_extra_premium[fname]
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


class CreateExtraPremiumOptionSelector(model.CoogView):
    'Create Extra Premium Option Selector'

    __name__ = 'contract.option.extra_premium.create.option_selector'

    contract = fields.Many2One('contract', 'Contract')
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', domain=[('contract', '=', Eval('contract'))],
        states={'invisible': Eval('hide_covered_element', False)},
        depends=['contract', 'hide_covered_element'])
    hide_covered_element = fields.Boolean('Hide Covered Element')
    options = fields.One2Many('contract.manage_extra_premium.select.option',
        None, 'Options', readonly=True)

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
            result['remove'] = [x.id for x in existing_options.values()]
        return result


class ManageExclusion(Wizard):
    'Manage Exclusions'

    __name__ = 'contract.manage_exclusion'

    start_state = 'existing'
    existing = StateView('contract.manage_exclusion.select',
        'contract_insurance.manage_exclusion_select_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next', default=True),
            ])
    apply = StateTransition()

    def default_existing(self, name):
        pool = Pool()
        active_model = Transaction().context.get('active_model')
        active_id = Transaction().context.get('active_id')
        Contract = pool.get('contract')
        Displayer = pool.get('contract.manage_exclusion.select.exclusion')
        if active_model == 'contract':
            contract = Contract(active_id)
            if len(contract.covered_elements) == 1:
                covered_element = contract.covered_elements[0]
            else:
                covered_element = None
        elif active_model == 'contract.option':
            option = pool.get('contract.option')(active_id)
            contract = option.parent_contract
            covered_element = option.covered_element
        else:
            raise ValueError('Unsupported model %s' % active_model)
        defaults = {
            'covered_element': covered_element.id if covered_element else None,
            'possible_covered_elements': [x.id
                for x in contract.covered_elements]}
        all_exclusions = []
        for cur_covered in contract.covered_elements:
            exclusions = defaultdict(list)
            for option in cur_covered.options:
                for exclusion in option.exclusions:
                    option_comment = {
                        'option': option,
                        'comment': exclusion.comment}
                    exclusions[exclusion.exclusion.id].append(option_comment)
            all_exclusions += [model.dictionarize(Displayer.new_displayer(
                cur_covered, exclusion, [elt.get('option') for elt in options],
                op.get('comment'))) for exclusion, options in exclusions.items()
                for op in options]

        defaults['all_exclusions'] = all_exclusions
        if covered_element:
            default_exclusions = []
            for x in defaults['all_exclusions']:
                if x['parent'] == str(covered_element) and x not in \
                        default_exclusions:
                    default_exclusions.append(x)
            defaults['cur_exclusions'] = default_exclusions
        return defaults

    def transition_apply(self):
        Option = Pool().get('contract.option')
        self.existing.update_exclusions()
        per_option = {option: []
            for covered_element in self.existing.possible_covered_elements
            for option in covered_element.options
            }
        for exclusion in self.existing.all_exclusions:
            for option in exclusion.options:
                if option.selected:
                    per_option[option.option].append({
                        'exclusion': exclusion.exclusion,
                        'comment': exclusion.comment})
        to_save = []
        for option, exclusions in per_option.items():
            if {x.get('exclusion').id for x in exclusions} != \
                    {x.id for x in option.exclusions}:
                option.exclusions = [{
                    'option': option,
                    'exclusion': ex.get('exclusion'),
                    'comment': ex.get('comment')} for ex in exclusions]
                to_save.append(option)
        if to_save:
            Option.save(to_save)
        return 'end'


class ExclusionDisplay(model.CoogView):
    'Exclusion Display'

    __name__ = 'contract.manage_exclusion.select'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element',
        domain=[('id', 'in', Eval('possible_covered_elements'))],
        states={'readonly': Len(Eval('possible_covered_elements', [])) == 1},
        depends=['possible_covered_elements'])
    possible_covered_elements = fields.Many2Many('contract.covered_element',
        None, None, 'Possible Covered Elements', readonly=True,
        states={'invisible': True})
    all_exclusions = fields.One2Many(
        'contract.manage_exclusion.select.exclusion', None, 'Exclusions',
        states={'invisible': True})
    cur_exclusions = fields.One2Many(
        'contract.manage_exclusion.select.exclusion', None, 'Exclusions')
    used_exclusions = fields.Many2Many('offered.exclusion', None, None,
        'Used Exclusions', states={'invisible': True})
    new_exclusion = fields.Many2One('offered.exclusion', 'New Exclusion',
        states={'invisible': ~Eval('covered_element')},
        domain=[('id', 'not in', Eval('used_exclusions'))],
        depends=['covered_element', 'used_exclusions'])
    propagate_exclusion = fields.Many2One('offered.exclusion', 'Propagate',
        domain=[('id', 'in', Eval('used_exclusions'))],
        depends=['used_exclusions'])

    @classmethod
    def __setup__(cls):
        super(ExclusionDisplay, cls).__setup__()
        cls._buttons.update({
                'button_propagate_selected': {'readonly':
                    ~Eval('propagate_exclusion')},
                })

    @fields.depends('all_exclusions', 'covered_element', 'cur_exclusions',
        'new_exclusion', 'used_exclusions')
    def on_change_covered_element(self):
        self.update_exclusions()
        self.new_exclusion = None

    @fields.depends('cur_exclusions', 'covered_element', 'new_exclusion',
        'used_exclusions')
    def on_change_new_exclusion(self):
        if not self.covered_element:
            return
        Displayer = Pool().get('contract.manage_exclusion.select.exclusion')
        self.cur_exclusions = list(self.cur_exclusions) + [
            Displayer.new_displayer(self.covered_element, self.new_exclusion,
                self.covered_element.options)]
        self.new_exclusion = None
        self.used_exclusions = [x.exclusion for x in self.cur_exclusions]

    @model.CoogView.button_change('cur_exclusions', 'propagate_exclusion')
    def button_propagate_selected(self):
        options = [x.options for x in self.cur_exclusions
            if x.exclusion == self.propagate_exclusion][0]
        option_ids = [x.option.id for x in options if x.selected]
        for exclusion in self.cur_exclusions:
            for option in exclusion.options:
                option.selected = option.option.id in option_ids
            exclusion.options = list(exclusion.options)
            exclusion.option_string = exclusion.on_change_with_option_string()
        self.cur_exclusions = list(self.cur_exclusions)

    def update_exclusions(self):
        self.used_exclusions = []
        if self.cur_exclusions:
            self.all_exclusions = [x for x in self.all_exclusions
                if self.cur_exclusions[0].parent != x.parent] + list(
                self.cur_exclusions)
        if not self.covered_element:
            self.cur_exclusions = []
            return
        self.cur_exclusions = [x for x in self.all_exclusions
            if str(self.covered_element) == x.parent]
        self.used_exclusions = [x.exclusion for x in self.cur_exclusions]


class ExclusionSelector(model.CoogView):
    'Exclusion'

    __name__ = 'contract.manage_exclusion.select.exclusion'

    exclusion = fields.Many2One('offered.exclusion', 'Exclusion',
        readonly=True)
    parent = fields.Char('Parent', states={'invisible': True})
    options = fields.One2Many('contract.option.selector', None, 'Options')
    option_string = fields.Char('Options', readonly=True)
    comment = fields.Text('Comment')

    @classmethod
    def __setup__(cls):
        super(ExclusionSelector, cls).__setup__()
        cls._buttons.update({
                'button_clear_all': {},
                'button_check_all': {},
                })

    @classmethod
    def view_attributes(cls):
        return [('/form/group[@id="invisible"]', 'states',
                {'invisible': True}),
            ]

    @fields.depends('options')
    def on_change_with_option_string(self):
        return ', '.join(x.option.rec_name for x in self.options if x.selected)

    @model.CoogView.button_change('options', 'option_string')
    def button_check_all(self):
        for option in self.options:
            option.selected = True
        self.option_string = self.on_change_with_option_string()
        self.options = list(self.options)

    @model.CoogView.button_change('options', 'option_string')
    def button_clear_all(self):
        for option in self.options:
            option.selected = False
        self.option_string = ''
        self.options = list(self.options)

    @classmethod
    def new_displayer(cls, covered_element, exclusion, options, comment=''):
        OptionSelector = Pool().get('contract.option.selector')
        displayer = cls(
            parent=str(covered_element),
            exclusion=exclusion,
            options=[OptionSelector(option=x, selected=x in (options or []))
                for x in options if x.coverage.with_exclusions],
            comment=comment)
        displayer.option_string = displayer.on_change_with_option_string()
        return displayer


class ExclusionOptionSelector(model.CoogView):
    'Option selector'

    __name__ = 'contract.option.selector'

    option = fields.Many2One('contract.option', 'Option', readonly=True)
    selected = fields.Boolean('Selected')


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase(self, party):
        super(PartyErase, self).check_erase(party)
        CoveredElement = Pool().get('contract.covered_element')
        covered_elements = CoveredElement.search([
                ('party', '=', party.id)])
        active_contracts = list(set([ce.contract for ce in covered_elements
                    if ce.contract.status == 'active']))
        if active_contracts:
            raise EraseError(gettext(
                    'contract_insurance.msg_party_covered_active',
                    party=party.rec_name,
                    contracts=', '.join(
                        c.contract_number for c in active_contracts)
                    ))
        quotes = list(set([ce.contract for ce in covered_elements
                    if ce.contract.status == 'quote']))
        if quotes:
            raise EraseError(gettext(
                    'contract_insurance.msg_party_covered_quote',
                    party=party.rec_name,
                    quotes=', '.join(c.quote_number for c in quotes)
                    ))
        terminated_unreached_shelf = list(set([ce.contract
                    for ce in covered_elements
                    if ce.contract.status == 'terminated'
                    and ce.contract.product.data_shelf_life
                    and (utils.today() <= (ce.contract.end_date or
                            ce.contract.initial_start_date) +
                        relativedelta(
                            years=ce.contract.product.data_shelf_life))
                    ]))
        if terminated_unreached_shelf:
            raise EraseError(gettext(
                    'contract_insurance.msg_party_covered_unreached_shelf_life',
                    party=party.rec_name,
                    contracts=', '.join(
                        c.contract_number for c in terminated_unreached_shelf)
                    ))
