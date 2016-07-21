# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder, Eval
from trytond.wizard import Wizard, StateAction, StateView, Button, \
    StateTransition
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model

__all__ = [
    'DisplayEnrollments',
    'AddEnrollment',
    'EnrollmentCreation',
    ]


class DisplayEnrollments(Wizard):
    'Display Enrollments'

    __name__ = 'contract.display_enrollments'

    start_state = 'display'
    display = StateAction('contract_group.act_display_enrollment_form')

    @classmethod
    def __setup__(cls):
        super(DisplayEnrollments, cls).__setup__()
        cls._error_messages.update({
                'wrong_active_model': 'Display Enrollment wizard must be '
                'started from a contract',
                })

    def do_display(self, action):
        pool = Pool()
        Contract = pool.get('contract')
        if Transaction().context.get('active_model') != 'contract':
            self.raise_user_error('wrong_active_model')
        contract = Contract(Transaction().context['active_id'])
        covered_ids = [sub_covered.id for covered in contract.covered_elements
            for sub_covered in covered.sub_covered_elements]

        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode([('id', 'in', covered_ids)])
        return action, {}


class EnrollmentCreation(model.CoopView):
    'Enrollment Creation'

    __name__ = 'contract.enrollment_creation'

    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', required=True, depends=['possible_covered_element'],
        domain=[('id', 'in', Eval('possible_covered_element'))])
    possible_covered_element = fields.Many2Many('contract.covered_element',
        None, None, 'Possible Covered Elements')
    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        required=True, depends=['possible_item_desc'],
        domain=[('id', 'in', Eval('possible_item_desc'))])
    possible_item_desc = fields.Many2Many('offered.item.description', None,
        None, 'Possible Item Desc')
    employee = fields.Many2One('party.party', 'Employee',
        domain=[('is_person', '=', True)])
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={
            'invisible': ~Eval('extra_data'),
            },
        depends=['extra_data'])
    contract = fields.Many2One('contract', 'Contract', required=True,
        readonly=True)

    @fields.depends('contract', 'covered_element')
    def on_change_covered_element(self):
        if not self.covered_element or not self.contract:
            self.possible_item_desc = None
            self.item_desc = None
            self.extra_data = {}
            return
        self.possible_item_desc = [item_desc
            for item_desc in self.contract.covered_elements[0].item_desc.
            sub_item_descs]
        if not self.possible_item_desc:
            self.item_desc = None
        else:
            self.item_desc = self.possible_item_desc[0]
        self.extra_data = self.contract.product.get_extra_data_def(
            'covered_element', {}, self.contract.start_date,
            item_desc=self.item_desc)

    @fields.depends('contract', 'item_desc')
    def on_change_item_desc(self):
        if not self.contract:
            self.extra_data = {}
            return
        self.extra_data = self.contract.product.get_extra_data_def(
            'covered_element', {}, self.contract.start_date,
            item_desc=self.item_desc)


class AddEnrollment(Wizard):
    'Add Enrollment'

    __name__ = 'contract.add_enrollment'

    start_state = 'enrollment_creation'
    enrollment_creation = StateView('contract.enrollment_creation',
        'contract_group.enrollment_creation_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_enrollment', 'tryton-go-next',
                default=True)])
    create_enrollment = StateTransition()

    @classmethod
    def __setup__(cls):
        super(AddEnrollment, cls).__setup__()
        cls._error_messages.update({
                'wrong_active_model': 'Enrollment wizard must be started from'
                ' a contract',
                'wrong_contract': 'Selected contract is not a group contract'
                ' or no covered element with sub element is defined in it'
                })

    def default_enrollment_creation(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        if Transaction().context.get('active_model') != 'contract':
            self.raise_user_error('wrong_active_model')
        contract_id = Transaction().context.get('active_id', None)
        contract = Contract(contract_id)
        if (not contract.is_group or not contract.covered_elements[0] or not
                contract.covered_elements[0].item_desc.sub_item_descs):
            self.raise_user_error('wrong_contract')
        item_desc = contract.covered_elements[0].item_desc.sub_item_descs[0]
        extra_data = contract.product.get_extra_data_def(
            'covered_element', {}, contract.start_date, item_desc=item_desc)
        return {
            'possible_covered_element': [covered.id
                for covered in contract.covered_elements],
            'item_desc': item_desc.id,
            'covered_element': contract.covered_elements[0].id,
            'contract': contract.id,
            'extra_data': extra_data,
            }

    def init_enrollments(self):
        covered = Pool().get('contract.covered_element')()
        pool = Pool()
        Version = pool.get('contract.covered_element.version')
        covered.party = self.enrollment_creation.employee
        covered.parent = self.enrollment_creation.covered_element
        covered.item_desc = self.enrollment_creation.item_desc
        covered.versions = [Version(
                extra_data=self.enrollment_creation.extra_data)]
        return [covered]

    def transition_create_enrollment(self):
        Covered = Pool().get('contract.covered_element')
        covereds = self.init_enrollments()
        Covered.save(covereds)
        return 'end'
