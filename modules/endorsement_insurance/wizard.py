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

    @fields.depends('covered_element', 'new_options')
    def on_change_covered_element(self):
        if not self.covered_element:
            return {
                'existing_options': [],
                'new_options': {
                    'remove': [x.id for x in self.new_options]},
                'possible_coverages': [],
                }
        Coverage = Pool().get('offered.option.description')
        result = {
            'existing_options': [x.id for x in self.covered_element.options],
            }
        possible_coverages = list(
            set([x.id for x in Coverage.search(
                        Coverage.get_possible_coverages_clause(
                            self.covered_element, self.effective_date))]) -
            set([x.coverage.id for x in self.covered_element.options]))
        result['possible_coverages'] = possible_coverages
        return result

    def update_option_dict(self, option_dict):
        contract = self.covered_element.contract
        option_dict.update({
                'covered_element': self.covered_element.id,
                'product': contract.product.id,
                'start_date': self.effective_date,
                'appliable_conditions_date':
                contract.appliable_conditions_date,
                'parties': [x.id for x in self.covered_element.parties],
                'all_extra_datas': self.covered_element.all_extra_datas,
                'status': 'quote',
                })
        return option_dict

    @fields.depends('covered_element', 'new_options', 'effective_date')
    def on_change_new_options(self):
        to_update = []
        for elem in self.new_options:
            to_update.append(self.update_option_dict({'id': elem.id}))
        if to_update:
            return {'new_options': {'update': to_update}}
        return {}

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
        return  update_dict

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
            if x.action !=  'add']
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
        result['covered_elements'][0].update(
            new_covered_element.on_change_item_desc())
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
