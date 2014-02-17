from trytond.pool import PoolMeta, Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'OptionSubscription',
    'OptionsDisplayer',
    'ExtraPremiumSelector',
    'CoveredDataSelector',
    'ExtraPremiumDisplay',
    'ManageExtraPremium',
    'ExclusionSelector',
    'ExclusionDisplay',
    'ManageExclusion',
    'ExtraPremiumDisplayer',
    'CreateExtraPremium',
    ]


class OptionSubscription:
    'Option Subscription'

    __name__ = 'contract.wizard.option_subscription'

    def default_options_displayer(self, values):
        Contract = Pool().get('contract')
        contract = Contract(Transaction().context.get('active_id'))
        res = super(OptionSubscription, self).default_options_displayer(
            values)
        res['possible_covered_elements'] = [
            x.id for x in contract.covered_elements]
        if len(contract.covered_elements) == 1:
            res['covered_element'] = contract.covered_elements[0].id
        return res

    def subscribe_option(self, coverage):
        contract = self.options_displayer.contract
        options = [x for x in contract.options if x.offered == coverage]
        if len(options) == 1:
            option = options[0]
        else:
            option = super(OptionSubscription, self).subscribe_option(coverage)
            option.save()
            self.options_displayer.contract.save()
        cov_data = option.append_covered_data(
            self.options_displayer.covered_element)
        cov_data.save()
        return option

    def delete_options(self, options):
        Option = Pool().get('contract.option')
        CoveredData = Pool().get('contract.covered_data')
        cov_element = self.options_displayer.covered_element
        cov_data_to_del = []
        option_to_delete = []
        for option in options:
            cov_data_to_del.extend([x for x in option.covered_data
                    if x.covered_element == cov_element])
            option.covered_data = list(option.covered_data)
            option.covered_data[:] = [x for x in option.covered_data
                if not x in cov_data_to_del]
            if not len(option.covered_data):
                option_to_delete.append(option)
        CoveredData.delete(cov_data_to_del)
        if option_to_delete:
            Option.delete(option_to_delete)

    def transition_update_options(self):
        cov_element = self.options_displayer.covered_element
        to_delete = []
        to_subscribe = [x.coverage for x in self.options_displayer.options
            if x.is_selected]
        contract = self.options_displayer.contract
        if contract.options:
            contract.options = list(contract.options)
        for option in contract.options:
            if option.offered in to_subscribe:
                for cov_data in option.covered_data:
                    if cov_data.covered_element == cov_element:
                        to_subscribe.remove(option.offered)
            else:
                to_delete.append(option)
        for coverage in to_subscribe:
            self.subscribe_option(coverage)
        contract.options = list(contract.options)
        contract.options[:] = [x for x in contract.options
            if not x in to_delete]
        if to_delete:
            self.delete_options(to_delete)
        contract.init_extra_data()
        contract.save()
        return 'end'


class OptionsDisplayer:
    'Select Covered Element'

    __name__ = 'contract.wizard.option_subscription.options_displayer'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element',
        domain=[('id', 'in', Eval('possible_covered_elements'))],
        depends=['possible_covered_elements'], required=True)
    possible_covered_elements = fields.Many2Many(
        'contract.covered_element', None, None, 'Covered Elements',
        states={'invisible': True})


class ExtraPremiumSelector(model.CoopView):
    'Extra Premium'

    __name__ = 'contract.manage_extra_premium.select.extra'

    selected = fields.Boolean('Selected')
    extra_premium = fields.Many2One('contract.covered_data.extra_premium',
        'Extra Premium')
    extra_premium_name = fields.Char('Extra Premium')


class CoveredDataSelector(model.CoopView):
    'Coverage'

    __name__ = 'contract.manage_extra_premium.select.coverage'

    selected = fields.Boolean('Selected')
    coverage = fields.Many2One('contract.covered_data', 'Coverage')
    coverage_name = fields.Char('Coverage')


