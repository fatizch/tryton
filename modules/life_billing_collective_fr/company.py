from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Company',
    ]


class Company:
    __name__ = 'company.company'

    rate_note_sequence = fields.Many2One('ir.sequence',
        'Rate Note Sequence')
