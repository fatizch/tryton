import copy
import pydot

from trytond.pool import PoolMeta, Pool
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

        xml = '<button string="%s" name="_button_transition_%s_%s"/>' % (
            self.get_rec_name(''),
            self.on_process.id,
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

    def get_pyson_readonly(self):
        result = super(StepTransition, self).get_pyson_readonly()
        if result:
            return result

        # Every step should be executable, unless its pyson says no
        if self.kind == 'standard' and \
                self.to_step.get_pyson_for_button():
            result = self.to_step.pyson
        else:
            result = 'False'

        return result


class CoopProcessFramework(ProcessFramework):
    'Coop Process Framework'

    def get_next_execution(self):
        if not self.current_state:
            return

        from_step = self.current_state.step
        for_process = self.current_state.process

        return for_process.get_next_execution(from_step, self)

    def get_previous_execution(self):
        if not self.current_state:
            return

        from_step = self.current_state.step
        for_process = self.current_state.process

        return for_process.get_previous_execution(from_step, self)

    @classmethod
    def build_instruction_next_method(cls, process, data):
        def next(works):
            for work in works:
                good_exec = work.get_next_execution()
                if good_exec:
                    good_exec.execute(work)
                    work.save()

        return next

    @classmethod
    def build_instruction_previous_method(cls, process, data):
        def previous(works):
            for work in works:
                good_exec = work.get_previous_execution()
                if good_exec:
                    good_exec.execute(work)
                    work.save()

        return previous

    @classmethod
    def build_instruction_step_method(cls, process, data):
        def button_step_generic(works):
            StepDesc = Pool().get('process.step_desc')
            target = StepDesc(data[0])

            for work in works:
                target.execute(work)
                work.save()

        return button_step_generic

    @classmethod
    def button_next_states(cls, process, data):
        return {}

    @classmethod
    def button_previous_states(cls, process, data):
        return {}

    @classmethod
    def button_step_states(cls, process, step_data):
        if process.custom_transitions and \
                not process.steps_implicitly_available:
            return {'readonly': True}

        StepDesc = Pool().get('process.step_desc')
        good_step = StepDesc(int(step_data[0]))
        if not good_step.pyson:
            return {}
        else:
            return {'readonly': utils.pyson_encode(good_step.pyson, True)}

    @classmethod
    def button_complete_states(cls, process, step_relation):
        return {}

    @classmethod
    def build_instruction_complete_method(cls, process, data):
        def button_complete_generic(works):
            for work in works:
                work.current_state = None
                work.save

        return button_complete_generic


class ProcessDesc():
    'Process Descriptor'

    __metaclass__ = PoolMeta

    __name__ = 'process.process_desc'

    with_prev_next = fields.Boolean(
        'With Previous / Next button',
    )

    custom_transitions = fields.Boolean(
        'Custom Transitions',
    )

    steps_implicitly_available = fields.Boolean(
        'Steps Implicitly Available',
        states={
            'invisible': ~Eval('custom_transitions')
        },
    )

    @classmethod
    def __setup__(cls):
        super(ProcessDesc, cls).__setup__()
        cls.transitions = copy.copy(cls.transitions)
        cls.transitions.states['invisible'] = ~Eval('custom_transitions')
        cls.transitions.depends.append('custom_transitions')

    @classmethod
    def default_with_prev_next(cls):
        return True

    @classmethod
    def default_custom_transitions(cls):
        return False

    @classmethod
    def default_steps_implicitly_available(cls):
        return True

    def get_next_execution(self, from_step, for_task):
        print '#' * 80
        print '%s' % self.custom_transitions
        print from_step

        from_step.execute_after(for_task)

        cur_step_found = False
        for step_relation in self.all_steps:
            print step_relation
            if step_relation.step == from_step:
                cur_step_found = True
                continue
            if not cur_step_found:
                continue
            # First we look for a matching transition
            if self.custom_transitions:
                print step_relation.step.fancy_name
                for trans in self.transitions:
                    if not trans.from_step == from_step:
                        continue
                    if not trans.to_step == step_relation.step:
                        continue
                    print 'FOUND'
                    if not for_task.is_button_available(self, trans):
                        continue
                    return trans

            if for_task.is_button_available(self, step_relation.step):
                return step_relation.step

    def get_previous_execution(self, from_step, for_task):
        cur_step_found = False
        for step_relation in reversed(self.all_steps):
            if step_relation.step == from_step:
                cur_step_found = True
                continue
            if not cur_step_found:
                continue
            # First we look for a matching transition
            if self.custom_transitions:
                for trans in self.transitions:
                    if not trans.from_step == from_step:
                        continue
                    if not trans.to_step == step_relation.step:
                        continue
                    if not for_task.is_button_available(self, trans):
                        continue
                    return trans

            if for_task.is_button_available(self, step_relation.step):
                return step_relation.step

    def get_xml_footer(self, colspan=4):
        xml = ''
        if self.with_prev_next:
            xml += '<group name="group_prevnext" colspan="4" col="8">'
            xml += '<button string="Previous"'
            xml += ' name="_button_previous_%s"/>' % self.id
            xml += '<group name="void" colspan="6"/>'
            xml += '<button string="Next" '
            xml += 'name="_button_next_%s"/>' % self.id
            xml += '</group>'
            xml += '<newline/>'

        xml += super(ProcessDesc, self).get_xml_footer(colspan)
        return xml

    def calculate_buttons_for_step(self, step_relation):
        if self.custom_transitions:
            return super(ProcessDesc, self).calculate_buttons_for_step(
                step_relation)

        result = {}
        for relation in self.all_steps:
            result[relation.step.id] = ('step', relation.step)

        return result

    def build_step_buttons(self, step_relation):
        nb, result = super(ProcessDesc, self).build_step_buttons(step_relation)
        if not self.custom_transitions and self.all_steps[-1] == step_relation:
            result += '<button string="Complete" '
            result += 'name="_button_complete_%s_%s"/>' % (
                self.id, step_relation.id)

            nb += 1

        return nb, result


class StepDesc():
    'Step Desc'

    __metaclass__ = PoolMeta

    __name__ = 'process.step_desc'

    pyson = fields.Char('Pyson Constraint')

    def get_pyson_for_button(self):
        return self.pyson or ''

    def execute(self, target, execute_after=True):
        origin = target.current_state.step
        if execute_after:
            origin.execute_after(target)
        self.execute_before(target)

        target.set_state(self)


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
