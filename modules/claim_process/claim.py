# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

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
        documents = defaultdict(set)
        default_docs_per_loss = defaultdict(dict)
        for loss in self.losses:
            if not loss.loss_desc:
                continue
            documents[loss] |= set(loss.loss_desc.get_documents())

            for delivered in loss.services:
                if not (hasattr(delivered, 'benefit') and delivered.benefit):
                    continue
                args = {}
                delivered.init_dict_for_rule_engine(args)
                default_docs_per_loss[loss].update(
                    delivered.benefit.calculate_required_documents(args))
            for loss, default_docs in default_docs_per_loss.items():
                if not default_docs:
                    continue
                descs = {x for x in [DocumentDescription.get_document_per_code(
                        c) for c in default_docs.keys()]}
                documents[loss] |= descs
        existing_document_desc = defaultdict(list)
        for line in self.document_request_lines:
            existing_document_desc[line.for_object].append(line.document_desc)
        to_save = []
        for loss, docs in documents.items():
            for desc in docs:
                if desc in existing_document_desc[loss]:
                    existing_document_desc[loss].remove(desc)
                    continue
                params = default_docs.get(desc.code, {})
                line = DocumentRequestLine(**params)
                line.document_desc = desc
                if loss:
                    line.for_object = '%s,%s' % (loss.__name__, loss.id)
                else:
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