class ExtraPremiumDisplay(model.CoopView):
    'Extra Premium Display'

    __name__ = 'contract.manage_extra_premium.select'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', domain=[('contract', '=', Eval('contract'))],
        states={'invisible': Eval('kind', '') != 'contract'},
        depends=['contract'])
    covered_data = fields.Many2One('contract.covered_data', 'Covered Data')
    contract = fields.Many2One('contract', 'Contract')
    extra_premiums = fields.One2Many(
        'contract.manage_extra_premium.select.extra', None,
        'Extra Premiums', states={
            'readonly': Eval('kind', '') == 'extra_premium'})
    coverages = fields.One2Many(
        'contract.manage_extra_premium.select.coverage', None,
        'Coverages')
    kind = fields.Selection([
            ('contract', 'Contract'),
            ('covered_data', 'Covered Data'),
            ('extra_premium', 'Extra Premium'),
            ], 'Kind')

    @classmethod
    def get_extra_premium_name(cls, extra_premium):
        return '%s (%s) : %s' % (extra_premium.motive.rec_name,
            extra_premium.covered_data.rec_name,
            extra_premium.get_rec_name(None))

    @classmethod
    def get_coverage_name(cls, coverage):
        return '%s (%s - %s)' % (coverage.option.offered.name,
            coverage.start_date,
            coverage.end_date if coverage.end_date else '')

    @fields.depends('covered_element', 'extra_premiums', 'coverages')
    def on_change_covered_element(self):
        extra_to_delete = [x.id for x in self.extra_premiums]
        coverages_to_delete = [x.id for x in self.coverages]
        result = {
            'extra_premiums': {'remove': extra_to_delete},
            'coverages': {'remove': coverages_to_delete},
            }
        if not self.covered_element:
            return result
        existing_extras = []
        existing_coverages = []
        for covered_data in self.covered_element.covered_data:
            for extra_premium in covered_data.extra_premiums:
                existing_extras.append({
                        'selected': False,
                        'extra_premium': extra_premium.id,
                        'extra_premium_name': self.get_extra_premium_name(
                            extra_premium),
                        })
            existing_coverages.append({
                    'selected': False,
                    'coverage': covered_data.id,
                    'coverage_name': self.get_coverage_name(covered_data),
                    })
        result['extra_premiums']['add'] = existing_extras
        result['coverages']['add'] = existing_coverages
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
        CoveredData = pool.get('contract.covered_data')
        ExtraPremium = pool.get('contract.covered_data.extra_premium')
        Selector = pool.get('contract.manage_extra_premium.select')
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        if active_model == 'contract':
            kind = 'contract'
            contract = Contract(active_id)
            covered_element = contract.covered_elements[0]
            selected_covered_data = None
            existing_extras = []
            existing_coverages = []
            for covered_data in covered_element.covered_data:
                for extra_premium in covered_data.extra_premiums:
                    existing_extras.append({
                            'selected': False,
                            'extra_premium': extra_premium.id,
                            'extra_premium_name':
                            Selector.get_extra_premium_name(extra_premium)})
                existing_coverages.append({
                        'selected': False,
                        'coverage': covered_data.id,
                        'coverage_name': Selector.get_coverage_name(
                            covered_data)})
        elif active_model == 'contract.covered_data':
            kind = 'covered_data'
            selected_covered_data = CoveredData(active_id)
            covered_element = selected_covered_data.covered_element
            contract = selected_covered_data.contract
            existing_extras = []
            existing_coverages = []
            for extra_premium in selected_covered_data.extra_premiums:
                existing_extras.append({
                        'selected': True,
                        'extra_premium': extra_premium.id,
                        'extra_premium_name':
                        Selector.get_extra_premium_name(extra_premium)})
            for covered_data in covered_element.covered_data:
                if covered_data == selected_covered_data:
                    continue
                existing_coverages.append({
                        'selected': True,
                        'coverage': covered_data.id,
                        'coverage_name': Selector.get_coverage_name(
                            covered_data)})
        elif active_model == 'contract.covered_data.extra_premium':
            kind = 'extra_premium'
            source_extra = ExtraPremium(active_id)
            selected_covered_data = source_extra.covered_data
            covered_element = selected_covered_data.covered_element
            contract = selected_covered_data.contract
            contract = selected_covered_data.contract
            existing_extras = [{
                    'selected': True,
                    'extra_premium': source_extra.id,
                    'extra_premium_name': Selector.get_extra_premium_name(
                        source_extra)}]
            existing_coverages = []
            for covered_data in covered_element.covered_data:
                if covered_data == selected_covered_data:
                    continue
                existing_coverages.append({
                        'selected': True,
                        'coverage': covered_data.id,
                        'coverage_name': Selector.get_coverage_name(
                            covered_data)})
        return {
            'contract': contract.id,
            'covered_element': covered_element.id,
            'kind': kind,
            'covered_data': selected_covered_data.id,
            'extra_premiums': existing_extras,
            'coverages': existing_coverages,
            }

    def transition_propagate_selected(self):
        selected = [x for x in self.existing.extra_premiums if x.selected]
        if len(selected) == 0:
            self.raise_user_error('no_extra_selected')
        for cur_selected in selected:
            selected_extra = cur_selected.extra_premium
            for coverage in self.existing.coverages:
                if not coverage.selected:
                    continue
                found = False
                for extra in coverage.coverage.extra_premiums:
                    if extra == selected_extra:
                        continue
                    if extra.kind == selected_extra.kind:
                        found = extra
                        break
                if found:
                    found.delete([found])
                new_extra = selected_extra.copy([selected_extra])[0]
                new_extra.covered_data = coverage.coverage
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

    coverages = fields.One2Many(
        'contract.manage_extra_premium.select.coverage', None,
        'Coverages')
    exclusions = fields.One2Many(
        'contract.manage_exclusion.select.exclusion', None,
        'Exclusions')


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
                'no_covered_data': 'No covered data found in the context, '
                'please report this',
                })

    def default_existing(self, name):
        pool = Pool()
        CoveredData = pool.get('contract.covered_data')
        Selector = pool.get('contract.manage_extra_premium.select')
        active_id = Transaction().context.get('active_id')
        active_model = Transaction().context.get('active_model')
        if active_model != 'contract.covered_data':
            self.raise_user_error('no_covered_data')
        selected_covered_data = CoveredData(active_id)
        covered_element = selected_covered_data.covered_element
        existing_exclusions = []
        existing_coverages = []
        for exclusion in selected_covered_data.exclusions:
            existing_exclusions.append({
                    'selected': True,
                    'exclusion': exclusion.id})
        for covered_data in covered_element.covered_data:
            if covered_data == selected_covered_data:
                continue
            existing_coverages.append({
                    'selected': True,
                    'coverage': covered_data.id,
                    'coverage_name': Selector.get_coverage_name(
                        covered_data)})
        return {
            'exclusions': existing_exclusions,
            'coverages': existing_coverages,
            }

    def transition_propagate_selected(self):
        selected = [x for x in self.existing.exclusions if x.selected]
        if len(selected) == 0:
            self.raise_user_error('no_exclusion_selected')
        exclusions = set([x.exclusion for x in selected])
        for coverage in self.existing.coverages:
            if not coverage.selected:
                continue
            values = list(coverage.coverage.exclusions)
            values.extend(list(exclusions - set(coverage.coverage.exclusions)))
            coverage.coverage.exclusions = values
            coverage.coverage.save()
        return 'end'


