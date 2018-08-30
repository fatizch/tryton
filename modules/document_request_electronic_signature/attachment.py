# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.config import config
from trytond.modules.coog_core import fields

__all__ = [
    'Attachment',
    ]


provider_name = config.get('electronic_signature', 'provider') \
    or 'NO_PROVIDER_DEFINED'
signature_status_field = provider_name + '_status'


class Attachment:
    __metaclass__ = PoolMeta
    __name__ = 'ir.attachment'

    @fields.depends(signature_status_field)
    def is_signed(self):
        return getattr(self, signature_status_field) == 'completed'

    @fields.depends(signature_status_field)
    def has_signature_transaction_request(self):
        return bool(getattr(self, signature_status_field))

    @classmethod
    def request_electronic_signature_transaction(cls, attachments):
        return getattr(cls, provider_name + '_request_transaction')(attachments)

    @classmethod
    def get_electronic_signature_transaction_info(cls, attachments):
        return getattr(cls, provider_name + '_get_transaction_info')(
                attachments)

    def update_electronic_signer(self, signer):
        setattr(self, provider_name + '_signer', signer)
