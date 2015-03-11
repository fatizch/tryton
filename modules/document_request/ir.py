from trytond.pool import PoolMeta
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'Attachment',
    ]


class Attachment:
    'Attachment'

    __name__ = 'ir.attachment'

    @classmethod
    def check_access(cls, ids, mode='read'):
        if '_force_access' in Transaction().context:
            return
        super(Attachment, cls).check_access(ids, mode)
