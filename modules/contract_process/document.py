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
            ('start_subscription', 'Start Subscription'))


class ReceiveDocument(metaclass=PoolMeta):
    __name__ = 'document.receive'

    start_subscription = StateAction(
        'contract_process.subscription_process_launcher')

    def do_start_subscription(self, action):
        return action, {
            'extra_context': {
                'current_document_reception': self.free_attach.document.id,
                }}