class ExtraPremiumDisplayer(model.CoopView):
    'Extra Premium Displayer'

    __name__ = 'contract.create_extra_premium.create'

    contract = fields.Many2One('contract', 'Contract')
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', domain=[('contract', '=', Eval('contract'))],
        depends=['contract'])
    covered_data = fields.Many2One('contract.covered_data', 'Covered Data',
        domain=[('covered_element', '=', Eval('covered_element'))],
        states={'invisible': ~Eval('covered_element')},
        depends=['covered_element'])
    extra_premium = fields.One2Many('contract.covered_data.extra_premium',
        None, 'Extra Premium', domain=[
            ('covered_data', '=', Eval('covered_data'))], states={
                'invisible': ~Eval('covered_data')},
        depends=['covered_data'])

    @fields.depends('covered_element', 'extra_premium')
    def on_change_covered_element(self):
        result = {}
        if not self.covered_element:
            result = {'covered_data': None}
        else:
            result = {
                'covered_data': self.covered_element.covered_data[0].id,
                'extra_premium': {'update': [{
                            'id': self.extra_premium[0].id,
                            'covered_data':
                            self.covered_element.covered_data[0].id}]}}
        return result

    @fields.depends('covered_data', 'extra_premium')
    def on_change_covered_data(self):
        result = {'extra_premium': {'remove':
                [x.id for x in self.extra_premium]}}
        if not self.covered_data:
            return result
        result['extra_premium']['add'] = [{
                'covered_data': self.covered_data.id,
                'start_date': self.covered_data.start_date,
                'end_date': self.covered_data.end_date,
                'calculation_kind': 'rate',
                'rate': 0,
                'flat_amount': 0}]
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
                'no_covered_data': 'Please select a covered data to continue',
                })

    def default_extra_premium(self, name):
        assert Transaction().context.get('active_model') == 'contract'
        pool = Pool()
        contract = pool.get('contract')(Transaction().context.get('active_id'))
        covered_element = contract.covered_elements[0]
        covered_data = covered_element.covered_data[0]
        return {
            'contract': contract.id,
            'covered_element': covered_element.id,
            'covered_data': covered_data.id,
            'extra_premium': [{
                    'covered_data': covered_data.id,
                    'start_date': covered_data.start_date,
                    'end_date': covered_data.end_date,
                    'calculation_kind': 'rate',
                    'rate': 0,
                    'flat_amount': 0}]}

    def transition_create_extra(self):
        if not self.extra_premium.covered_data:
            self.raise_user_error('no_covered_data')
        self.extra_premium.extra_premium[0].save()
        return 'end'
