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
            ('start_endorsement', 'Start Endorsement'))


class ReceiveDocument:
    __metaclass__ = PoolMeta
    __name__ = 'document.receive'

    start_endorsement = StateAction('endorsement.act_start_endorsement')

    @classmethod
    def __setup__(cls):
        super(ReceiveDocument, cls).__setup__()
        cls._error_messages.update({
                'no_contract_selected': 'A contract must be set !',
                })

    def do_start_endorsement(self, action):
        document = self.free_attach.document
        if not document.contract:
            self.raise_user_error('no_contract_selected')
        document.transfer(document.contract)
        return action, {
            'id': document.contract.id,
            'model': 'contract',
            }
