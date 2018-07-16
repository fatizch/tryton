# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateAction

from trytond.modules.coog_core import fields, model
from trytond.modules.process_cog.process import ProcessFinder, ProcessStart

__all__ = [
    'Process',
    'ProcessLossDescRelation',
    'ClaimDeclareFindProcess',
    'ClaimDeclare',
    'CloseClaim',
    'ClaimDeclarationElement'
    ]


class Process:
    __metaclass__ = PoolMeta
    __name__ = 'process'

    for_loss_descs = fields.Many2Many('process-benefit.loss.description',
        'process', 'loss_desc', 'Loss Description', states={
            'invisible': ~Eval('kind').in_(
                ['claim_declaration', 'claim_reopening'])},
        depends=['kind'])

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('claim_declaration', 'Claim Declaration'))
        cls.kind.selection.append(('claim_declaration_and_reopening',
            'Claim Declaration and Reopening'))
        cls.kind.selection.append(('claim_reopening', 'Claim Reopening'))
        cls.kind.selection[:] = list(set(cls.kind.selection))

    @classmethod
    def _export_light(cls):
        return super(Process, cls)._export_light() | set(['for_loss_descs'])


class ProcessLossDescRelation(model.CoogSQL):
    'Process Loss Desc Relation'

    __name__ = 'process-benefit.loss.description'

    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description',
        ondelete='CASCADE', required=True, select=True)
    process = fields.Many2One('process', 'Process', ondelete='RESTRICT',
        required=True)


class ClaimDeclarationElement(model.CoogView):
    'Claim Declaration Element'

    __name__ = 'claim.declare.element'

    select = fields.Boolean('Select')
    claim = fields.Many2One('claim', 'Claim', readonly=True)
    name = fields.Char('Name', readonly=True)
    declaration_date = fields.Date('Declaration Date', readonly=True)
    end_date = fields.Date('End Date', readonly=True)
    status = fields.Char('Status', readonly=True)
    sub_status = fields.Many2One(
        'claim.sub_status', 'Status details', readonly=True)
    losses_summary = fields.Text('Losses Summary', readonly=True)

    @classmethod
    def from_claim(cls, claim):
        return {
            'select': False,
            'claim': claim.id,
            'name': claim.name,
            'declaration_date': claim.declaration_date,
            'end_date': claim.end_date,
            'status': claim.status_string,
            'sub_status': claim.sub_status.id if claim.sub_status else None,
            'losses_summary': '\n'.join([l.rec_name for l in claim.losses]),
            }


class ClaimDeclareFindProcess(ProcessStart):
    'Claim Declare Find Process'

    __name__ = 'claim.declare.find_process'

    party = fields.Many2One('party.party', 'Party', required=True,
        ondelete='SET NULL')
    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description')
    claims = fields.One2Many('claim.declare.element', None, 'Select claims')
    claim_process_type = fields.Char('Claim Process Type', readonly=True)
    claim_current_process = fields.Integer('Current Process Id',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(ClaimDeclareFindProcess, cls).__setup__()
        cls.good_process.states['invisible'] = False

    @classmethod
    def build_process_domain(cls):
        res = super(ClaimDeclareFindProcess, cls).build_process_domain()
        res += [If(Bool(Eval('loss_desc')),
                [('for_loss_descs', '=', Eval('loss_desc'))],
                []),
            If(Eval('claim_current_process', 0) != 0,
                [('id', '=', Eval('claim_current_process'))],
                ['OR', [('kind', '=', 'claim_declaration_and_reopening')],
                    [('kind', '=', Eval('claim_process_type'))],
                ])]
        return res

    @fields.depends('party', 'claims')
    def on_change_with_claim_process_type(self, name=None):
        for claim in self.claims:
            if claim.select:
                return 'claim_reopening'
        return 'claim_declaration'

    @fields.depends('party', 'claims')
    def on_change_with_claim_current_process(self, name=None):
        for claim in self.claims:
            if claim.select and claim.claim.current_state:
                return claim.claim.current_state.process.id
        return 0

    @classmethod
    def default_party(cls):
        return Transaction().context.get('party', None)

    @classmethod
    def default_loss_desc(cls):
        return Transaction().context.get('loss_desc', None)

    @classmethod
    def build_process_depends(cls):
        res = super(ClaimDeclareFindProcess, cls).build_process_depends()
        res += ['claims', 'party', 'loss_desc', 'claim_process_type',
            'claim_current_process']
        return res

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'claim')])[0].id

    @fields.depends('claims', 'party')
    def on_change_party(self):
        pool = Pool()
        Claim = pool.get('claim')
        Element = pool.get('claim.declare.element')
        if not self.party:
            self.claims = []
            return

        force_claim = Transaction().context.get('force_claim', None)
        if (not force_claim and
                Transaction().context.get('active_model', None) == 'claim'):
            force_claim = Transaction().context.get('active_id', None)
        available_claims = Claim.search([
                ('claimant', '=', self.party)],
            order=[('declaration_date', 'DESC')])
        elements = []
        selected = False
        for claim in available_claims:
            element = Element.from_claim(claim)
            if ((not force_claim and not selected and claim.status in ('open',
                        'reopened'))
                    or (force_claim and claim.id == force_claim)):
                selected = True
                element['select'] = True
            elements.append(element)
        self.claims = elements

    @fields.depends('claims', 'party', 'loss_desc', 'claim_process_type',
        'claim_current_process')
    def on_change_with_good_process(self):
        return super(ClaimDeclareFindProcess,
            self).on_change_with_good_process()


