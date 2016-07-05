import functools

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, Button, StateTransition

from trytond.modules.cog_utils import fields, model, utils
from trytond.modules.report_engine import Printable

__all__ = [
    'DocumentRequestLine',
    'DocumentRequest',
    'DocumentReceiveRequest',
    'DocumentReceiveAttach',
    'DocumentReceiveSetRequests',
    'DocumentReceive',
    ]


class DocumentRequestLine(model.CoopSQL, model.CoopView):
    'Document Request Line'

    __name__ = 'document.request.line'

    document_desc = fields.Many2One('document.description',
        'Document Definition', required=True, ondelete='RESTRICT')
    for_object = fields.Reference('Needed For', selection='models_get',
        states={'readonly': ~~Eval('for_object')}, required=True, select=True)
    send_date = fields.Date('Send Date')
    reception_date = fields.Date('Reception Date')
    first_reception_date = fields.Date('First Reception Date')
    request_date = fields.Date('Request Date', states={'readonly': True})
    received = fields.Function(
        fields.Boolean('Received', depends=['attachment', 'reception_date']),
        'on_change_with_received', setter='set_received')
    request = fields.Many2One('document.request', 'Document Request',
        ondelete='CASCADE', select=True)
    attachment = fields.Many2One('ir.attachment', 'Attachment',
        domain=[('resource', '=', Eval('for_object')),
            ('document_desc', '=', Eval('document_desc'))],
        depends=['for_object', 'document_desc'], ondelete='RESTRICT')
    attachment_name = fields.Function(fields.Char('Attachment Name',
            depends=['attachment']),
        'get_attachment_info')
    attachment_data = fields.Function(
        fields.Binary('Data', filename='attachment_name',
            depends=['attachment']),
        'get_attachment_info')
    matching_attachments = fields.Function(
        fields.Many2Many('ir.attachment', None, None, 'Matching Attachments'),
        'get_matching_attachments')
    blocking = fields.Boolean('Blocking', readonly=True)

    @staticmethod
    def models_get():
        return utils.models_get()

    @fields.depends('attachment', 'reception_date', 'received',
        'attachment_name', 'attachment_data')
    def on_change_attachment(self):
        if self.attachment:
            self.attachment_name = self.attachment.name
            self.attachment_data = self.attachment.data
            self.received = True
            if not self.reception_date:
                self.reception_date = utils.today()
            if not self.first_reception_date:
                self.first_reception_date = utils.today()
        else:
            self.received = False
            self.reception_date = None

    @fields.depends('reception_date')
    def on_change_with_received(self, name=None):
        return bool(self.reception_date)

    @fields.depends('received', 'reception_date', 'first_reception_date')
    def on_change_received(self):
        if self.received:
            if not self.reception_date:
                self.reception_date = utils.today()
            if not self.first_reception_date:
                self.first_reception_date = utils.today()
        else:
            self.reception_date = None

    @fields.depends('attachment', 'reception_date')
    def on_change_with_reception_date(self, name=None):
        return self.reception_date if (self.reception_date and
            self.attachment) else utils.today()

    def get_rec_name(self, name=None):
        return self.document_desc.name if self.document_desc else ''

    @classmethod
    def default_request_date(cls):
        return utils.today()

    @classmethod
    def default_for_object(cls):
        if 'request_owner' not in Transaction().context:
            return ''

        needed_by = Transaction().context.get('request_owner')
        the_model, the_id = needed_by.split(',')
        if the_model not in [
                k for k, v in cls._fields['for_object'].selection]:
            return ''
        return needed_by

    @classmethod
    def set_received(cls, request_lines, name, value):
        if value:
            cls.write(request_lines, {'reception_date': utils.today()})
        else:
            cls.write(request_lines, {'reception_date': None})

    def get_attachment_info(self, name):
        if self.attachment:
            return getattr(self.attachment, name.split('_')[1])

    def get_matching_attachments(self, name):
        Attachment = Pool().get('ir.attachment')
        return [x.id for x in Attachment.search([
                    ('resource', '=', str(self.for_object)),
                    ('document_desc', '=', self.document_desc)])]


