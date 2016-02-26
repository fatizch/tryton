from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Attachment',
    ]

ATTACHMENT_STATUSES = [('valid', 'Valid'), ('invalid', 'Invalid')]
BLOCKING_STATUSES = ['invalid']


class Attachment:
    'Attachment'

    __name__ = 'ir.attachment'

    status = fields.Selection('status_get', 'Status', required=True)
    is_conform = fields.Function(
        fields.Boolean('Conform'),
        'on_change_with_is_conform')

    @classmethod
    def default_status(cls):
        return cls.status_get()[0][0]

    @classmethod
    def status_get(cls):
        return ATTACHMENT_STATUSES

    @classmethod
    def blocking_statuses_get(cls):
        return BLOCKING_STATUSES

    @fields.depends('status')
    def on_change_with_is_conform(self, name=None):
        return self.status not in self.blocking_statuses_get()

    @classmethod
    def check_access(cls, ids, mode='read'):
        if '_force_access' in Transaction().context:
            return
        super(Attachment, cls).check_access(ids, mode)
