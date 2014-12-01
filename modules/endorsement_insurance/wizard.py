from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, StateTransition, Button
from trytond.pyson import Eval, Len
from trytond.model import Model

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import EndorsementWizardStepMixin


__metaclass__ = PoolMeta
__all__ = [
    'NewCoveredElement',
    'NewOptionOnCoveredElement',
    'ExtraPremiumDisplayer',
    'ManageExtraPremium',
    'OptionSelector',
    'CoveredElementSelector',
    'NewExtraPremium',
    'StartEndorsement',
    ]


class NewCoveredElement(model.CoopView, EndorsementWizardStepMixin):
    'New Covered Element'

    __name__ = 'contract.covered_element.new'

    covered_elements = fields.One2Many('contract.covered_element', None,
        'New Covered Elements',
        domain=[
            # ('item_desc', '=', Eval('possible_item_desc', [])),
            ('parent', '=', None)],
        context={
            'contract': Eval('contract'),
            'product': Eval('product'),
            'start_date': Eval('start_date'),
            'all_extra_datas': Eval('extra_data')},
        depends=['contract', 'product', 'start_date', 'extra_data',
            'possible_item_desc'])
    extra_data = fields.Dict('extra_data', 'Contract Extra Data')
    extra_data_string = extra_data.translated('extra_data')
    contract = fields.Many2One('contract', 'Contract')
    possible_item_desc = fields.Many2Many('offered.item.description', None,
        None, 'Possible item desc')
    product = fields.Many2One('offered.product', 'Product')
    start_date = fields.Date('Start Date')

    def update_endorsement(self, endorsement, wizard):
        wizard.update_add_to_list_endorsement(self, endorsement,
            'covered_elements')


class NewOptionOnCoveredElement(model.CoopView, EndorsementWizardStepMixin):
    'New Covered Element Option'

    __name__ = 'contract.covered_element.add_option'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', states={
            'invisible': Len(Eval('possible_covered_elements', [])) > 1,
            },
        domain=[('id', 'in', Eval('possible_covered_elements'))],
        depends=['possible_covered_elements'])
    existing_options = fields.Many2Many('contract.option', None, None,
        'Existing Options', states={
            'readonly': True,
            'invisible': ~Eval('covered_element', False)},
        depends=['covered_element'])
    new_options = fields.One2Many('contract.option', None, 'New Options',
        states={'invisible': ~Eval('covered_element', False)},
        domain=[('coverage', 'in', Eval('possible_coverages'))],
        depends=['possible_coverages', 'covered_element'])
    possible_coverages = fields.Many2Many('offered.option.description',
        None, None, 'Possible Coverages')
    possible_covered_elements = fields.Many2Many('contract.covered_element',
        None, None, 'Possible Covered Elements', states={'invisible': True})

    @fields.depends('covered_element', 'new_options', 'effective_date')
    def on_change_covered_element(self):
        if not self.covered_element:
            self.new_options = []
            self.possible_coverages = []
            self.existing_options = []
            return
        Coverage = Pool().get('offered.option.description')
        self.existing_options = [x for x in self.covered_element.options]
        self.possible_coverages = list(
            set([x for x in Coverage.search(
                        Coverage.get_possible_coverages_clause(
                            self.covered_element, self.effective_date))]) -
            set([x.coverage for x in self.covered_element.options]))

    def update_option(self, option):
        contract = self.covered_element.contract
        option.covered_element = self.covered_element
        option.product = contract.product
        option.start_date = self.effective_date
        option.appliable_conditions_date = contract.appliable_conditions_date
        option.all_extra_datas = self.covered_element.all_extra_datas
        option.status = 'quote'

    @fields.depends('covered_element', 'new_options', 'effective_date')
    def on_change_new_options(self):
        for elem in self.new_options:
            self.update_option(elem)
        self.new_options = self.new_options

    @classmethod
    def update_default_values(cls, wizard, endorsement, default_values):
        modified_covered_elements = [x for x in endorsement.covered_elements
            if x.action in ('add', 'update')]
        if not modified_covered_elements:
            return {}
        if len(modified_covered_elements) != 1:
            # TODO
            raise NotImplementedError
        covered_element = modified_covered_elements[0].covered_element
        tmp_instance = cls(**default_values)
        tmp_instance.covered_element = covered_element
        tmp_instance.effective_date = default_values['effective_date']
        update_dict = {
            'covered_element': covered_element.id,
            'new_options': [tmp_instance.update_option_dict(x.values)
                for x in modified_covered_elements[0].options
                if x.action == 'add'],
            }
        return update_dict

    def update_endorsement(self, endorsement, wizard):
        pool = Pool()
        EndorsementCoveredElement = pool.get(
            'endorsement.contract.covered_element')
        EndorsementCoveredElementOption = pool.get(
            'endorsement.contract.covered_element.option')
        good_endorsement = [x for x in endorsement.covered_elements
            if x.covered_element == self.covered_element]
        if not good_endorsement:
            good_endorsement = EndorsementCoveredElement(
                contract_endorsement=endorsement,
                relation=self.covered_element.id,
                definition=self.endorsement_definition,
                options=[],
                action='update',
                )
        else:
            good_endorsement = good_endorsement[0]
        option_endorsements = dict([(x.coverage, x)
                for x in good_endorsement.options
                if x.action == 'add' and 'coverage' in x.values])
        new_option_endorsements = [x for x in good_endorsement.options
            if x.action != 'add']
        for new_option in self.new_options:
            if new_option.coverage in option_endorsements:
                option_endorsement = option_endorsements[new_option.coverage]
                new_option_endorsements.append(option_endorsement)
                del option_endorsements[new_option.coverage]
            else:
                option_endorsement = EndorsementCoveredElementOption(
                    action='add', values={})
                new_option_endorsements.append(option_endorsement)
            for field in self.endorsement_part.option_fields:
                new_value = getattr(new_option, field.name, None)
                if isinstance(new_value, Model):
                    new_value = new_value.id
                option_endorsement.values[field.name] = new_value
        EndorsementCoveredElementOption.delete(option_endorsements.values())
        good_endorsement.options = new_option_endorsements

        good_endorsement.save()


