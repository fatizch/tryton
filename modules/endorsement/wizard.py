from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.wizard import StateAction

from trytond.modules.coop_utils import model, fields

__all__ = [
    'EndorsementSelection',
    'EndorsementLauncher',
]


class EndorsementSelection(model.CoopView):
    'Endorsement Selection'

    __name__ = 'endorsement.wizard.selection'

    contract = fields.Many2One('contract.contract', 'Contract', states={
            'readonly': ~Eval('to_select')}, depends=['to_select'],
        on_change=['contract'])
    to_select = fields.Boolean('Select Contract', states={'invisible': True})
    selected_product = fields.Many2One('offered.product', 'Product',
        states={'invisible': ~Eval('contract'), 'readonly': True})
    template = fields.Many2One('endorsement.template', 'Endorsement Template',
        states={'invisible': ~Eval('selected_product')},
        domain=[('products', '=', Eval('selected_product'))],
        on_change=['template'],
        depends=['selected_product', 'contract'])
    template_description = fields.Text('Template Description',
        states={'readonly': True})
    endorsement = fields.Many2One('endorsement', 'Endorsement',
        states={'invisible': True})

    def on_change_contract(self):
        if not self.contract:
            return {
                'selected_product': None,
                'template': None,
                'template_description': None,
            }
        result = {
            'selected_product': self.contract.offered.id,
        }
        try:
            template = self.contract.offered.endorsement_templates[0]
            result['template'] = template.id
            result['template_description'] = template.description
        except IndexError:
            result['template'] = None
            result['template_description'] = ''
        return result

    def on_change_template(self, name):
        if not self.template:
            return {'template_description': ''}
        return self.template.description


class EndorsementLauncher(Wizard):
    'Endorsement Launcher'

    __name__ = 'endorsement.wizard.launcher'

    start_state = 'select_endorsement'
    select_endorsement = StateView('endorsement.wizard.selection',
        'endorsement.wizard_launcher_selection_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'prepare_endorsement', 'tryton-go-next',
                states={'readonly': ~Eval('template')})])
    prepare_endorsement = StateTransition()
    show_endorsement = StateAction('endorsement.act_endorsement_form')

    def default_select_endorsement(self, name):
        model_name = Transaction().context.get('active_model')
        target_id = Transaction().context.get('active_id')
        if model_name != 'contract.contract' or not target_id:
            return {'to_select': True}
        Contract = Pool().get(model_name)
        contract = Contract(target_id)
        result = {
            'contract': target_id,
            'to_select': False,
            'selected_product': contract.offered.id,
        }
        try:
            template = contract.offered.endorsement_templates[0]
            result['template'] = template.id
            result['template_description'] = template.description
        except IndexError:
            result['template'] = None
            result['template_description'] = ''
        return result

    def transition_prepare_endorsement(self):
        Endorsement = Pool().get('endorsement')
        new_endorsement = Endorsement()
        new_endorsement.contract = self.select_endorsement.contract
        self.select_endorsement.template.init_endorsement(new_endorsement)
        new_endorsement.save()
        self.select_endorsement.endorsement = new_endorsement
        return 'show_endorsement'

    def do_show_endorsement(self, action):
        views = action['views']
        if len(views) > 1:
            for view in views:
                if view[1] == 'form':
                    action['views'] = [view]
                    break
        return (action, {
                'id': self.select_endorsement.endorsement.id,
                'model': 'endorsement',
                'res_id': self.select_endorsement.endorsement.id,
                'res_model': 'endorsement'})