class DocumentRequest(Printable, model.CoopSQL, model.CoopView):
    'Document Request'

    __name__ = 'document.request'

    needed_by = fields.Reference('Requested for', [('', '')], required=True,
        select=True)
    documents = fields.One2Many('document.request.line', 'request',
        'Documents', depends=['needed_by_str'],
        context={'request_owner': Eval('needed_by_str')}, delete_missing=True,
        target_not_required=True)
    is_complete = fields.Function(
        fields.Boolean('Is Complete', depends=['documents'],
            states={'readonly': ~~Eval('is_complete')}),
        'on_change_with_is_complete', 'setter_void')
    needed_by_str = fields.Function(
        fields.Char('Master as String', depends=['needed_by']),
        'on_change_with_needed_by_str')
    request_description = fields.Function(
        fields.Char('Request Description', depends=['needed_by']),
        'on_change_with_request_description')
    documents_str = fields.Function(
        fields.Char('Documents'),
        'on_change_with_documents_str')

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls._buttons.update({'generic_send_letter': {}})
        cls._error_messages.update({
                'document_request_for': 'Document Request For',
                })

    def get_request_date(self):
        return utils.today()

    @fields.depends('needed_by')
    def on_change_with_request_description(self, name=None):
        return '%s %s' % (self.raise_user_error('document_request_for',
                raise_exception=False), self.needed_by.get_rec_name(name))

    def get_contact(self, name=None):
        return self.needed_by.get_main_contact() if self.needed_by else None

    @fields.depends('documents')
    def on_change_with_documents_str(self, name=None):
        return ', '.join([d.document_desc.name for d in self.documents])

    @fields.depends('needed_by')
    def on_change_with_needed_by_str(self, name=None):
        return utils.convert_to_reference(self.needed_by) if \
            self.needed_by else None

    @fields.depends('documents')
    def on_change_with_is_complete(self, name=None):
        return all([x.received for x in self.documents])

    @fields.depends('documents', 'is_complete')
    def on_change_documents(self):
        self.is_complete = self.on_change_with_is_complete()

    @fields.depends('documents', 'is_complete')
    def on_change_is_complete(self):
        if not (self.is_complete or self.documents):
            return
        for document in self.documents:
            document.received = True
            if not document.reception_date:
                document.reception_date = utils.today()
        self.documents = self.documents

    def get_current_docs(self):
        res = {}
        for elem in self.documents:
            res[(elem.document_desc.id, utils.convert_to_reference(
                        elem.for_object))] = elem
        return res

    def add_documents(self, date, docs):
        # "docs" should be a list of tuple (doc_desc, for_object)
        existing_docs = self.get_current_docs()
        Document = Pool().get('document.request.line')
        for desc, obj in docs:
            if ((desc.id, utils.convert_to_reference(obj))) in existing_docs:
                continue
            good_doc = Document()
            good_doc.document_desc = desc
            good_doc.for_object = utils.convert_to_reference(obj)
            good_doc.request = self
            good_doc.save()
            existing_docs[
                (desc.id, utils.convert_to_reference(obj))] = good_doc

    def clean_extras(self, docs):
        existing_docs = self.get_current_docs()
        id_docs = [(d.id, utils.convert_to_reference(o)) for d, o in docs]
        to_del = []
        for k, v in existing_docs.iteritems():
            if k not in id_docs:
                to_del.append(v)
        Document = Pool().get('document.request.line')
        Document.delete(to_del)

    def get_waiting_documents(self):
        return len([doc for doc in self.documents if not doc.received])

    def post_generation(self):
        for document in self.documents:
            if not document.received:
                document.send_date = utils.today()
                document.save()

    def notify_completed(self):
        pass

    def get_doc_template_kind(self):
        res = super(DocumentRequest, self).get_doc_template_kind()
        res.append('doc_request')
        return res

    def get_object_for_contact(self):
        return self.needed_by

    def get_rec_name(self, name):
        return self.needed_by.get_rec_name(name)

    def get_product(self):
        return self.needed_by.get_product()


