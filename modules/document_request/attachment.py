# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields, utils, model
from trytond.model import Workflow

__all__ = [
    'Attachment',
    ]

BLOCKING_STATUSES = ['invalid']


class Attachment(Workflow, metaclass=PoolMeta):
    'Attachment'
    __name__ = 'ir.attachment'

    _transition_state = 'status'

    status = fields.Selection((
        ('waiting_validation', 'Waiting Validation'),
        ('valid', 'Valid'),
        ('invalid', 'Invalid')),
        'Status', required=True, readonly=True)
    is_conform = fields.Function(
        fields.Boolean('Conform'),
        'on_change_with_is_conform')
    status_change_date = fields.Date('Status Change Date',
        states={'invisible': Eval('status') == 'waiting_validation',
            'readonly': True},
        depends=['status'], help="Date of Last Status Change")
    request_lines = fields.One2Many('document.request.line', 'attachment',
        'Request Lines')
    request_line = fields.Function(
        fields.Many2One('document.request.line', 'Request Line'),
        'getter_request_line')

    @classmethod
    def __setup__(cls):
        super(Attachment, cls).__setup__()
        cls._transitions |= set((
                ('waiting_validation', 'valid'),
                ('waiting_validation', 'invalid'),
                ('valid', 'waiting_validation'),
                ('invalid', 'waiting_validation'),
                ))
        cls._buttons.update({
                'valid': {
                    'invisible': Eval('status').in_(['valid', 'invalid']),
                    'depends': ['status'],
                    },
                'invalid': {
                    'invisible': Eval('status').in_(['invalid', 'valid']),
                    'depends': ['status'],
                    },
                'waiting': {
                    'invisible': Eval('status') == 'waiting_validation',
                    'depends': ['status'],
                    }
                })

    @classmethod
    @model.CoogView.button
    @Workflow.transition('valid')
    def valid(cls, attachments):
        pass

    @classmethod
    @model.CoogView.button
    @Workflow.transition('invalid')
    def invalid(cls, attachments):
        pass

    @classmethod
    @model.CoogView.button
    @Workflow.transition('waiting_validation')
    def waiting(cls, attachments):
        pass

    @classmethod
    def default_status(cls):
        return 'valid'

    @classmethod
    def blocking_statuses_get(cls):
        return BLOCKING_STATUSES

    def getter_request_line(self, name):
        return self.request_lines[0].id if self.request_lines else None

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
