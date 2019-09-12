# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields, utils
from trytond.i18n import gettext

__all__ = [
    'Attachment',
    ]

ATTACHMENT_STATUSES = (('waiting_validation', 'Waiting Validation'),
    ('valid', 'Valid'), ('invalid', 'Invalid'))
BLOCKING_STATUSES = ['invalid']


class Attachment(metaclass=PoolMeta):
    'Attachment'
    __name__ = 'ir.attachment'

    status = fields.Selection('status_get', 'Status', required=True)
    is_conform = fields.Function(
        fields.Boolean('Conform'),
        'on_change_with_is_conform')
    status_change_date = fields.Date('Status Change Date', readonly=True,
        states={'invisible': Eval('status') == 'waiting_validation'},
        depends=['status'], help="Date of Last Status Change"
        )

    @classmethod
    def default_status(cls):
        return 'valid'

    @classmethod
    def status_get(cls):
        return [(x[0], gettext('document_request.msg_' + x[0]))
            for x in ATTACHMENT_STATUSES]

    @classmethod
    def blocking_statuses_get(cls):
        return BLOCKING_STATUSES

    @fields.depends('status', 'status_change_date')
    def on_change_status(self):
        if self.status != 'waiting_validation':
            self.status_change_date = utils.today()
        else:
            self.status_change_date = None

    @fields.depends('status')
    def on_change_with_is_conform(self, name=None):
        return self.status not in self.blocking_statuses_get()

    @classmethod
    def check_access(cls, ids, mode='read'):
        if '_force_access' in Transaction().context:
            return
        super(Attachment, cls).check_access(ids, mode)
