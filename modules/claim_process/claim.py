from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Bool

from trytond.modules.process import ClassAttr
from trytond.modules.cog_utils import utils, fields
from trytond.modules.process_cog import CogProcessFramework
from trytond.modules.process_cog import ProcessFinder, ProcessStart


__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    'Loss',
    'Process',
    'ClaimDeclareFindProcess',
    'ClaimDeclare',
    ]


class Claim(CogProcessFramework):
    'Claim'

    __metaclass__ = ClassAttr
    __name__ = 'claim'

    doc_received = fields.Function(
        fields.Boolean('All Documents Received', depends=['documents']),
        'on_change_with_doc_received')
    indemnifications = fields.Function(
        fields.One2Many('claim.indemnification', None, 'Indemnifications'),
        'get_indemnifications', 'set_indemnifications')
    indemnifications_consult = fields.Function(
        fields.One2Many('claim.indemnification', None, 'Indemnifications'),
        'get_indemnifications')
    contact_history = fields.Function(
        fields.One2Many('party.interaction', '', 'History',
            depends=['claimant']),
        'on_change_with_contact_history')
    is_pending_indemnification = fields.Function(
        fields.Boolean('Pending Indemnification', states={'invisible': True}),
        'get_is_pending_indemnification')

    @fields.depends('claimant')
    def on_change_with_contact_history(self, name=None):
        if not (hasattr(self, 'claimant') and self.claimant):
            return []
        ContactHistory = Pool().get('party.interaction')
        return [x.id for x in ContactHistory.search(
            [('party', '=', self.claimant)])]

    def calculate_indemnification(self):
        for loss in self.losses:
            for service in loss.services:
                if service.status == 'calculating':
                    service.calculate()
                    service.save()
        return True

    def init_declaration_document_request(self):
        DocRequest = Pool().get('document.request')
        if not (hasattr(self, 'documents') and self.documents):
            good_req = DocRequest()
            good_req.needed_by = self
            good_req.save()
        else:
            good_req = self.documents[0]
        documents = []
        for loss in self.losses:
            if not loss.loss_desc:
                continue
            loss_docs = loss.loss_desc.get_documents()
            if loss_docs:
                documents.extend([(doc_desc, self) for doc_desc in loss_docs])
            for delivered in loss.services:
                if not (hasattr(delivered, 'benefit') and delivered.benefit):
                    continue
                contract = delivered.contract
                product = contract.product
                if not product:
                    continue
                benefit_docs, errs = delivered.benefit.get_result(
                    'documents', {
                        'product': product,
                        'contract': contract,
                        'loss': loss,
                        'claim': self,
                        'date': loss.start_date,
                        'appliable_conditions_date':
                        contract.appliable_conditions_date,
                    })
                if errs:
                    return False, errs
                if not benefit_docs:
                    continue
                documents.extend([
                    (doc_desc, delivered) for doc_desc in benefit_docs])
        good_req.add_documents(utils.today(), documents)
        # good_req.clean_extras(documents)
        return True, ()

    @fields.depends('documents')
    def on_change_with_doc_received(self, name=None):
        if not (hasattr(self, 'documents') and self.documents):
            return False
        for doc in self.documents:
            if not doc.is_complete:
                return False
        return True

    def get_indemnifications(self, name=None):
        res = []
        for loss in self.losses:
            for service in loss.services:
                for indemnification in service.indemnifications:
                    res.append(indemnification.id)
        return res

    @classmethod
    def set_indemnifications(cls, instances, name, vals):
        Indemnification = Pool().get('claim.indemnification')
        for val in vals:
            if not val[0] == 'write':
                continue
            Indemnification.write(Indemnification.browse(val[1]), val[2])

    def reject_and_close_claim(self):
        self.status = 'closed'
        self.end_date = utils.today()
        return True

    def get_is_pending_indemnification(self, name):
        for loss in self.losses:
            for del_ser in loss.services:
                for indemn in del_ser.indemnifications:
                    if indemn.status == 'calculated':
                        return True
        return False


