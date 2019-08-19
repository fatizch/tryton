# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__all__ = [
    'ContractNote',
    ]


class ContractNote(metaclass=PoolMeta):
    __name__ = 'contract'

    medical_notes = fields.One2ManyDomain('ir.note', 'resource',
        'Medical Notes',
        domain=[('type_', '=', 'medical')], delete_missing=True)
