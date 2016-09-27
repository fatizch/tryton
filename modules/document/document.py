# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.model import Unique
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model, coop_string, utils

__all__ = [
    'DocumentDescription',
    'DocumentReception',
    'ReceiveDocument',
    'ReattachDocument',
    ]


class DocumentDescription(model.CoopSQL, model.CoopView):
    'Document Description'

    __name__ = 'document.description'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True, translate=True)
    when_received = fields.Selection([
            ('', ''), ('free_attach', 'Free Attachment')],
        'Action when received')

    @classmethod
    def __setup__(cls):
        super(DocumentDescription, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('code_unique', Unique(t, t.code),
                'The document description code must be unique'),
        ]
        cls._order.insert(0, ('name', 'ASC'))

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class DocumentReception(model.CoopSQL, model.CoopView):
    'Document Reception'

    __name__ = 'document.reception'

    state = fields.Selection([
            ('new', 'New'),
            ('waiting', 'Waiting'),
            ('done', 'Done'),
            ('rejected', 'Rejected'),
            ], 'State', readonly=True)
    state_string = state.translated('state')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Content',
        size=1, states={'invisible': ~Eval('attachments')})
    # Once the document is treated, attachments becomes empty, and attachment
    # is set.
    attachment = fields.Many2One('ir.attachment', 'Attachment', readonly=True,
        ondelete='SET NULL', states={'invisible': ~Eval('attachment')})
    reception_date = fields.Date('Reception Date')
    document_desc = fields.Function(
        fields.Many2One('document.description', 'Document Description',
            states={'readonly': Eval('state', '') == 'done'},
            depends=['state']),
        'on_change_with_document_desc', 'setter_void')
    action_defined = fields.Function(
        fields.Char('Action Defined'),
        'on_change_with_action_defined')
    final_target = fields.Function(
        fields.Reference('Target Instance', 'get_models', states={
                'invisible': ~Eval('final_target')}),
        'getter_final_target')

    @classmethod
    def __setup__(cls):
        super(DocumentReception, cls).__setup__()
        cls._order = [('create_date', 'ASC')]
        cls._buttons.update({
                'execute': {'invisible': (Eval('state', '') == 'done')
                    | (Eval('state', '') == 'rejected')},
                'do_wait': {'invisible':
                    (Eval('state', '') == 'waiting')
                    | (Eval('state', '') == 'done')},
                'do_reject': {'invisible': (Eval('state', '') == 'done')
                    | (Eval('state', '') == 'rejected')},
                })
        cls.__rpc__.update({'get_models': RPC()})
        cls._error_messages.update({
                'no_reception_date': 'A reception date must be set on '
                '%(document_name)s before going on.',
                'not_attached': 'The document will not be attached to '
                'anything !',
                })

    @classmethod
    def default_state(cls):
        return 'new'

    @fields.depends('attachments', 'document_desc')
    def on_change_document_desc(self):
        self.attachments[0].document_desc = self.document_desc
        self.attachments = list(self.attachments)
        if self.document_desc:
            self.action_defined = self.document_desc.when_received

    @fields.depends('document_desc')
    def on_change_with_action_defined(self, name=None):
        if self.document_desc:
            return self.document_desc.when_received
        return ''

    @fields.depends('attachment', 'attachments')
    def on_change_with_document_desc(self, name=None):
        if self.attachments and self.attachments[0].document_desc:
            return self.attachments[0].document_desc.id
        if self.attachment and self.attachment.document_desc:
            return self.attachment.document_desc.id

    def get_rec_name(self, name=None):
        if self.attachments:
            return self.attachments[0].rec_name
        if self.attachment:
            return self.attachment.rec_name
        if self.document_desc:
            return self.document_desc.rec_name

    @classmethod
    def get_models(cls):
        return utils.models_get()

    def getter_final_target(self, name):
        if not self.attachment:
            return None
        return str(self.attachment.resource)

    @classmethod
    def check_reception_date(cls, documents):
        with model.error_manager():
            for document in documents:
                if not document.reception_date:
                    document.append_functional_error('no_reception_date',
                        {'document_name': document.rec_name})

    @classmethod
    def check_attached(cls, documents):
        for document in documents:
            if not document.attachment:
                document.raise_user_warning(document.id, 'not_attached')

    @classmethod
    @model.CoopView.button_action('document.act_receive_document')
    def execute(cls, documents):
        cls.check_reception_date(documents)

    @classmethod
    def complete(cls, documents):
        cls.check_reception_date(documents)
        cls.check_attached(documents)
        cls.write(documents, {'state': 'done'})

    @classmethod
    def do_reject(cls, documents):
        cls.write(documents, {'state': 'rejected'})

    @classmethod
    def do_wait(cls, documents):
        cls.write(documents, {'state': 'waiting'})

    def transfer(self, target):
        attachment = self.attachments[0]
        self.attachment = attachment
        self.save()
        attachment.resource = target
        attachment.save()
        self.complete([self])


class ReceiveDocument(Wizard):
    'Receive Document'

    __name__ = 'document.receive'

    start_state = 'decide'
    decide = StateTransition()
    nothing = StateTransition()
    free_attach = StateView('document.receive.reattach',
        'document.reattach_document_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Attach', 'reattach', 'tryton-go-next', default=True)])
    reattach = StateTransition()

    def transition_decide(self):
        DocumentReception = Pool().get('document.reception')
        assert (Transaction().context.get('active_model') ==
            'document.reception')
        doc_id = Transaction().context.get('active_id')
        document = DocumentReception(doc_id)
        self.free_attach.document = document
        if not document.action_defined:
            return 'nothing'
        return document.action_defined

    def transition_nothing(self):
        document = self.free_attach.document
        document.complete([document])
        return 'end'

    def default_free_attach(self, name):
        if self.free_attach._default_values:
            return self.free_attach._default_values

    def transition_reattach(self):
        document = self.free_attach.document
        document.transfer(self.free_attach.target)
        return 'end'

    def do_launch(self, action):
        return action, {}


class ReattachDocument(model.CoopView):
    'Reattach Document'

    __name__ = 'document.receive.reattach'

    document = fields.Many2One('document.reception', 'Document',
        readonly=True)
    target = fields.Reference('Target Instance', 'get_models', required=True)

    @classmethod
    def get_models(cls):
        return utils.models_get()
