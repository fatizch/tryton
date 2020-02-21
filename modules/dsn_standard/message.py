# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from pathlib import Path

from trytond.exceptions import UserWarning
from trytond.i18n import gettext
from trytond.pool import Pool
from trytond.model import Workflow, ModelView, fields
from trytond.model.exceptions import AccessError
from trytond.pyson import Eval
from trytond.config import config

from trytond.modules.coog_core import model, utils

__all__ = [
    'DsnMessage'
    ]


class DsnMessage(Workflow, model.CoogSQL, model.CoogView):
    'Dsn message'
    __name__ = 'dsn.message'
    _states = {
        'readonly': Eval('state') != 'draft',
        }
    _depends = ['state']

    type = fields.Selection([
            ('in,', 'In'),
            ('out', 'Out'),
            ], 'Type', required=True, states=_states, depends=_depends)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('done', 'Done'),
            ('canceled', 'Canceled'),
            ], 'State', readonly=True, select=True)
    origin = fields.Reference('Origin', required=True, selection='get_origin',
        select=True, states=_states, depends=_depends)
    message = fields.Binary('Message', states=_states, depends=_depends,
        filename='filename')
    text_message = fields.Function(
        fields.Text('Message', states=_states, depends=_depends),
        'get_text_message')
    filename = fields.Function(fields.Char('Filename'), 'get_filename')

    @classmethod
    def __setup__(cls):
        super(DsnMessage, cls).__setup__()
        cls._transitions |= {
            ('draft', 'waiting'),
            ('waiting', 'done'),
            ('waiting', 'draft'),
            ('draft', 'done'),
            ('draft', 'canceled'),
            ('waiting', 'canceled'),
            }
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'waiting']),
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                'wait': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'do': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                })

    @staticmethod
    def default_type():
        return 'out'

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def _get_origin(cls):
        return []

    @classmethod
    def get_origin(cls):
        IrModel = Pool().get('ir.model')
        models = cls._get_origin()
        models = IrModel.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    def get_filename(self, name):
        return '_'.join([self.origin.rec_name,
            self.create_date_.strftime("%Y%m%d_%H%M%S")]) + '.txt'

    def get_text_message(self, name):
        if not self.message:
            return ''
        return self.message.decode('latin1')

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, messages):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, messages):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, messages):
        pool = Pool()
        Event = pool.get('event')
        archive_dir = config.get('dsn', 'output_dir')
        assert archive_dir, "Please set output_dir in dsn configuration"
        for message in messages:
            if message.type == 'out':
                filepath = Path(archive_dir) / message.filename
                utils.mkdir_if_not_exists(filepath.parent)
                with filepath.open('wb') as _f:
                    _f.write(message.message)
        Event.notify_events(messages, 'dsn_message_sent')

    @classmethod
    @ModelView.button
    @Workflow.transition('canceled')
    def cancel(cls, messages):
        pass

    @classmethod
    def delete(cls, messages):
        for message in messages:
            if message.state != 'draft':
                raise AccessError(gettext(
                        'dsn_standard.msg_delete_draft_msg',
                        message=message.rec_name))
        super(DsnMessage, cls).delete(messages)

    @classmethod
    def check_configuration(cls):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        sender_code = config.get('dsn', 'sender_code', default=-1)
        if sender_code == -1:
            if Warning.check('undefined_dsn_section'):
                raise UserWarning(
                        gettext('dsn_standard.msg_undefined_dsn_section'))
            return False
        return True
