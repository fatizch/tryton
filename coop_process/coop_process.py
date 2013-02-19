import copy
import sys
import pydot

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.model import fields

from trytond.modules.coop_utils import utils

from trytond.modules.process import ProcessFramework


__all__ = [
    'StepTransition',
    'GenerateGraph',
    'CoopProcessFramework',
    'ProcessDesc',
    'StepDesc',
]


class StepTransition():
    'Step Transition'

    __metaclass__ = PoolMeta

    __name__ = 'process.step_transition'

    pyson_choice = fields.Char(
        'Choice',
        states={
            'invisible': Eval('kind') != 'choice',
        },
    )

    pyson_description = fields.Char(
        'Pyson Description',
        states={
            'invisible': Eval('kind') != 'choice',
        },
    )

    choice_if_true = fields.Many2One(
        'process.step_transition',
        'Transition if True',
        states={
            'invisible': Eval('kind') != 'choice',
        },
        domain=[('kind', '=', 'calculated')],
    )

    choice_if_false = fields.Many2One(
        'process.step_transition',
        'Transition if False',
        states={
            'invisible': Eval('kind') != 'choice',
        },
        domain=[('kind', '=', 'calculated')],
    )

    @classmethod
    def __setup__(cls):
        super(StepTransition, cls).__setup__()
        kind = copy.copy(cls.kind)
        kind.selection.append(('calculated', 'Calculated'))
        setattr(cls, 'kind', kind)

        cls._error_messages.update({
            'missing_pyson': 'Pyson expression and description is mandatory',
            'missing_choice': 'Both choices must be filled !',
        })

        cls._constraints += [
            ('check_pyson', 'missing_pyson'),
            ('check_choices', 'missing_choice'),
        ]

    def execute(self, target):
        if self.kind != 'choice':
            super(StepTransition, self).execute(target)
            return

        result = utils.pyson_result(self.pyson_choice, target)

        if result:
            self.choice_if_true.execute(target)
        else:
            self.choice_if_false.execute(target)

    def get_rec_name(self, name):
        if self.kind != 'choice':
            return super(StepTransition, self).get_rec_name(name)

        return self.pyson_description

    def build_button(self):
        if self.kind != 'choice':
            return super(StepTransition, self).build_button()

        xml = '<button string="%s" name="_button_%s"/>' % (
            self.get_rec_name(''),
            self.id)

        return xml

    def check_pyson(self):
        if self.kind != 'choice':
            return True

        if not self.pyson_choice or not self.pyson_description:
            return False

        return True

    def check_choices(self):
        if self.kind != 'choice':
            return True

        if not self.choice_if_true or not self.choice_if_false:
            return False

        return True


class GenerateGraph():
    'Generate Graph'

    __metaclass__ = PoolMeta

    __name__ = 'process.graph_generation'

    @classmethod
    def build_transition(cls, process, step, transition, graph, nodes, edges):
        if not transition.kind == 'choice':
            super(GenerateGraph, cls).build_transition(
                process, step, transition, graph, nodes, edges)
            return

        choice_node = pydot.Node(
            transition.pyson_description,
            style='filled',
            shape='diamond',
            fillcolor='orange',
            fontname='Century Gothic',
        )

        nodes['tr%s' % transition.id] = choice_node

        choice_edge = pydot.Edge(
            nodes[transition.from_step.id],
            choice_node,
            fontname='Century Gothic',
        )

        edges[(transition.from_step.id, 'tr%s' % transition.id)] = choice_edge

        true_edge = pydot.Edge(
            choice_node,
            nodes[transition.choice_if_true.to_step.id],
            fontname='Century Gothic',
        )

        true_edge.set('len', '1.0')
        true_edge.set('constraint', '1')
        true_edge.set('weight', '0.5')
        true_edge.set('label', 'Yes')
        true_edge.set('color', 'green')

        edges[(
            'tr%s' % transition.id,
            transition.choice_if_true.to_step.id)] = true_edge

        false_edge = pydot.Edge(
            choice_node,
            nodes[transition.choice_if_false.to_step.id],
            fontname='Century Gothic',
        )

        false_edge.set('len', '1.0')
        false_edge.set('constraint', '1')
        false_edge.set('weight', '0.5')
        false_edge.set('label', 'No')
        false_edge.set('color', 'red')

        edges[(
            'tr%s' % transition.id,
            transition.choice_if_false.to_step.id)] = false_edge


