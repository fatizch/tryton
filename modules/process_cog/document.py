# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.wizard import Button, StateAction, StateTransition

from trytond.modules.coog_core import fields


__all__ = [
    'ReceiveDocument',
    'ReattachDocument',
    ]


class ReceiveDocument:
    __metaclass__ = PoolMeta
    __name__ = 'document.receive'

    attach_and_resume = StateTransition()
    resume_process = StateAction('process_cog.act_resume_process')

    @classmethod
    def __setup__(cls):
        super(ReceiveDocument, cls).__setup__()
        cls.free_attach.buttons.append(
            Button('Attach and Resume Process', 'attach_and_resume',
                'tryton-fullscreen',
                # client bug which breaks states syncing
                # states={'readonly': ~Eval('current_process')}))
                ))
        cls._error_messages.update({
                'no_process': 'No process was found for the selected element.',
                })

    def transition_attach_and_resume(self):
        if not self.free_attach.current_process:
            self.raise_user_error('no_process')
        self.transition_reattach()
        return 'resume_process'

    def do_resume_process(self, action):
        return action, {
            'id': self.free_attach.current_process.id,
            'model': self.free_attach.current_process.__name__,
            }


class ReattachDocument:
    __metaclass__ = PoolMeta
    __name__ = 'document.receive.reattach'

    current_process = fields.Reference('Current Process', 'get_models')

    @fields.depends('current_process', 'target')
    def on_change_target(self):
        super(ReattachDocument, self).on_change_target()
        self.current_process = None
        if not self.target:
            return
        to_check = self.target
        if self.target.__name__ == 'document.request.line':
            to_check = self.target.for_object
        if getattr(to_check, 'current_state', None):
            self.current_process = to_check
