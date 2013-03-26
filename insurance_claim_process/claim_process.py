import copy

from trytond.pool import Pool, PoolMeta
from trytond.modules.coop_utils import utils, fields

from trytond.modules.process import ClassAttr
from trytond.modules.coop_process import CoopProcessFramework
from trytond.modules.coop_process import ProcessFinder, ProcessParameters


__all__ = [
    'ClaimProcess',
    'LossProcess',
    'ProcessDesc',
    'DeclarationProcessParameters',
    'DeclarationProcessFinder',
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

    def get_possible_contracts(self, at_date=None):
        if not at_date:
            at_date = self.declaration_date
        return self.get_possible_contracts_from_party(self.claimant,
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
        for loss in self.losses:
            for delivered_service in loss.delivered_services:
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

    def validate_indemnifications(self):
        for loss in self.losses:
            for delivered_service in loss.delivered_services:
                for indemnification in delivered_service.indemnifications:
                    if indemnification.status == 'validated':
                        indemnification.status = 'paid'
                        indemnification.save()
        return True

    def close_claim(self):
        self.status = 'closed'
        self.sub_status = 'paid'
        self.end_date = utils.today()
        return True

    @classmethod
    def set_indemnifications(cls, instances, name, vals):
        Indemnification = Pool().get('ins_claim.indemnification')
        for val in vals:
            if not val[0] == 'write':
                continue
            Indemnification.write(
                Indemnification.browse(val[1]),
                val[2])

    def reject_and_close_claim(self):
        self.status = 'closed'
        self.sub_status = 'refusal'
        self.end_date = utils.today()
        return True


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


class ProcessDesc():
    'Process Desc'

    __metaclass__ = PoolMeta

    __name__ = 'process.process_desc'

    @classmethod
    def __setup__(cls):
        super(ProcessDesc, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('claim_declaration', 'Claim Declaration'))


class DeclarationProcessParameters(ProcessParameters):
    'Declaration Process Parameters'

    __name__ = 'ins_claim.declaration_process_parameters'

    @classmethod
    def build_process_domain(cls):
        result = super(
            DeclarationProcessParameters, cls).build_process_domain()
        result.append(('kind', '=', 'claim_declaration'))
        return result

    @classmethod
    def default_model(cls):
        Model = Pool().get('ir.model')
        return Model.search([('model', '=', 'ins_claim.claim')])[0].id


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
        return res, errs
