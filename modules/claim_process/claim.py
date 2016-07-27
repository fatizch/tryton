# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.modules.process import ClassAttr
from trytond.modules.cog_utils import utils, fields, model
from trytond.modules.process_cog import CogProcessFramework
from trytond.modules.process_cog import ProcessFinder, ProcessStart
from trytond.wizard import Button, StateTransition, StateAction


__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    'Loss',
    'Process',
    'ProcessLossDescRelation',
    'ClaimDeclareFindProcess',
    'ClaimDeclare',
    'CloseClaim',
    'ClaimDeclarationElement'
    ]


class Claim(CogProcessFramework):
    'Claim'

    __metaclass__ = ClassAttr
    __name__ = 'claim'

    contact_history = fields.Function(
        fields.One2Many('party.interaction', '', 'History',
            depends=['claimant']),
        'on_change_with_contact_history')
    main_loss_description = fields.Function(
        fields.Char('Loss Description'),
        'get_main_loss_description')

    @fields.depends('claimant')
    def on_change_with_contact_history(self, name=None):
        if not (hasattr(self, 'claimant') and self.claimant):
            return []
        ContactHistory = Pool().get('party.interaction')
        return [x.id for x in ContactHistory.search(
                [('party', '=', self.claimant)])]

    def get_main_loss_description(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Transaction().language
        if not self.losses:
            return ''
        loss = self.losses[0]
        return '%s (%s - %s)' % (loss.loss_desc.name, Lang.strftime(
                loss.start_date, lang, '%d/%m/%Y') if loss.start_date else '',
            Lang.strftime(loss.end_date, lang, '%d/%m/%Y')
            if loss.end_date else '')

    def init_declaration_document_request(self):
        pool = Pool()
        DocumentRequestLine = pool.get('document.request.line')
        DocumentDescription = pool.get('document.description')
        documents = []
        for loss in self.losses:
            if not loss.loss_desc:
                continue
            loss_docs = loss.loss_desc.get_documents()
            documents.extend(loss_docs)
            for delivered in loss.services:
                if not (hasattr(delivered, 'benefit') and delivered.benefit):
                    continue
                args = {}
                delivered.init_dict_for_rule_engine(args)
                docs = delivered.benefit.calculate_required_documents(args)
                docs = DocumentDescription.search(
                    [('code', 'in', docs.keys())])
                documents.extend(docs)
        existing_document_desc = [request.document_desc
            for request in self.document_request_lines]
        to_save = []
        documents = list(set(documents))
        for desc in documents:
            if desc in existing_document_desc:
                existing_document_desc.remove(desc)
                continue
            line = DocumentRequestLine()
            line.document_desc = desc
            line.for_object = '%s,%s' % (self.__name__, self.id)
            line.claim = self
            to_save.append(line)
        if to_save:
            DocumentRequestLine.save(to_save)

    def reject_and_close_claim(self):
        self.status = 'closed'
        self.end_date = utils.today()
        return True

    def add_new_loss(self, loss_desc_code, parameters=None):
        for loss in self.losses:
            if (not loss.end_date and loss.loss_desc and
                    loss.loss_desc.code == loss_desc_code):
                return
        pool = Pool()
        Loss = pool.get('claim.loss')
        loss = Loss()
        loss.claim = self
        loss.init_loss(loss_desc_code, parameters)
        self.losses = self.losses + (loss, )

    def deliver_services(self):
        pool = Pool()
        Option = pool.get('contract.option')
        Services = pool.get('claim.service')
        to_save = []
        for loss in self.losses:
            if loss.services:
                continue
            option_benefit = loss.get_possible_benefits()
            for option_id, benefits in option_benefit.iteritems():
                for benefit in benefits:
                    loss.init_services(Option(option_id), [benefit])
                    to_save.extend(loss.services)
        if to_save:
            Services.save(to_save)


class Loss:
    __name__ = 'claim.loss'

    # The Benefit to deliver is just a shortcut to ease delivered service
    # creation. it should not be used once a service has been created
    benefit_to_deliver = fields.Function(
        fields.Many2One('benefit', 'Benefit',
            # domain=[('id', 'in', Eval('benefits'))],
            depends=['benefits']),
        'get_benefit_to_deliver', 'setter_void')
    benefits = fields.Function(
        fields.One2Many('benefit', None, 'Benefits'),
        'on_change_with_benefits')

    def init_loss(self, loss_desc_code, parameters=None):
        pool = Pool()
        LossDesc = pool.get('benefit.loss.description')
        self.loss_desc, = LossDesc.search([('code', '=', loss_desc_code)])
        self.event_desc = self.loss_desc.event_descs[0]
        self.extra_data = utils.init_extra_data(self.loss_desc.extra_data_def)
        if not parameters:
            return
        for arg, value in parameters.iteritems():
            setattr(self, arg, value)

    def get_possible_benefits(self):
        if not self.claim or not self.loss_desc:
            return {}
        res = {}
        if self.claim.main_contract:
            contracts = [self.claim.main_contract]
        else:
            contracts = self.claim.get_possible_contracts(
                at_date=self.get_date())
        for contract in contracts:
            for covered_element in contract.covered_elements:
                for option in covered_element.options:
                    benefits = option.get_possible_benefits(self)
                    if benefits:
                        res[option.id] = benefits
        return res

    @fields.depends('loss_desc', 'event_desc', 'claim')
    def on_change_with_benefits(self, name=None):
        res = []
        for x in self.get_possible_benefits().values():
            res += [benefit.id for benefit in x]
        return list(set(res))

    def get_benefit_to_deliver(self, name):
        if (len(self.services) == 1
                and self.services[0].status == 'calculating'):
            return self.services[0].benefit.id

    @fields.depends('benefit_to_deliver', 'services', 'claim', 'loss_desc',
        'event_desc')
    def on_change_benefit_to_deliver(self):
        pool = Pool()
        Service = pool.get('claim.service')
        if not self.services:
            self.services = [Service(status='calculating')]
        elif not((len(self.services) == 1
                and self.services[0].status == 'calculating')):
            return
        service = self.services[0]
        service.benefit = (self.benefit_to_deliver if self.benefit_to_deliver
            else None)
        service.extra_data = (utils.init_extra_data(
                self.benefit_to_deliver.extra_data_def)
            if self.benefit_to_deliver else {})
        contract = None
        if self.claim.main_contract:
            contract = self.claim.main_contract
        else:
            contracts = self.claim.get_possible_contracts(self.get_date())
            if len(contracts) == 1:
                contract = contracts[0]
        if contract:
            service.contract = contract
            if self.benefit_to_deliver:
                options = []
                for covered_element in contract.covered_elements:
                    for option in covered_element.options:
                        if self.benefit_to_deliver in \
                                option.get_possible_benefits(self):
                            options.append(option)
                if len(set(options)) == 1:
                    service.option = options[0]
        self.services = self.services


class Process:
    __name__ = 'process'

    for_loss_descs = fields.Many2Many('process-benefit.loss.description',
        'process', 'loss_desc', 'Loss Description')

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('claim_declaration', 'Claim Declaration'))
        cls.kind.selection.append(('claim_reopening', 'Claim Reopening'))
        cls.kind.selection[:] = list(set(cls.kind.selection))


class ProcessLossDescRelation(model.CoopSQL):
    'Process Loss Desc Relation'

    __name__ = 'process-benefit.loss.description'

    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description',
        ondelete='CASCADE', required=True, select=True)
    process = fields.Many2One('process', 'Process', ondelete='RESTRICT',
        required=True)


class ClaimDeclarationElement(model.CoopView):
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

    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')
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
                [('kind', '=', Eval('claim_process_type'))])]
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
        available_claims = Claim.search([
                ('claimant', '=', self.party)],
            order=[('declaration_date', 'DESC')])
        elements = []
        selected = False
        for claim in available_claims:
            element = Element.from_claim(claim)
            if not selected and claim.status == 'open':
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
        cls.process_parameters.buttons[1].state = 'confirm_declaration'
        cls.process_parameters.buttons.insert(
            1, Button('Close claims', 'close_claim', 'tryton-delete'))
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


class CloseClaim:
    'Clase Claims'

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
