import copy
import functools

from lxml import etree

from trytond.tools import safe_eval

from trytond.rpc import RPC

from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool

from trytond.modules.coop_utils import model

from trytond.transaction import Transaction

from trytond.model import Workflow, ModelView
from trytond.model.modelview import _inherit_apply

try:
    import simplejson as json
except ImportError:
    import json


__all__ = ['RichWorkflow']


class DuplicateStateDefinition(Exception):
    pass


class RichWorkflow(Workflow, model.CoopView):
    'Rich Workflow'

    __name__ = 'process.rich_workflow'

    # We need to know the history of the states in order to navigate properly
    states_history = fields.Text(
        'States History',
        states={
            'invisible': True
        },)

    # We plug a selection field on this history to be able to jump around
    history = fields.Function(
        fields.Selection(
            'get_history_selection',
            'History',
            depends=['states_history'],
            context={
                'good_history': Eval('states_history'),
            },
        ),
        'get_history_value',
        'set_history_value',
    )

    @classmethod
    def __setup__(cls):
        super(RichWorkflow, cls).__setup__()

        state_elems = []

        # Set up default state for workflow states
        for elem, elem_name in [(getattr(cls, x), x)
                for x in dir(cls)
                if x.startswith('workflow_')]:
            if not isinstance(elem, fields.Char):
                continue

            @classmethod
            def default_state(cls):
                w_field = Transaction().context.get('workflow_field')
                w_value = Transaction().context.get('workflow_value')
                if not w_field or w_field != elem_name or not w_value:
                    return ''
                return w_value

            setattr(cls, 'default_%s' % elem_name, default_state)

            elem = copy.copy(elem)
            if not elem.states:
                elem.states = {}
            elem.states.update({'invisible': True})
            setattr(cls, elem_name, elem)

            state_elems.append(elem_name)

        # We need to create function fields to calculate whether a given button
        # should be displayed or not
        for elem in cls.technical_states():
            field = fields.Function(
                fields.Boolean(
                    'Display %s' % elem,
                    depends=state_elems,
                    states={
                        'invisible': True
                    },
                ),
                'must_display_field')
            setattr(cls, 'display_%s' % elem, field)

            setattr(cls, 'default_display_%s' % elem, functools.partial(
                cls.default_generic_display,
                name=elem))

            cls._buttons.update({
                'transition_%s' % elem :
                    {'readonly': ~Eval('display_%s' % elem)}})

            cls.__rpc__['get_history_selection'] = RPC()

    @classmethod
    def default_generic_display(cls, name):
        try:
            good_step = cls.get_good_step_from_context()
        except ValueError:
            return False

        return good_step.get_button('button_%s' % name)

    @classmethod
    def get_history_selection(cls):
        field_name = Transaction().context.get('workflow_field')
        state_histo = Transaction().context.get('good_history')
        field_value = Transaction().context.get('workflow_value')

        if not field_name:
            return []

        todo = False

        if not state_histo:
            if field_value:
                cur_hist = {field_name: [field_value]}
            else:
                return []
        else:
            cur_hist = json.loads(state_histo)
            if not field_name in cur_hist or not cur_hist[field_name]:
                cur_hist[field_name] = [field_value]
            else:
                todo = True

        res = []
        StepDesc = Pool().get('process.step_desc')
        for elem in cur_hist[field_name]:
            the_step, = StepDesc.search([
                    ('step_technical_name', '=', elem),
                    ('main_model.model', '=', cls.__name__),
                    ('process_field.name', '=', field_name),
                ], limit=1)
            res.append((the_step.step_technical_name, the_step.step_name))

        if todo:
            res.append((
                the_step.next_steps[0].step_technical_name,
                the_step.next_steps[0].step_name))

        return res

    def get_history_value(self, name):
        field_name = Transaction().context.get('workflow_field')
        if not field_name:
            return

        return getattr(self, field_name)

    @classmethod
    def get_model_field_from_context(cls):
        # TODO : Cache !
        w_field = Transaction().context.get('workflow_field')
        if not w_field:
            raise ValueError
        Model = Pool().get('ir.model')
        good_model, = Model.search([
                ('model', '=', cls.__name__),
            ], limit=1)
        Field = Pool().get('ir.model.field')
        good_field, = Field.search([
                ('model', '=', good_model),
                ('name', '=', w_field),
            ], limit=1)
        return (good_model, good_field)

    @classmethod
    def get_good_field_from_context(cls):
        return Transaction().context.get('workflow_field')

    @classmethod
    def get_good_step_from_context(cls, value=None):
        try:
            good_model, good_field = cls.get_model_field_from_context()
        except ValueError:
            raise

        if not value:
            value = Transaction().context.get('workflow_value')

        StepDesc = Pool().get('process.step_desc')
        good_step, = StepDesc.search([
            ('main_model', '=', good_model),
            ('step_technical_name', '=', value),
            ('process_field', '=', good_field)], limit=1)

        return good_step

    def must_display_field(self, name):
        w_field = Transaction().context.get('workflow_field')
        try:
            good_step = self.get_good_step_from_context(
                value=getattr(self, w_field))
        except ValueError:
            return False

        return good_step.get_button('button_%s' % name[8:])

    @classmethod
    def technical_states(cls):
        # Technical states to be mapped on buttons :
        #  - Next : calls check methods, post methods, calculate next step
        #           and calls pre methods.
        #  - Previous : calls pre methods of the previous step.
        #  - Check : calls the check methods of the current state.
        #  - Cancel : cancels the process.
        return ('next', 'previous', 'check', 'cancel')

    def parse_history(self):
        if not (hasattr(self, 'states_history') and self.states_history):
            return {}

        hist = json.loads(self.states_history)

        return hist

    def update_history(self, value):
        self.states_history = json.dumps(value)

    @classmethod
    def compute_before(cls, step_desc, work):
        step_desc.apply_these_methods('before', work)

    @classmethod
    def compute_after(cls, step_desc, work):
        # First step : we check that the data input is coherent
        step_desc.apply_these_methods('check', work)

        # Next : we update the core objects through the update method
        step_desc.apply_these_methods('update', work)

        # We got to check that the update worked properly
        step_desc.apply_these_methods('validate', work)

        # Finally : call the after methods
        step_desc.apply_these_methods('after', work)

    def get_step_desc(self):
        good_field = self.get_good_field_from_context()
        good_value = getattr(self, good_field)
        return self.get_good_step_from_context(value=good_value)

    def get_workflow_state(self):
        return getattr(self, self.get_good_field_from_context())

    # This method defines the 'next' transition. It should be accessible from
    # each non-technical step.
    #
    # It will usually be displayed as a button, hence the CoopView.button
    # decorator.
    @classmethod
    @model.CoopView.button
    def transition_next(cls, works):

        field_name = Transaction().context.get('workflow_field')

        for work in works:
            step_desc = work.get_step_desc()

            work.compute_after(step_desc, work)

            next_step = step_desc.next_step(work)

            cur_hist = work.parse_history()

            if field_name not in cur_hist:
                cur_hist[field_name] = []

            cur_hist[field_name].append(work.get_workflow_state())

            work.update_history(cur_hist)

            work.compute_before(next_step, work)

            setattr(work, field_name, next_step.step_technical_name)

            work.save()

    @classmethod
    @model.CoopView.button
    def transition_previous(cls, works):

        field_name = Transaction().context.get('workflow_field')

        for work in works:
            cur_hist = work.parse_history()

            print cur_hist

            next_step_name = cur_hist[field_name][-1]

            next_step_desc = work.get_good_step_from_context(next_step_name)

            work.compute_before(next_step_desc, work)

            cur_hist[field_name] = cur_hist[field_name][:-1]

            work.update_history(cur_hist)

            setattr(work, field_name, next_step_desc.step_technical_name)

            work.save()

    @classmethod
    @model.CoopView.button
    @Workflow.transition('check')
    def transition_check(cls, works):
        pass

    @classmethod
    @model.CoopView.button
    @Workflow.transition('cancel')
    def transition_cancel(cls, works):
        pass

    @classmethod
    def get_process_name(cls):
        return ''

    @staticmethod
    def def_meth(fancy_name, meth_type, long_desc):
        def real_decorator(function):
            def wrapper(*args, **kwargs):
                function(*args, **kwargs)
            wrapper.def_meth = {
                'fancy_name': fancy_name,
                'meth_type': meth_type,
                'long_desc': long_desc}
            return wrapper
        return real_decorator

    @classmethod
    def calculate_form(cls, w_field, w_value, view_id=None, view_type='form'):
        key = (cls.__name__, view_id, view_type, w_field, w_value)
        #result = cls._fields_view_get_cache.get(key)
        #if result:
            #return result
        result = {'model': 'process.rich_workflow'}
        pool = Pool()
        View = pool.get('ir.ui.view')

        test = True
        model = True
        view = None
        inherit_view_id = False
        while test:
            if view_id:
                domain = [('id', '=', view_id)]
                if model:
                    domain.append(('model', '=', 'process.rich_workflow'))
                views = View.search(domain, order=[])
            else:
                domain = [
                    ('model', '=', 'process.rich_workflow'),
                    ('type', '=', view_type),
                    ]
                order = [
                    ('inherit', 'DESC'),
                    ('priority', 'ASC'),
                    ('id', 'ASC'),
                    ]
                views = View.search(domain, order=order)
            if not views:
                break
            view = views[0]
            test = view.inherit
            if test:
                inherit_view_id = view.id
            view_id = test.id if test else view.id
            model = False

        # if a view was found
        if view:
            result['type'] = view.type
            result['view_id'] = view_id
            result['arch'] = view.arch
            result['field_childs'] = view.field_childs

            # Check if view is not from an inherited model
            if view.model != 'process.rich_workflow':
                Inherit = pool.get(view.model)
                result['arch'] = Inherit.fields_view_get(
                        result['view_id'])['arch']
                view_id = inherit_view_id

            # get all views which inherit from (ie modify) this view
            views = View.search([
                    'OR', [
                        ('inherit', '=', view_id),
                        ('model', '=', 'process.rich_workflow'),
                        ], [
                        ('id', '=', view_id),
                        ('inherit', '!=', None),
                        ],
                    ],
                order=[
                    ('priority', 'ASC'),
                    ('id', 'ASC'),
                    ])
            raise_p = False
            while True:
                try:
                    views.sort(key=lambda x:
                        cls._modules_list.index(x.module or None))
                    break
                except ValueError:
                    if raise_p:
                        raise
                    # There is perhaps a new module in the directory
                    ModelView._reset_modules_list()
                    raise_p = True
            for view in views:
                if view.domain:
                    if not safe_eval(view.domain,
                            {'context': Transaction().context}):
                        continue
                if not view.arch or not view.arch.strip():
                    continue
                result['arch'] = _inherit_apply(result['arch'], view.arch)

            result['arch'] = _inherit_apply(
                result['arch'],
                cls.build_workflow_view(w_field, w_value))

        # Update arch and compute fields from arch
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(result['arch'], parser)
        xarch, xfields = cls._view_look_dom_arch(tree, result['type'],
                result['field_childs'])
        result['arch'] = xarch
        result['fields'] = xfields

        cls._fields_view_get_cache.set(key, result)
        return result

    @classmethod
    def build_workflow_view(cls, w_field, w_value):
        Model = Pool().get('ir.model')
        good_model, = Model.search([
            ('model', '=', cls.__name__)], limit=1)
        Field = Pool().get('ir.model.field')
        good_field, = Field.search([
            ('model', '=', good_model),
            ('name', '=', w_field)], limit=1)
        StepDesc = Pool().get('process.step_desc')
        good_step, = StepDesc.search(
            [
                ('main_model', '=', good_model),
                ('process_field', '=', good_field),
                ('step_technical_name', '=', w_value),
            ], limit=1)
        transitions = {}
        good_step.calculate_transitions(transitions)
        steps = transitions.keys()
        xml = '<?xml version="1.0"?>'
        xml += '<data>'
        xml += '<xpath expr="/form" position="replace_attributes">'
        xml += '<form string="%s"/>' % cls.get_process_name()
        xml += '</xpath>'
        xml += "<xpath expr='/form/group[@id=\"process_header\"]' "
        xml += "position='inside'>"
        xml += '<field name="%s"/>' % w_field
        xml += '</xpath>'
        xml += "<xpath expr='/form/group[@id=\"process_body\"]' "
        xml += "position='inside'>"
        for step in steps:
            step_obj, = StepDesc.search([
                ('main_model', '=', good_model),
                ('process_field', '=', good_field),
                ('step_technical_name', '=', step)], limit=1)
            xml += '<newline/>'
            xml += '<group id="group_%s" ' % step_obj.step_technical_name
            xml += 'xfill="1" xexpand="1" yfill="1" yexpand="1" '
            xml += 'states="{\'invisible\': Eval(\'%s\') != \'%s\'}">' % (
                good_field.name, step_obj.step_technical_name)
            xml += step_obj.step_xml.strip()
            xml += '</group>'
        xml += '</xpath>'
        xml += '</data>'
        print xml

        return xml

    @classmethod
    def fields_view_get(cls, view_ids=None, view_type='form'):
        if cls.__name__ == 'process.rich_workflow':
            return super(
                RichWorkflow, cls).fields_view_get(view_ids, view_type)
        w_field = Transaction().context.get('workflow_field')
        w_value = Transaction().context.get('workflow_value')
        if not w_field or not w_value:
            return super(
                RichWorkflow, cls).fields_view_get(view_ids, view_type)
        if view_type == 'form':
            return cls.calculate_form(w_field, w_value)
        elif view_type == 'tree':
            return super(
                RichWorkflow, cls).fields_view_get(view_ids, view_type)