class ClaimDeclare(ProcessFinder):
    'Claim Declare'

    __name__ = 'claim.declare'

    close_claim = StateAction('claim_process.act_close_claim_wizard')
    confirm_declaration = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ClaimDeclare, cls).__setup__()
        buttons = list(cls.process_parameters.buttons)
        filtered_buttons = [b for b in buttons
            if b.state != 'confirm_declaration']
        confirm_buttons = [b for b in buttons
            if b.state == 'confirm_declaration']
        cls.process_parameters.buttons = filtered_buttons
        # We ensured that we will have only one button_confirm
        # after modifying the buttons
        if confirm_buttons:
            cls.process_parameters.buttons.append(confirm_buttons[0])
        if 'Close Claims' not in [b.string for b in
                cls.process_parameters.buttons]:
            cls.process_parameters.buttons.insert(
                1, Button('Close Claims', 'close_claim', 'tryton-delete'))
        cls._error_messages.update({
                'no_claim_selected':
                'You must select at least one open claim.',
                'open_claims':
                'There are claim\'s still open.',
                'declare_multiple_selected':
                'You can only reopen one claim at a time.',
                'missing_loss_desc': 'Missing Loss Description',
                })

    @classmethod
    def get_parameters_model(cls):
        return 'claim.declare.find_process'

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'claim_process',
            'declaration_process_parameters_form')

    def default_process_parameters(self, name):
        active_model = Transaction().context.get('active_model', None)
        if active_model == 'party.party':
            return {
                'party': Transaction().context.get('active_id', None),
                }
        elif active_model == 'contract':
            contract_id = Transaction().context.get('active_id', None)
            contract = Pool().get('contract')(contract_id)
            if contract and contract.subscriber:
                return {
                    'party': contract.subscriber.id,
                    }
        elif active_model == 'claim':
            claim_id = Transaction().context.get('active_id', None)
            claim = Pool().get('claim')(claim_id)
            return {
                'party': claim.claimant.id,
                }

        return {}

    def transition_confirm_declaration(self):
        open_claims = []
        selected_claims = []
        for claim in self.process_parameters.claims:
            if claim.claim.status in ('open', 'reopened'):
                open_claims.append(claim)
            if claim.select is True:
                selected_claims.append(claim)
        if len(selected_claims) > 1:
            self.raise_user_error('declare_multiple_selected')
        if open_claims and len(open_claims) != len(selected_claims):
            self.raise_user_warning(str(open_claims), 'open_claims')
        return 'action'

    def do_close_claim(self, action):
        selected_claims = []
        for claim in self.process_parameters.claims:
            if claim.select and claim.claim.status in ('open', 'reopened'):
                selected_claims.append(claim)
        if not selected_claims:
            self.raise_user_error('no_claim_selected')
        return action, {
            'extra_context': {
                'last_party': self.process_parameters.party.id,
                'loss_desc': self.process_parameters.loss_desc.id
                if self.process_parameters.loss_desc else None},
            'ids': [claim.claim.id for claim in selected_claims],
            'model': 'claim'}

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ClaimDeclare,
            self).init_main_object_from_process(obj, process_param)
        if res:
            obj.claimant = process_param.party
            obj.declaration_date = obj.default_declaration_date()
            obj.losses = []
            possible_contracts = obj.get_possible_contracts()
            if len(possible_contracts) == 1:
                obj.main_contract = possible_contracts[0]
        return res, errs

    def search_main_object(self):
        for claim in self.process_parameters.claims:
            if claim.select is True:
                return claim.claim
        return None

    def update_main_object(self, main_obj):
        if main_obj.status == 'closed':
            main_obj.reopen_claim()
        return main_obj

    def finalize_main_object(self, obj):
        document_reception = Transaction().context.get(
            'current_document_reception', None)
        if not document_reception:
            return
        document = Pool().get('document.reception')(document_reception)
        document.transfer(obj)


class CloseClaim:
    'Clase Claims'

    __metaclass__ = PoolMeta
    __name__ = 'claim.close'

    process = StateAction('claim_process.declaration_process_launcher')

    def transition_apply_sub_status(self):
        super(CloseClaim, self).transition_apply_sub_status()
        if Transaction().context.get('last_party', None):
            return 'process'
        return 'end'

    def do_process(self, action):
        ctx = Transaction().context
        party_id = ctx.get('last_party', None)
        prejudice_type = ctx.get('loss_desc', None)
        return action, {
            'extra_context': {
                'party': party_id,
                'loss_desc': prejudice_type}}
