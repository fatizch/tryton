from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction

from trytond.modules.process import ClassAttr
from trytond.modules.cog_utils import utils, fields, model
from trytond.modules.process_cog import CogProcessFramework
from trytond.modules.process_cog import ProcessFinder, ProcessStart


__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    'Loss',
    'Process',
    'ProcessLossDescRelation',
    'ClaimDeclareFindProcess',
    'ClaimDeclare',
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
    delivered_services = fields.Function(
        fields.One2Many('claim.service', None, 'Claim Services'),
        'get_delivered_services', setter='set_delivered_services')

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

    def get_delivered_services(self, name):
        return [d.id for loss in self.losses for d in loss.services]

    @classmethod
    def set_delivered_services(cls, claims, name, value):
        pool = Pool()
        Service = pool.get('claim.service')
        for action in value:
            if action[0] == 'write':
                objects = [Service(id_) for id_ in action[1]]
                Service.write(objects, action[2])
            elif action[0] == 'delete':
                objects = [Service(id_) for id_ in action[1]]
                Service.delete(objects)

    def init_declaration_document_request(self):
        pool = Pool()
        DocumentRequestLine = pool.get('document.request.line')
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
                documents.extend(docs)
        existing_document_desc = [request.document_desc
            for request in self.document_request_lines]
        documents = list(set(documents))
        for desc in documents:
            if desc in existing_document_desc:
                existing_document_desc.remove(desc)
                continue
            line = DocumentRequestLine()
            line.document_desc = desc
            line.for_object = '%s,%s' % (self.__name__, self.id)
            line.save()

    def reject_and_close_claim(self):
        self.status = 'closed'
        self.end_date = utils.today()
        return True

    def init_first_loss(self):
        pool = Pool()
        Loss = pool.get('claim.loss')
        LossDesc = pool.get('benefit.loss.description')
        if self.losses:
            return
        loss_descs = LossDesc.search([])
        if loss_descs:
            loss_desc = loss_descs[0]
            event_desc = loss_desc.event_descs[0]
            self.losses = [Loss(loss_desc=loss_desc, event_desc=event_desc)]

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


class ClaimDeclareFindProcess(ProcessStart):
    'Claim Declare Find Process'

    __name__ = 'claim.declare.find_process'

    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')
    claim = fields.Many2One('claim', 'Claim',
        domain=[('id', 'in', Eval('claims'))], depends=['claims'],
        ondelete='SET NULL')
    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Description')
    claims = fields.Function(
        fields.One2Many('claim', None, 'Claims'),
        'on_change_with_claims')

    @classmethod
    def build_process_domain(cls):
        res = super(ClaimDeclareFindProcess, cls).build_process_domain()
        res += [('for_loss_descs', '=', Eval('loss_desc')),
            If(Bool(Eval('claim')),
                ('kind', '=', 'claim_reopening'),
                ('kind', '=', 'claim_declaration')
                )]
        return res

    @classmethod
    def build_process_depends(cls):
        res = super(ClaimDeclareFindProcess, cls).build_process_depends()
        res += ['claim', 'party', 'loss_desc']
        return res

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'claim')])[0].id

    @fields.depends('party')
    def on_change_with_claims(self, name=None):
        Claim = Pool().get('claim')
        return [x.id for x in Claim.search([('claimant', '=', self.party)])]

    @fields.depends('claim', 'party', 'loss_desc')
    def on_change_with_good_process(self):
        return super(ClaimDeclareFindProcess,
            self).on_change_with_good_process()


class ClaimDeclare(ProcessFinder):
    'Claim Declare'

    __name__ = 'claim.declare'

    @classmethod
    def get_parameters_model(cls):
        return 'claim.declare.find_process'

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'claim_process',
            'declaration_process_parameters_form')

    def init_main_object_from_process(self, obj, process_param):
        pool = Pool()
        Loss = pool.get('claim.loss')
        res, errs = super(ClaimDeclare,
            self).init_main_object_from_process(obj, process_param)
        if res:
            if process_param.party:
                obj.claimant = process_param.party
                obj.declaration_date = obj.default_declaration_date()
                possible_contracts = obj.get_possible_contracts()
                if len(possible_contracts) == 1:
                    obj.main_contract = possible_contracts[0]
            if len(process_param.good_process.for_loss_descs) == 1:
                loss_desc = process_param.good_process.for_loss_descs[0]
                event_desc = loss_desc.event_descs[0]
                obj.losses = [Loss(loss_desc=loss_desc,
                        event_desc=event_desc,
                        covered_person=process_param.party
                        if (process_param.party and
                            process_param.party.is_person)
                        else None)]
        return res, errs

    def search_main_object(self):
        return self.process_parameters.claim

    def update_main_object(self, main_obj):
        if main_obj.status == 'closed':
            main_obj.status = 'open'
        return main_obj
