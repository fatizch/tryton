from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, StateTransition, Button
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import EndorsementWizardStepMixin


__metaclass__ = PoolMeta
__all__ = [
    'NewCoveredElement',
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