class DocumentReceiveRequest(model.CoopView):
    'Document Receive Request'

    __name__ = 'document.receive.request'

    kind = fields.Selection([('', '')], 'Kind')
    value = fields.Char('Value')
    request = fields.Many2One('document.request', 'Request',
        states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(DocumentReceiveRequest, cls).__setup__()
        idx = 0
        cls.kind.selection = [('', '')]
        for k, v in cls.allowed_values().iteritems():
            cls.kind.selection.append((k, v[0]))
            tmp = fields.Many2One(
                k, v[0],
                states={'invisible': Eval('kind') != k},
                depends=['kind', 'value'])
            setattr(cls, 'tmp_%s' % idx, tmp)

            def on_change_tmp(self, name=''):
                if not (hasattr(self, name) and getattr(self, name)):
                    return {}

                relation = getattr(self, name)
                if not (hasattr(relation, 'documents') and relation.documents):
                    return {'value': utils.convert_to_reference(
                        getattr(self, name))}
                return {'request': relation.documents[0].id}
            # Hack to fix http://bugs.python.org/issue3445
            tmp_function = functools.partial(on_change_tmp,
                name='tmp_%s' % idx)
            tmp_function.__module__ = on_change_tmp.__module__
            tmp_function.__name__ = on_change_tmp.__name__
            setattr(cls, 'on_change_tmp_%s' % idx, fields.depends(
                    'request', 'tmp_%s' % idx, 'kind')(tmp_function))
            idx += 1

    @classmethod
    def allowed_values(cls):
        return {}

    @fields.depends('kind')
    def on_change_kind(self):
        for k, v in self._fields.iteritems():
            if not k.startswith('tmp_'):
                continue
            setattr(self, k, None)

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        result = super(DocumentReceiveRequest,
            cls).fields_view_get(view_id, view_type)
        request_finder = Pool().get('ir.model').search([
                ('model', '=', cls.__name__)])[0]
        fields = ['kind', 'value', 'request']
        xml = '<?xml version="1.0"?>'
        xml += '<form string="%s">' % request_finder.name
        xml += '<label name="kind" xalign="0" colspan="1"/>'
        xml += '<field name="kind" colspan="3"/>'
        xml += '<field name="value" invisible="1"/>'
        xml += '<newline/>'
        xml += '<field name="request"/>'
        for k, v in cls._fields.iteritems():
            if not k.startswith('tmp_'):
                continue
            xml += '<newline/>'
            xml += '<label name="%s" colspan="1"/>' % k
            xml += '<field name="%s" colspan="3"/>' % k
            fields.append(k)
        xml += '</form>'
        result['arch'] = xml
        result['fields'] = cls.fields_get(fields_names=fields)
        return result


class DocumentReceiveAttach(model.CoopView):
    'Document Receive Attach'

    __name__ = 'document.receive.attach'

    attachments = fields.One2Many('ir.attachment', '', 'Attachments',
        context={'resource': Eval('resource')})
    resource = fields.Char('Resource', states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(DocumentReceiveAttach, cls).__setup__()
        cls._error_messages.update({
            'ident_name': 'Duplicate name on attachments : %s'})


class DocumentReceiveSetRequests(model.CoopView):
    'Document Receive Set Requests'

    __name__ = 'document.receive.set_requests'

    documents = fields.One2Many('document.request', '', 'Documents', size=1)


class DocumentReceive(Wizard):
    'Document Receive'

    __name__ = 'document.receive'

    start_state = 'start'
    start = StateTransition()
    select_instance = StateView('document.receive.request',
        'document_request.document_receive_request_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'attachment_setter', 'tryton-ok')])
    attachment_setter = StateView('document.receive.attach',
        'document_request.document_receive_attach_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'only_store', 'tryton-go-next')])
    only_store = StateTransition()
    store_attachments = StateTransition()
    store_and_reconcile = StateTransition()
    input_document = StateView('document.receive.set_requests',
        'document_request.document_receive_set_requests_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Complete', 'notify_request', 'tryton-ok')])
    notify_request = StateTransition()
    try_to_go_forward = StateTransition()

    @classmethod
    def __setup__(cls):
        super(DocumentReceive, cls).__setup__()
        cls._error_messages.update({
                'no_document_request_found': 'No document request found for '
                'this object'})

    def default_select_instance(self, name):
        if not(Transaction().context.get('active_model', 'z') in [
                k[0] for k in self.select_instance._fields['kind'].selection]):
            return {}

        GoodModel = Pool().get(Transaction().context.get('active_model'))
        good_id = Transaction().context.get('active_id')

        result = {'kind': Transaction().context.get('active_model')}
        for key, field in self.select_instance._fields.iteritems():
            if not key.startswith('tmp_'):
                continue
            if field.model_name == Transaction().context.get('active_model'):
                result[key] = Transaction().context.get('active_id')
                try:
                    result['request'] = GoodModel(good_id).documents[0].id
                except:
                    self.raise_user_error('no_document_request_found')
                break

        return result

    def transition_start(self):
        if Transaction().context.get('active_model', '') == 'ir.ui.menu':
            return 'select_instance'

        GoodModel = Pool().get(Transaction().context.get('active_model'))
        good_id = Transaction().context.get('active_id')

        self.select_instance.kind = Transaction().context.get('active_model')
        for key, field in self.select_instance._fields.iteritems():
            if not key.startswith('tmp_'):
                continue
            if field.model_name == Transaction().context.get('active_model'):
                setattr(
                    self.select_instance, key,
                    Transaction().context.get('active_id'))
                try:
                    self.select_instance.request = \
                        GoodModel(good_id).documents[0].id
                except:
                    self.raise_user_error('no_document_request_found')
                break

        return 'attachment_setter'

    def default_attachment_setter(self, name):
        Attachment = Pool().get('ir.attachment')
        if not (hasattr(self.select_instance, 'request') and
                self.select_instance.request):
            return {'resource': self.select_instance.value}
        good_obj = self.select_instance.request.needed_by
        good_obj = utils.convert_to_reference(good_obj)
        return {
            'resource': good_obj,
            'attachments': [att.id for att in Attachment.search(
                [
                    ('resource', '=', good_obj),
                ])]}

    def default_input_document(self, name):
        return {'documents': [self.select_instance.request.id]}

    def transition_only_store(self):
        if (hasattr(self.select_instance, 'request') and
                self.select_instance.request):
            return 'store_and_reconcile'
        else:
            return 'store_attachments'

    def update_attachments(self, resource):
        Attachment = Pool().get('ir.attachment')
        previous = Attachment.search([('resource', '=', resource)])
        current = [k.id for k in self.attachment_setter.attachments]
        with Transaction().set_context(_force_access=True):
            for prev_att in previous:
                if prev_att.id not in current:
                    prev_att.delete([prev_att])
            for att in self.attachment_setter.attachments:
                if isinstance(att.data, int):
                    continue
                att.resource = resource
                att.save()

    def transition_store_attachments(self):
        resource = self.select_instance.value
        if resource:
            self.update_attachments(resource)
        return 'end'

    def transition_store_and_reconcile(self):
        resource = self.select_instance.request.needed_by
        resource = utils.convert_to_reference(resource)
        self.update_attachments(resource)
        return 'input_document'

    def transition_notify_request(self):
        for doc in self.input_document.documents[0].documents:
            doc.save()
        self.input_document.documents[0].save()
        if self.input_document.documents[0].is_complete:
            self.input_document.documents[0].notify_completed()

        return 'try_to_go_forward'

    def transition_try_to_go_forward(self):
        # try:
            # obj = self.select_instance.request.needed_by
            # obj.build_instruction_method('next')([obj])
        # except AttributeError:
            # pass

        return 'end'