class ExtraPremiumDisplayer(model.CoopView):
    'Extra Premium Displayer'

    __name__ = 'endorsement.contract.extra_premium.displayer'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', readonly=True)
    covered_element_endorsement = fields.Many2One(
        'endorsement.contract.covered_element', 'Covered Element',
        readonly=True)
    covered_element_name = fields.Char('Covered Element', readonly=True)
    option = fields.Many2One('contract.option', 'Option', readonly=True)
    option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option', 'Option Endorsement',
        readonly=True)
    option_name = fields.Char('Option', readonly=True)
    extra_premium = fields.One2Many('contract.option.extra_premium',
        None, 'Extra Premium')
    extra_premium_id = fields.Integer('Extra Premium Id')
    extra_premium_name = fields.Char('Extra Premium')
    to_delete = fields.Boolean('To Delete')
    to_add = fields.Boolean('To Add')
    to_update = fields.Boolean('To Update')


class ManageExtraPremium(model.CoopView, EndorsementWizardStepMixin):
    'Manage Extra Premium'

    __name__ = 'endorsement.contract.manage_extra_premium'

    extra_premiums = fields.One2Many(
        'endorsement.contract.extra_premium.displayer', None, 'Extra Premiums')

    @staticmethod
    def update_dict(to_update, key, value):
        # TODO : find a cleaner endorsement class detection
        to_update[key] = to_update[key + '_endorsement'] = None
        if hasattr(value, 'get_endorsed_record'):
            to_update[key + '_endorsement'] = value.id
            to_update[key] = value.relation
        else:
            to_update[key] = value.id
        to_update[key + '_name'] = value.rec_name

    @classmethod
    def _extra_premium_fields_to_extract(cls):
        return ['calculation_kind', 'capital_per_mil_rate', 'currency',
            'currency_digits', 'currency_symbol', 'duration', 'duration_unit',
            'end_date', 'flat_amount', 'is_discount', 'max_rate',
            'max_value', 'motive', 'option', 'rate', 'start_date',
            'time_limited']

    @classmethod
    def create_displayer(cls, extra_premium, template):
        ExtraPremium = Pool().get('contract.option.extra_premium')
        displayer = template.copy()
        if extra_premium.__name__ == 'endorsement.contract.extra_premium':
            if extra_premium.action == 'add':
                instance = ExtraPremium(**extra_premium.values)
                displayer['extra_premium_id'] = None
                displayer['to_add'] = True
            elif extra_premium.action == 'remove':
                instance = extra_premium.extra_premium
                displayer['extra_premium_id'] = instance.id
                displayer['to_delete'] = True
            elif extra_premium.action == 'update':
                instance = extra_premium.extra_premium
                displayer['extra_premium_id'] = instance.id
                for fname, fvalue in extra_premium.values.iteritems():
                    setattr(instance, fname, fvalue)
                displayer['to_update'] = True
        else:
            instance = extra_premium
            displayer['extra_premium_id'] = extra_premium.id
        displayer['extra_premium_name'] = instance.get_rec_name(None)
        displayer['extra_premium'] = [model.dictionarize(instance,
                cls._extra_premium_fields_to_extract())]
        return displayer

    @classmethod
    def update_default_values(cls, wizard, base_endorsement, default_values):
        # Base_endorsement may be the current new endorsement. But we also have
        # to look in wizard.endorsement.contract_endorsements to detect other
        # contracts that may be modified
        if not base_endorsement.id:
            # New endorsement, no need to look somewhere else.
            all_endorsements = [base_endorsement]
        else:
            all_endorsements = list(wizard.endorsement.contract_endorsements)
        displayers, template = [], {'to_delete': False, 'to_add': False,
            'to_update': False}
        for endorsement in all_endorsements:
            updated_struct = endorsement.updated_struct
            template['contract'] = endorsement.contract.id
            for covered_element, values in (
                    updated_struct['covered_elements'].iteritems()):
                cls.update_dict(template, 'covered_element', covered_element)
                for option, o_values in values['options'].iteritems():
                    cls.update_dict(template, 'option', option)
                    for extra_premium, ex_values in (
                            o_values['extra_premiums'].iteritems()):
                        displayers.append(cls.create_displayer(extra_premium,
                                template))
        return {'extra_premiums': displayers}

    def update_endorsement(self, base_endorsement, wizard):
        # Base_endorsement may be the current new endorsement. But we also have
        # to look in wizard.endorsement.contract_endorsements to detect other
        # contracts that may be modified
        if not base_endorsement.id:
            all_endorsements = {base_endorsement.contract.id: base_endorsement}
        else:
            all_endorsements = {x.contract.id: x
                for x in wizard.endorsement.contract_endorsements}
        pool = Pool()
        CoveredElementEndorsement = pool.get(
            'endorsement.contract.covered_element')
        OptionEndorsement = pool.get(
            'endorsement.contract.covered_element.option')
        ExtraPremiumEndorsement = pool.get(
            'endorsement.contract.extra_premium')
        ExtraPremium = pool.get('contract.option.extra_premium')
        new_covered_elements, new_options, to_create = {}, {}, []
        for elem in self.extra_premiums:
            if elem.to_delete:
                if elem.extra_premium_id:
                    ex_endorsement = ExtraPremiumEndorsement(action='remove',
                        extra_premium=elem.extra_premium_id)
                else:
                    continue
            elif elem.to_add:
                ex_endorsement = ExtraPremiumEndorsement(action='add',
                    values=elem.extra_premium[0]._save_values)
                ex_endorsement.values['start_date'] = self.effective_date
            else:
                base_instance = ExtraPremium(elem.extra_premium_id)
                update_values = {
                    k: v for k, v in
                    elem.extra_premium[0]._save_values.iteritems()
                    if getattr(base_instance, k, None) != v}
                if update_values:
                    ex_endorsement = ExtraPremiumEndorsement(action='update',
                        extra_premium=elem.extra_premium_id,
                        values=update_values)
                else:
                    continue
            if not (elem.option_endorsement or elem.option.id in new_options):
                option_endorsement = OptionEndorsement(action='update',
                    option=elem.option.id, extra_premiums=[])
                new_options[elem.option.id] = option_endorsement
                if not(elem.covered_element_endorsement or
                        elem.covered_element.id in new_covered_elements):
                    ce_endorsement = CoveredElementEndorsement(action='update',
                        options=[option_endorsement],
                        relation=elem.covered_element.id)
                    ctr_endorsement = all_endorsements[elem.contract.id]
                    if not ctr_endorsement.id:
                        ctr_endorsement.covered_elements = list(
                            ctr_endorsement.covered_elements) + [
                                ce_endorsement]
                    else:
                        ce_endorsement.contract_endorsement = \
                            ctr_endorsement.id
                    new_covered_elements[elem.covered_element.id] = \
                        ce_endorsement
                else:
                    ce_endorsement = (elem.covered_element_endorsement or
                        new_covered_elements[elem.covered_element.id])
                    if ce_endorsement.id:
                        option_endorsement.covered_element_endorsement = \
                            ce_endorsement.id
                    else:
                        ce_endorsement.options = list(
                            ce_endorsement.options) + [option_endorsement]
            else:
                option_endorsement = (elem.option_endorsement or
                    new_options[elem.option.id])
            if option_endorsement.id:
                ex_endorsement.covered_option_endorsement = \
                    option_endorsement.id
                to_create.append(ex_endorsement)
            else:
                option_endorsement.extra_premiums = list(
                    option_endorsement.extra_premiums) + [ex_endorsement]
        if to_create:
            ExtraPremiumEndorsement.create([x._save_values for x in to_create])
        if new_options:
            OptionEndorsement.create([x._save_values
                    for x in new_options.itervalues()
                    if getattr(x, 'covered_element_endorsement', None)])
        if new_covered_elements:
            CoveredElementEndorsement.create([x._save_values
                    for x in new_covered_elements
                    if getattr(x, 'contract_endorsement', None)])


