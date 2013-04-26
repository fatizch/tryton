import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Bool

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

    def on_change_with_contact_history(self, name=None):
        if not (hasattr(self, 'claimant') and self.claimant):
            return []
        ContactHistory = Pool().get('party.contact_history')
        return [x.id for x in ContactHistory.search(
            [('party', '=', self.claimant)])]

    def calculate_indemnification(self):
        for loss in self.losses:
            for delivered_service in loss.delivered_services:
                if delivered_service.status == 'calculating':
                    delivered_service.calculate()
                    delivered_service.save()
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

    #The Benefit to deliver is just a shortcut to ease delivered service
    #creation. it should not be used once a delivered_service has been created
    benefit_to_deliver = fields.Function(
        fields.Many2One('ins_product.benefit', 'Benefit',
            domain=[('id', 'in', Eval('benefits'))],
            depends=['benefits', 'can_modify_benefit'],
            states={'invisible': ~Eval('can_modify_benefit')},
            on_change=['benefit_to_deliver', 'delivered_services', 'claim',
                'start_date', 'loss_desc', 'event_desc']),
        'get_benefit_to_deliver', 'set_void')
    benefits = fields.Function(
        fields.One2Many(
            'ins_product.benefit', None, 'Benefits',
            on_change_with=['loss_desc', 'event_desc', 'start_date', 'claim']),
        'on_change_with_benefits')
    can_modify_benefit = fields.Function(
        fields.Boolean('Can Modify Benefit?',
            on_change_with=['delivered_services']),
        'on_change_with_can_modify_benefit')

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

    def get_benefit_to_deliver(self, name):
        if (len(self.delivered_services) == 1
                and self.delivered_services[0].status == 'calculating'):
            return self.delivered_services[0].benefit.id

    @classmethod
    def set_void(cls, instances, name, vals):
        pass

    def on_change_benefit_to_deliver(self):
        res = {}
        if not self.delivered_services:
            res['delivered_services'] = utils.create_inst_with_default_val(
                self, 'delivered_services', 'add')
            del_serv_dict = res['delivered_services']['add'][0]
        elif (len(self.delivered_services) == 1
                and self.delivered_services[0].status == 'calculating'):
            res['delivered_services'] = {'update':
                [{'id': self.delivered_services[0].id}]
            }
            del_serv_dict = res['delivered_services']['update'][0]
        else:
            return res
        del_serv_dict['benefit'] = (self.benefit_to_deliver.id
            if self.benefit_to_deliver else None)
        del_serv_dict['complementary_data'] = (utils.init_complementary_data(
                self.benefit_to_deliver.complementary_data_def)
            if self.benefit_to_deliver else {})
        contract = None
        if self.claim.main_contract:
            contract = self.claim.main_contract
        else:
            contracts = self.claim.get_possible_contracts(self.start_date)
            if len(contracts) == 1:
                contract = contracts[0]
        if not contract:
            return res
        del_serv_dict['contract'] = contract.id
        if not self.benefit_to_deliver:
            return res
        options = []
        for option in contract.options:
            if self.benefit_to_deliver in option.get_possible_benefits(self):
                options.append(option)
        if len(set(options)) == 1:
            del_serv_dict['subscribed_service'] = options[0].id
        return res

    def on_change_with_can_modify_benefit(self, name=None):
        return (not self.delivered_services
            or (len(self.delivered_services) == 1
                and self.delivered_services[0].status == 'calculating'))


class DeliveredServiceProcess():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta


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
