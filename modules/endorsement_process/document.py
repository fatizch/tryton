# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.wizard import StateAction


__all__ = [
    'DocumentDescription',
    'ReceiveDocument',
    ]


class DocumentDescription:
    __metaclass__ = PoolMeta
    __name__ = 'document.description'

    @classmethod
    def __setup__(cls):
        super(DocumentDescription, cls).__setup__()
        cls.when_received.selection.append(
            ('start_endorsement_process', 'Start Endorsement Process'))


class ReceiveDocument:
    __metaclass__ = PoolMeta
    __name__ = 'document.receive'

    start_endorsement_process = StateAction(
        'endorsement.act_start_endorsement')

    def do_start_endorsement_process(self, action):
        document = self.free_attach.document
        if not document.contract:
            self.raise_user_error('no_contract_selected')
        document.transfer(document.contract)
        return action, {
            'id': document.contract.id,
            'model': 'contract',
            'ids': [document.contract.id],
            }
