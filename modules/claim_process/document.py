# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.wizard import StateAction


__all__ = [
    'DocumentDescription',
    'ReceiveDocument',
    ]


class DocumentDescription(metaclass=PoolMeta):
    __name__ = 'document.description'

    @classmethod
    def __setup__(cls):
        super(DocumentDescription, cls).__setup__()
        cls.when_received.selection.append(
            ('start_claim_declaration', 'Start Claim Declaration'))


class ReceiveDocument(metaclass=PoolMeta):
    __name__ = 'document.receive'

    start_claim_declaration = StateAction(
        'claim_process.declaration_process_launcher')

    def do_start_claim_declaration(self, action):
        context = {
            'extra_context': {
                'current_document_reception': self.free_attach.document.id,
                }
            }
        party = self.free_attach.document.party
        if party:
            context['id'] = party.id
            context['ids'] = [party.id]
            context['model'] = 'party.party'
            if self.free_attach.document.claim:
                context['extra_context']['force_claim'] = \
                    self.free_attach.document.claim.id
        return action, context
