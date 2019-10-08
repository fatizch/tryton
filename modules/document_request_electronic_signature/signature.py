# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta

from trytond.modules.coog_core import export

__all__ = [
    'Signature',
    'SignatureCredential',
    'SignatureConfiguration',
    ]


class Signature(metaclass=PoolMeta):
    __name__ = 'document.signature'

    @classmethod
    def signer_structure(cls, conf, signer):
        struct = super(Signature, cls).signer_structure(conf, signer)
        if signer.is_person:
            struct['first_name'] = signer.first_name
            struct['last_name'] = signer.name
            struct['birth_date'] = datetime.datetime.combine(signer.birth_date,
                datetime.datetime.min.time())
        return struct

    @classmethod
    def format_url(cls, url, from_object):
        if hasattr(from_object, 'format_signature_url'):
            return from_object.format_signature_url(url)
        return super(Signature, cls).format_url(url, from_object)

    def notify_signature_completed(self):
        super(Signature, self).notify_signature_completed()
        if self.attachment and self.attachment.request_line:
            self.attachment.request_line.notify_signature_completed(self)

    def notify_signature_failed(self):
        super(Signature, self).notify_signature_failed()
        if self.attachment and self.attachment.request_line:
            self.attachment.request_line.notify_signature_failed(self)


class SignatureCredential(export.ExportImportMixin, metaclass=PoolMeta):
    __name__ = 'document.signature.credential'


class SignatureConfiguration(export.ExportImportMixin, metaclass=PoolMeta):
    __name__ = 'document.signature.configuration'