class OptionSelector(model.CoopView):
    'Option Selector'

    __name__ = 'endorsement.option.selector'

    option_id = fields.Integer('Option Id')
    option_endorsement_id = fields.Integer('Endorsement Id')
    option_rec_name = fields.Char('Option', readonly=True)
    covered_element_id = fields.Integer('Covered Element Id')
    covered_element_endorsement_id = fields.Integer('Endorsement Id')
    covered_element_rec_name = fields.Char('Covered Element', readonly=True)
    selected = fields.Boolean('Selected')

    @classmethod
    def new_selector(cls, option):
        selector = {}
        if option.__name__ == 'contract.option':
            selector['option_id'] = option.id
        else:
            selector['option_endorsement_id'] = option.id
        selector['option_rec_name'] = option.rec_name
        return selector


class CoveredElementSelector(model.CoopView):
    'Covered Element Selector'

    __name__ = 'endorsement.covered_element.selector'

    covered_element_id = fields.Integer('Covered Element Id')
    covered_element_endorsement_id = fields.Integer('Endorsement Id')
    covered_element_rec_name = fields.Char('Covered Element', readonly=True)
    selected = fields.Boolean('Selected')

    @classmethod
    def new_selector(cls, covered_element):
        selector = {}
        if covered_element.__name__ == 'contract.covered_element':
            selector['covered_element_id'] = covered_element.id
        else:
            selector['covered_element_endorsement_id'] = covered_element.id
        selector['covered_element_rec_name'] = covered_element.rec_name
        return selector


