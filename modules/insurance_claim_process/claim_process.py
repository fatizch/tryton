import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Or, If, Bool

from trytond.modules.process import ClassAttr
from trytond.modules.coop_utils import utils, fields
from trytond.modules.coop_process import CoopProcessFramework
from trytond.modules.coop_process import ProcessFinder, ProcessParameters


__all__ = [
    'ClaimProcess',
    'LossProcess',
    'ProcessDesc',
    'DeclarationProcessParameters',
    'DeclarationProcessFinder',
    'DeliveredServiceProcess',
]


class ClaimProcess(CoopProcessFramework):
    'Claim'

    __metaclass__ = ClassAttr
    __name__ = 'ins_claim.claim'

    contracts = fields.Function(
        fields.One2Many(
            'ins_contract.contract', None, 'Contracts',
            on_change_with=['claimant', 'declaration_date']),
        'on_change_with_contracts')
    doc_received = fields.Function(
        fields.Boolean(
            'All Document Received',
            depends=['documents'],
            on_change_with=['documents']),
        'on_change_with_doc_received')
    indemnifications = fields.Function(
        fields.One2Many('ins_claim.indemnification', None, 'Indemnifications'),
        'get_indemnifications', 'set_indemnifications')
    indemnifications_consult = fields.Function(
        fields.One2Many('ins_claim.indemnification', None, 'Indemnifications'),
        'get_indemnifications')
    contact_history = fields.Function(
        fields.One2Many(
            'party.contact_history', '', 'History',
            on_change_with=['claimant'], depends=['claimant']),
        'on_change_with_contact_history')
    is_pending_indemnification = fields.Function(
        fields.Boolean('Pending Indemnification', states={'invisible': True}),
        'get_is_pending_indemnification')
    working_loss = fields.Function(
        fields.One2Many('ins_claim.loss', None, 'Loss'),
        'get_working_loss', 'set_working_loss')

    def get_possible_contracts(self, at_date=None):
        if not at_date:
            at_date = self.declaration_date
        Contract = Pool().get('ins_contract.contract')
        return Contract.get_possible_contracts_from_party(self.claimant,
            at_date)

    def on_change_with_contracts(self, name=None):
        return [x.id for x in self.get_possible_contracts()]

    def on_change_with_contact_history(self, name=None):
        if not (hasattr(self, 'claimant') and self.claimant):
            return []
        ContactHistory = Pool().get('party.contact_history')
        return [x.id for x in ContactHistory.search(
            [('party', '=', self.claimant)])]

    def init_delivered_services(self):
        Option = Pool().get('ins_contract.option')
        for loss in self.losses:
            for option_id, benefits in loss.get_possible_benefits().items():
                loss.init_delivered_services(Option(option_id), benefits)
            loss.save()
        return True

    def calculate_indemnification(self):
        to_delete = []
        for loss in self.losses:
            for delivered_service in loss.delivered_services:
                if delivered_service.status == 'calculating':
                    delivered_service.calculate()
                    delivered_service.save()
                elif delivered_service.status == 'applicable':
                    to_delete.append(delivered_service)
        Pool().get('ins_contract.delivered_service').delete(to_delete)
        return True

    def init_declaration_document_request(self):
        DocRequest = Pool().get('ins_product.document_request')
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
            for delivered in loss.delivered_services:
                if not (hasattr(delivered, 'benefit') and delivered.benefit):
                    continue
                contract = delivered.get_contract()
                product = contract.get_offered()
                if not product:
                    continue
                benefit_docs, errs = delivered.benefit.get_result(
                    'documents', {
                        'product': product,
                        'contract': contract,
                        'loss': loss,
                        'claim': self,
                        'date': loss.start_date,
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
            for delivered_service in loss.delivered_services:
                for indemnification in delivered_service.indemnifications:
                    res.append(indemnification.id)
        return res

    @classmethod
    def set_indemnifications(cls, instances, name, vals):
        Indemnification = Pool().get('ins_claim.indemnification')
        for val in vals:
            if not val[0] == 'write':
                continue
            Indemnification.write(Indemnification.browse(val[1]), val[2])

    @classmethod
    def set_working_loss(cls, instances, name, vals):
        Loss = Pool().get('ins_claim.loss')
        for val in vals:
            if not val[0] == 'write':
                continue
            Loss.write(Loss.browse(val[1]), val[2])

    def get_working_loss(self, name):
        return [self.losses[-1].id]

    def reject_and_close_claim(self):
        self.status = 'closed'
        self.end_date = utils.today()
        return True

    def get_is_pending_indemnification(self, name):
        for loss in self.losses:
            for del_ser in loss.delivered_services:
                for indemn in del_ser.indemnifications:
                    if indemn.status == 'calculated':
                        return True
        return False


class LossProcess():
    'Loss'

    __name__ = 'ins_claim.loss'
    __metaclass__ = PoolMeta

    benefits = fields.Function(
        fields.One2Many(
            'ins_product.benefit', None, 'Benefits',
            on_change_with=['loss_desc', 'event_desc', 'start_date', 'claim',
            'covered_person']),  #  TODO:Covered person should not be here
        'on_change_with_benefits')

    def get_possible_benefits(self):
        if not self.claim or not self.loss_desc:
            return {}
        res = {}
        for contract in self.claim.get_possible_contracts(
                at_date=self.start_date):
            for option in contract.options:
                benefits = option.get_possible_benefits(self)
                if benefits:
                    res[option.id] = benefits
        return res

    def on_change_with_benefits(self, name=None):
        res = []
        for x in self.get_possible_benefits().values():
            res += [benefit.id for benefit in x]
        return list(set(res))


class DeliveredServiceProcess():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta

    needs_to_be_calculated = fields.Function(
        fields.Boolean('To Be Calculated',
            on_change=['needs_to_be_calculated', 'status']),
        'get_needs_to_be_calculated', 'set_void')

    @classmethod
    def __setup__(cls):
        super(DeliveredServiceProcess, cls).__setup__()
        utils.update_states(cls, 'status', {'invisible': Or(
                Eval('status') == 'applicable',
                Eval('status') == 'calculating'
        )})

    def get_needs_to_be_calculated(self, name):
        if self.status == 'applicable':
            return False
        elif self.status == 'calculating':
            return True

    def on_change_needs_to_be_calculated(self):
        res = {}
        if self.needs_to_be_calculated:
            res['status'] = 'calculating'
        elif not self.needs_to_be_calculated:
            res['status'] = 'applicable'
        return res

    @classmethod
    def set_void(cls, instances, names, vals):
        pass


class ProcessDesc():
    'Process Desc'

    __metaclass__ = PoolMeta

    __name__ = 'process.process_desc'

    @classmethod
    def __setup__(cls):
        super(ProcessDesc, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('claim_declaration', 'Claim Declaration'))
        cls.kind.selection.append(('claim_reopening', 'Claim Reopening'))
        cls.kind.selection[:] = list(set(cls.kind.selection))


class DeclarationProcessParameters(ProcessParameters):
    'Declaration Process Parameters'

    __name__ = 'ins_claim.declaration_process_parameters'

    party = fields.Many2One('party.party', 'Party')
    claim = fields.Many2One('ins_claim.claim', 'Claim',
        domain=[('id', 'in', Eval('claims'))],
        depends=['claims'])
    claims = fields.Function(
        fields.One2Many('ins_claim.claim', None, 'Claims',
            on_change_with=['party']),
        'on_change_with_claims')

    @classmethod
    def build_process_domain(cls):
        res = super(DeclarationProcessParameters, cls).build_process_domain()
        res += [
            If(
                Bool(Eval('claim')),
                ('kind', 'in', ['claim_reopening', 'claim_declaration']),
                ('kind', '=', 'claim_declaration')
            )
        ]
        return res

    @classmethod
    def build_process_depends(cls):
        res = super(DeclarationProcessParameters, cls).build_process_depends()
        res += ['claim']
        return res

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'ins_claim.claim')])[0].id

    def on_change_with_claims(self, name=None):
        Claim = Pool().get('ins_claim.claim')
        return [x.id for x in Claim.search([('claimant', '=', self.party)])]


class DeclarationProcessFinder(ProcessFinder):
    'Declaration Process Finder'

    __name__ = 'ins_claim.declaration_process_finder'

    @classmethod
    def get_parameters_model(cls):
        return 'ins_claim.declaration_process_parameters'

    @classmethod
    def get_parameters_view(cls):
        return '%s.%s' % (
            'insurance_claim_process',
            'declaration_process_parameters_form')

    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(DeclarationProcessFinder,
            self).init_main_object_from_process(obj, process_param)
        if res:
            obj.declaration_date = process_param.date
            if process_param.party:
                obj.claimant = process_param.party
        return res, errs

    def search_main_object(self):
        return self.process_parameters.claim
