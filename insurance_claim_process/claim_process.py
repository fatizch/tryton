from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.modules.coop_utils import utils, model

from trytond.modules.process import ClassAttr


__all__ = [
    'ClaimProcess',
    'LossProcess',
]


class ClaimProcess():
    'Claim'

    __name__ = 'ins_claim.claim'
    __metaclass__ = ClassAttr

    contracts = fields.Function(
        fields.One2Many('ins_contract.contract', None, 'Contracts',
            on_change_with=['claimant']),
        'on_change_with_contracts')
    doc_received = fields.Function(
        fields.Boolean(
            'All Document Received',
            depends=['documents'],
            on_change_with=['documents']),
        'on_change_with_doc_received')
    indemnifications = fields.Function(
        fields.One2Many('ins_claim.indemnification', None, 'Indemnifications'),
        'get_indemnifications', 'set_toto')
    indemnifications_consult = fields.Function(
        fields.One2Many('ins_claim.indemnification', None, 'Indemnifications'),
        'get_indemnifications')

    def get_possible_contracts(self):
        if not self.claimant:
            return []
        Contract = Pool().get('ins_contract.contract')
        return Contract.search([('subscriber', '=', self.claimant.id)])

    def on_change_with_contracts(self, name=None):
        return [x.id for x in self.get_possible_contracts()]

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
                    print indemnification.status
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
    def set_toto(cls, instances, name, vals):
        Indemnification = Pool().get('ins_claim.indemnification')
        vals_as_dict = dict([(k[0], k[1:]) for k in vals])
        if 'write' in vals_as_dict:
            objects = Indemnification.browse(vals_as_dict['write'][0])
            Indemnification.write(
                objects,
                vals_as_dict['write'][1])

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
        fields.One2Many('ins_product.benefit', None, 'Benefits',
            on_change_with=['loss_desc', 'event_desc', 'start_date', 'claim']),
        'on_change_with_benefits')

    def get_possible_benefits(self):
        if not self.claim or not self.loss_desc:
            return {}
        res = {}
        for contract in self.claim.get_possible_contracts():
            for option in contract.options:
                benefits = option.offered.get_possible_benefits(
                    self.loss_desc, self.event_desc, self.start_date)
                if benefits:
                    res[option.id] = benefits
        return res

    def on_change_with_benefits(self, name=None):
        res = []
        for x in self.get_possible_benefits().values():
            res += [benefit.id for benefit in x]
        return list(set(res))
