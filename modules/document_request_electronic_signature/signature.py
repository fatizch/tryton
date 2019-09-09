# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields
from trytond.modules.offered.extra_data import with_extra_data_def
from trytond.modules.offered.extra_data import ExtraDataDefTable

__all__ = [
    'Signature',
    'SignatureConfiguration',
    'SignatureConfigurationExtraDataRelation',
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


class SignatureConfiguration(
        with_extra_data_def('document.signature.configuration-extra_data',
            'conf', 'signature'),
        metaclass=PoolMeta):
    __name__ = 'document.signature.configuration'


class SignatureConfigurationExtraDataRelation(ExtraDataDefTable):
    'Relation between Signature Configuration and Extra Data'

    __name__ = 'document.signature.configuration-extra_data'

    conf = fields.Many2One('document.signature.configuration',
        'Signature Configuration', ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT')