class CoopProcessFramework(ProcessFramework):
    'Coop Process Framework'

    def get_next_transition(self):
        if not self.current_state:
            return

        from_step = self.current_state.step
        for_process = self.current_state.process

        return for_process.get_next_transition(from_step, self)

    def get_previous_transition(self):
        if not self.current_state:
            return

        from_step = self.current_state.step
        for_process = self.current_state.process

        return for_process.get_previous_transition(from_step, self)

    @classmethod
    def build_instruction_method(cls, instruction):
        if instruction == 'next':
            def next(works):
                for work in works:
                    good_trans = work.get_next_transition()
                    if good_trans:
                        good_trans.execute(work)
                        work.save()

            return next
        elif instruction == 'previous':
            def previous(works):
                for work in works:
                    good_trans = work.get_previous_transition()
                    if good_trans:
                        good_trans.execute(work)
                        work.save()

            return previous
        else:
            return super(CoopProcessFramework, cls).build_instruction_method(
                instruction)

    @classmethod
    def special_button_states(cls, transition_id):
        if transition_id[1] in ('next', 'previous'):
            return {}

        return super(CoopProcessFramework, cls).special_button_states(
            transition_id)


class ProcessDesc():
    'Process Descriptor'

    __metaclass__ = PoolMeta

    __name__ = 'process.process_desc'

    with_prev_next = fields.Boolean(
        'With Previous / Next button',
    )

    @classmethod
    def default_with_prev_next(cls):
        return True

    def get_next_transition(self, from_step, for_task):
        step_order = dict(
            [(rel.step.id, rel.order) for rel in self.all_steps])

        def get_priority(step):
            return step_order[step.id]

        good_values = []
        for transition in self.transitions:
            if not transition.from_step == from_step:
                continue
            if transition.kind == 'standard':
                if transition.is_forward():
                    good_values.append(
                        (get_priority(transition.to_step), transition))
                elif transition.kind == 'complete':
                    good_values.append(
                        (sys.maxint, transition))
            elif transition.kind == 'choice':
                good_values.append((
                    min(get_priority(transition.choice_if_true),
                        get_priority(transition.choice_if_false)),
                    transition))

        if not good_values:
            return

        good_values.sort(key=lambda x: x[0])

        for _, trans in good_values:
            if not for_task.is_button_available(trans):
                continue

            return trans

    def get_previous_transition(self, from_step, for_task):
        step_order = dict(
            [(rel.step.id, rel.order) for rel in self.all_steps])

        def get_priority(step):
            return step_order[step.id]

        good_values = []
        for transition in self.transitions:
            if not transition.from_step == from_step:
                continue

            if transition.kind == 'standard':
                if not transition.is_forward():
                    good_values.append(
                        (get_priority(transition.to_step), transition))

        if not good_values:
            return

        good_values.sort(key=lambda x: x[0])

        for _, trans in reversed(good_values):
            if not for_task.is_button_available(trans):
                continue

            return trans


class StepDesc():
    'Step Desc'

    __metaclass__ = PoolMeta

    __name__ = 'process.step_desc'

    def calculate_form_view(self, process, buttons):
        result = super(StepDesc, self).calculate_form_view(process, buttons)
        if not process.with_prev_next:
            return result

        result += '<newline/>'
        result += '<group name="group_%s_prevnext">' % self.id
        if not process.first_step().step.id == self.id:
            result += '<button string="Previous"'
            result += ' name="_button_%s_previous"/>' % self.id
        result += '<button string="Next" name="_button_%s_next"/>' % (
            self.id)
        result += '</group>'

        return result