class NewExtraPremium(model.CoopView):
    'New Extra Premium'

    __name__ = 'endorsement.contract.new_extra_premium'

    new_extra_premium = fields.One2Many('contract.option.extra_premium', None,
        'New Extra Premium')
    options = fields.One2Many('endorsement.option.selector', None, 'Options')
    covered_elements = fields.One2Many('endorsement.covered_element.selector',
        None, 'Covered Elements')

    @fields.depends('covered_elements', 'options')
    def on_change_covered_elements(self):
        for covered_element in self.covered_elements:
            for option in self.options:
                if (option.covered_element_id ==
                        covered_element.covered_element_id) and (
                        option.covered_element_endorsement_id ==
                        covered_element.covered_element_endorsement_id):
                    option.selected = covered_element.selected
        self.options = self.options

    @fields.depends('covered_elements')
    def on_change_options(self):
        for covered_element in self.covered_elements:
            covered_element.selected = False
        self.covered_elements = self.covered_elements

    @classmethod
    def _extra_premium_fields_to_extract(cls):
        return ['calculation_kind', 'capital_per_mil_rate', 'currency',
            'currency_digits', 'currency_symbol', 'duration', 'duration_unit',
            'end_date', 'flat_amount', 'is_discount', 'is_loan', 'max_rate',
            'max_value', 'motive', 'option', 'rate', 'start_date',
            'time_limited']

    def update_endorsement(self, wizard):
        all_endorsements = {x.contract.id: x
            for x in wizard.endorsement.contract_endorsements}
        pool = Pool()
        CoveredElementEndorsement = pool.get(
            'endorsement.contract.covered_element')
        OptionEndorsement = pool.get(
            'endorsement.contract.covered_element.option')
        ExtraPremiumEndorsement = pool.get(
            'endorsement.contract.extra_premium')
        CoveredElement = pool.get('contract.covered_element')
        new_covered_elements, new_options, to_create = {}, {}, []
        new_values = {
            'action': 'add',
            'values': model.dictionarize(self.new_extra_premium[0],
                self._extra_premium_fields_to_extract()),
            }
        for option_selector in self.options:
            if not option_selector.selected:
                continue
            if (not option_selector.option_endorsement_id and
                    option_selector.option_id not in new_options):
                option_endorsement = OptionEndorsement(action='update',
                    option=option_selector.option_id, extra_premiums=[])
                new_options[option_selector.option_id] = option_endorsement
                if (not option_selector.covered_element_endorsement_id and
                        option_selector.covered_element_id not in
                        new_covered_elements):
                    covered_element = CoveredElement(
                        option_selector.covered_element_id)
                    ce_endorsement = CoveredElementEndorsement(action='update',
                        options=[option_endorsement],
                        covered_element=covered_element.id,
                        contract_endorsement=all_endorsements[
                            covered_element.contract.id].id)
                    new_covered_elements[covered_element.id] = ce_endorsement
                elif option_selector.covered_element_endorsement_id:
                    option_endorsement.covered_element_endorsement = \
                        option_selector.covered_element_endorsement_id
                else:
                    covered_endorsement = new_covered_elements[
                        option_selector.covered_element_id]
                    covered_endorsement.options = list(
                        covered_endorsement.options) + [option_endorsement]

            save_values = new_values.copy()
            if option_selector.option_endorsement_id:
                save_values['covered_option_endorsement'] = \
                    option_selector.option_endorsement_id
                to_create.append(save_values)
            else:
                new_option = new_options[option_selector.option_id]
                new_option.extra_premiums = list(new_option.extra_premiums) + [
                    ExtraPremiumEndorsement(**save_values)]
        if to_create:
            ExtraPremiumEndorsement.create(to_create)
        if new_options:
            OptionEndorsement.create([x._save_values
                    for x in new_options.itervalues()
                    if getattr(x, 'covered_element_endorsement', None)])
        if new_covered_elements:
            CoveredElementEndorsement.create([x._save_values
                    for x in new_covered_elements.itervalues()
                    if getattr(x, 'contract_endorsement', None)])