class Loss:
    __name__ = 'claim.loss'

    # The Benefit to deliver is just a shortcut to ease delivered service
    # creation. it should not be used once a service has been created
    benefit_to_deliver = fields.Function(
        fields.Many2One('benefit', 'Benefit',
            domain=[('id', 'in', Eval('benefits'))],
            depends=['benefits', 'can_modify_benefit'],
            states={'invisible': ~Eval('can_modify_benefit')}),
        'get_benefit_to_deliver', 'set_void')
    benefits = fields.Function(
        fields.One2Many('benefit', None, 'Benefits'),
        'on_change_with_benefits')
    can_modify_benefit = fields.Function(
        fields.Boolean('Can Modify Benefit?'),
        'on_change_with_can_modify_benefit')

    def get_possible_benefits(self):
        if not self.claim or not self.loss_desc:
            return {}
        res = {}
        if self.claim.main_contract:
            contracts = [self.claim.main_contract]
        else:
            contracts = self.claim.get_possible_contracts(
                at_date=self.start_date)
        for contract in contracts:
            for covered_element in contract.covered_elements:
                for option in covered_element.options:
                    benefits = option.get_possible_benefits(self)
                    if benefits:
                        res[option.id] = benefits
        return res

    @fields.depends('loss_desc', 'event_desc', 'start_date', 'claim')
    def on_change_with_benefits(self, name=None):
        res = []
        for x in self.get_possible_benefits().values():
            res += [benefit.id for benefit in x]
        return list(set(res))

    def get_benefit_to_deliver(self, name):
        if (len(self.services) == 1
                and self.services[0].status == 'calculating'):
            return self.services[0].benefit.id

    @classmethod
    def set_void(cls, instances, name, vals):
        pass

    @fields.depends('benefit_to_deliver', 'services', 'claim', 'start_date',
        'loss_desc', 'event_desc')
    def on_change_benefit_to_deliver(self):
        pool = Pool()
        Service = pool.get('contract.service')
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
            contracts = self.claim.get_possible_contracts(self.start_date)
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

    @fields.depends('services')
    def on_change_with_can_modify_benefit(self, name=None):
        return (not self.services
            or (len(self.services) == 1
                and self.services[0].status == 'calculating'))


class Process:
    __name__ = 'process'

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('claim_declaration', 'Claim Declaration'))
        cls.kind.selection.append(('claim_reopening', 'Claim Reopening'))
        cls.kind.selection[:] = list(set(cls.kind.selection))


class ClaimDeclareFindProcess(ProcessStart):
    'Claim Declare Find Process'

    __name__ = 'claim.declare.find_process'

    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')
    claim = fields.Many2One('claim', 'Claim',
        domain=[('id', 'in', Eval('claims'))], depends=['claims'],
        ondelete='SET NULL')
    claims = fields.Function(
        fields.One2Many('claim', None, 'Claims'),
        'on_change_with_claims')

    @classmethod
    def build_process_domain(cls):
        res = super(ClaimDeclareFindProcess, cls).build_process_domain()
        res += [If(
                Bool(Eval('claim')),
                ('kind', 'in', ['claim_reopening', 'claim_declaration']),
                ('kind', '=', 'claim_declaration')
                )]
        return res

    @classmethod
    def build_process_depends(cls):
        res = super(ClaimDeclareFindProcess, cls).build_process_depends()
        res += ['claim']
        return res

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'claim')])[0].id

    @fields.depends('party')
    def on_change_with_claims(self, name=None):
        Claim = Pool().get('claim')
        return [x.id for x in Claim.search([('claimant', '=', self.party)])]


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
        res, errs = super(ClaimDeclare,
            self).init_main_object_from_process(obj, process_param)
        if res:
            if process_param.party:
                obj.claimant = process_param.party
        return res, errs

    def search_main_object(self):
        return self.process_parameters.claim
