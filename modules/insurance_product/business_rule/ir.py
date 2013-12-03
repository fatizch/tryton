from trytond.pool import PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coop_utils import fields

__all__ = [
    'PrintableModel',
    'NoTargetCheckAttachment',
]

__metaclass__ = PoolMeta


class PrintableModel():
    'Model'

    __name__ = 'ir.model'

    printable = fields.Boolean('Printable')


class NoTargetCheckAttachment():
    'Attachment'

    __name__ = 'ir.attachment'

    @classmethod
    def check_access(cls, ids, mode='read'):
        if '_force_access' in Transaction().context:
            return
        super(NoTargetCheckAttachment, cls).check_access(ids, mode)