class StartEndorsement:
    __name__ = 'endorsement.start'

    new_covered_element = StateView('contract.covered_element.new',
        'endorsement_insurance.new_covered_element_view_form', [
            Button('Previous', 'new_covered_element_previous',
                'tryton-go-previous'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'new_covered_element_next', 'tryton-go-next')])
    new_covered_element_previous = StateTransition()
    new_covered_element_next = StateTransition()
    new_option_covered_element = StateView(
        'contract.covered_element.add_option',
        'endorsement_insurance.add_option_to_covered_element_view_form', [
            Button('Previous', 'new_option_covered_element_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Next', 'new_option_covered_element_next',
                'tryton-go-next')])
    new_option_covered_element_previous = StateTransition()
    new_option_covered_element_next = StateTransition()
    manage_extra_premium = StateView(
        'endorsement.contract.manage_extra_premium',
        'endorsement_insurance.manage_extra_premium_view_form', [
            Button('Previous', 'manage_extra_premium_previous',
                'tryton-go-previous'),
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('New Extra Premium', 'start_new_extra_premium',
                'tryton-new'),
            Button('Next', 'manage_extra_premium_next',
                'tryton-go-next')])
    manage_extra_premium_previous = StateTransition()
    start_new_extra_premium = StateTransition()
    new_extra_premium = StateView('endorsement.contract.new_extra_premium',
        'endorsement_insurance.new_extra_premium_view_form', [
            Button('Cancel', 'manage_extra_premium', 'tryton-go-previous'),
            Button('Continue', 'add_extra_premium', 'tryton-go-next',
                default=True)])
    add_extra_premium = StateTransition()
    manage_extra_premium_next = StateTransition()

    def set_main_object(self, endorsement):
        super(StartEndorsement, self).set_main_object(endorsement)
        endorsement.covered_elements = []

    def update_default_covered_element_from_endorsement(self, endorsement,
            default_values):
        if not getattr(endorsement, 'covered_elements', None):
            return
        default_covered_element = default_values['covered_elements'][0]
        # TODO : improve for multiple covered_elements
        for covered_element in endorsement.covered_elements:
            if covered_element.action == 'add':
                default_covered_element.update(covered_element.values)
                break

    def default_new_covered_element(self, name):
        endorsement_part = self.get_endorsement_part_for_state(
            'new_covered_element')
        contract = self.get_endorsed_object(endorsement_part)
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'product': self.select_endorsement.product.id,
            'start_date': endorsement_date,
            'contract': contract.id,
            'possible_item_desc': [x.id for x in contract.possible_item_desc],
            'extra_data': contract.extra_data,
            }
        result['covered_elements'] = [{
                'start_date': endorsement_date,
                'item_desc': (result['possible_item_desc'] or [None])[0],
                'main_contract': contract.id,
                'product': result['product'],
                }]
        new_covered_element = Pool().get('contract.covered_element')(
            **result['covered_elements'][0])
        new_covered_element.on_change_item_desc()
        result['covered_elements'][0].update(
            new_covered_element._default_values)
        endorsement = self.get_endorsement_for_state('new_covered_element')
        if endorsement:
            self.update_default_covered_element_from_endorsement(endorsement,
                result)
        return result

    def transition_new_covered_element_next(self):
        self.end_current_part('new_covered_element')
        return self.get_next_state('new_covered_element')

    def transition_new_covered_element_previous(self):
        self.end_current_part('new_covered_element')
        return self.get_state_before('new_covered_element')

    def default_new_option_covered_element(self, name):
        endorsement_part = self.get_endorsement_part_for_state(
            'new_option_covered_element')
        contract = self.get_endorsed_object(endorsement_part)
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            'possible_covered_elements': [
                x.id for x in contract.covered_elements],
            }
        if len(result['possible_covered_elements']) == 1:
            result['covered_element'] = result['possible_covered_elements'][0]
        endorsement = self.get_endorsements_for_state(
            'new_option_covered_element')
        if endorsement:
            NewOptionState = Pool().get('contract.covered_element.add_option')
            result.update(NewOptionState.update_default_values(self,
                    endorsement[0], result))
        return result

    def transition_new_option_covered_element_next(self):
        self.end_current_part('new_option_covered_element')
        return self.get_next_state('new_option_covered_element')

    def transition_new_option_covered_element_previous(self):
        self.end_current_part('new_option_covered_element')
        return self.get_state_before('new_option_covered_element')

    def default_manage_extra_premium(self, name):
        ContractEndorsement = Pool().get('endorsement.contract')
        endorsement_part = self.get_endorsement_part_for_state(
            'manage_extra_premium')
        endorsement_date = self.select_endorsement.effective_date
        result = {
            'endorsement_part': endorsement_part.id,
            'effective_date': endorsement_date,
            }
        endorsements = self.get_endorsements_for_state('manage_extra_premium')
        if not endorsements:
            if self.select_endorsement.contract:
                endorsements = [ContractEndorsement(definition=self.definition,
                        endorsement=self.endorsement,
                        contract=self.select_endorsement.contract)]
            else:
                return result
        ManageExtraPremium = Pool().get(
            'endorsement.contract.manage_extra_premium')
        result.update(ManageExtraPremium.update_default_values(self,
                endorsements[0], result))
        return result

    def transition_start_new_extra_premium(self):
        self.end_current_part('manage_extra_premium')
        return 'new_extra_premium'

    def default_new_extra_premium(self, name):
        pool = Pool()
        CoveredElementSelector = pool.get(
            'endorsement.covered_element.selector')
        OptionSelector = pool.get('endorsement.option.selector')
        endorsements = list(self.endorsement.contract_endorsements)
        default_values = {
            'new_extra_premium': [
                {'start_date': self.select_endorsement.effective_date}],
            'covered_elements': [],
            'options': [],
            }

        for endorsement in endorsements:
            updated_struct = endorsement.updated_struct
            for covered_element, values in (
                    updated_struct['covered_elements'].iteritems()):
                default_values['covered_elements'].append(
                    CoveredElementSelector.new_selector(covered_element))
                for option, o_values in values['options'].iteritems():
                    default_values['options'].append(
                        OptionSelector.new_selector(option))
                    default_values['options'][-1].update(
                        default_values['covered_elements'][-1])
        return default_values

    def transition_add_extra_premium(self):
        self.new_extra_premium.update_endorsement(self)
        return 'manage_extra_premium'

    def transition_manage_extra_premium_previous(self):
        self.end_current_part('manage_extra_premium')
        return self.get_state_before('manage_extra_premium')

    def transition_manage_extra_premium_next(self):
        self.end_current_part('manage_extra_premium')
        return self.get_next_state('manage_extra_premium')
