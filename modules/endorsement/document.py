# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
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
            ('start_endorsement', 'Start Endorsement'))


class ReceiveDocument(metaclass=PoolMeta):
    __name__ = 'document.receive'

    start_endorsement = StateAction('endorsement.act_start_endorsement')

    def do_start_endorsement(self, action):
        document = self.free_attach.document
        if not document.contract:
            raise ValidationError(gettext(
                    'endorsement.msg_no_contract_selected'))
        document.transfer(document.contract)
        return action, {
            'id': document.contract.id,
            'model': 'contract',
            }
