# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from trytond.modules.process import ClassAttr
from trytond.modules.coog_core import utils, fields
from trytond.modules.process_cog.process import CoogProcessFramework


__all__ = [
    'Claim',
    ]


class Claim(CoogProcessFramework):
    'Claim'

    __metaclass__ = ClassAttr
    __name__ = 'claim'

    contact_history = fields.Function(
        fields.One2Many('party.interaction', '', 'History',
            depends=['claimant']),
        'on_change_with_contact_history')
    open_loss = fields.Function(
        fields.One2Many('claim.loss', None, 'Open Loss'),
        'get_open_loss', setter='set_open_loss')

    @fields.depends('claimant')
    def on_change_with_contact_history(self, name=None):
        if not (hasattr(self, 'claimant') and self.claimant):
            return []
        ContactHistory = Pool().get('party.interaction')
        return [x.id for x in ContactHistory.search(
                [('party', '=', self.claimant)])]

    def get_open_loss(self, name):
        return [l.id for l in self.losses if not l.end_date]

    @classmethod
    def set_open_loss(cls, claims, name, value):
        pool = Pool()
        Loss = pool.get('claim.loss')
        for action in value:
            if action[0] == 'write':
                objects = [Loss(id_) for id_ in action[1]]
                Loss.write(objects, action[2])
            elif action[0] == 'delete':
                objects = [Loss(id_) for id_ in action[1]]
                Loss.delete(objects)

    def init_declaration_document_request(self):
        pool = Pool()
        DocumentRequestLine = pool.get('document.request.line')
        DocumentDescription = pool.get('document.description')
        documents = []
        default_docs = {}
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
                default_docs.update(
                    delivered.benefit.calculate_required_documents(args))
        if default_docs:
            documents += DocumentDescription.search(
                [('code', 'in', default_docs.keys())])
        existing_document_desc = [request.document_desc
            for request in self.document_request_lines]
        to_save = []
        documents = list(set(documents))
        for desc in documents:
            if desc in existing_document_desc:
                existing_document_desc.remove(desc)
                continue
            params = default_docs.get(desc.code, {})
            line = DocumentRequestLine(**params)
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

    def set_sub_status(self, sub_status_code):
        SubStatus = Pool().get('claim.sub_status')
        sub_status = SubStatus.get_sub_status(sub_status_code)
        self.sub_status = sub_status
        self.save()
