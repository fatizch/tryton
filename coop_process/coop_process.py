import copy
import datetime
import time

import pydot

from trytond.pool import PoolMeta
from trytond.pyson import Eval, And, PYSONDecoder, PYSONEncoder, CONTEXT
from trytond.tools import safe_eval

from trytond.transaction import Transaction

from trytond.model.modelstorage import EvalEnvironment



from trytond.model import fields


__all__ = [
    'StepTransition',
    'GenerateGraph',
]


class StepTransition():
    'Step Transition'

    __metaclass__ = PoolMeta

    __name__ = 'process.step_transition'

    transition_kind = fields.Selection(
        [
            ('standard', 'Standard'),
            ('choice', 'Choice')
        ],
        'Transition Kind',
    )

    pyson_choice = fields.Char(
        'Choice',
        states={
            'invisible': Eval('transition_kind') != 'choice',
        },
    )

    pyson_description = fields.Char(
        'Pyson Description',
        states={
            'invisible': Eval('transition_kind') != 'choice',
        },
    )

    choice_if_true = fields.Many2One(
        'process.step_transition',
        'Transition if True',
        states={
            'invisible': Eval('transition_kind') != 'choice',
        },
        domain=[('kind', '=', 'calculated')],
    )

    choice_if_false = fields.Many2One(
        'process.step_transition',
        'Transition if False',
        states={
            'invisible': Eval('transition_kind') != 'choice',
        },
        domain=[('kind', '=', 'calculated')],
    )

    @classmethod
    def __setup__(cls):
        super(StepTransition, cls).__setup__()
        for attr in ('to_step', 'methods'):
            the_attr = copy.copy(getattr(cls, attr))
            if not the_attr.states:
                the_attr.states = {}
            if not 'invisible' in the_attr.states:
                the_attr.states['invisible'] = ''

            if not the_attr.states['invisible']:
                the_attr.states['invisible'] = \
                    Eval('transition_kind') == 'choice'
            else:
                the_attr.states['invisible'] = And(
                    the_attr.states['invisible'],
                    Eval('transition_kind') == 'choice')

            setattr(cls, attr, the_attr)

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

    @classmethod
    def default_transition_kind(cls):
        return 'standard'

    def execute(self, target):
        if self.transition_kind != 'choice':
            super(StepTransition, self).execute(target)
            return

        encoder = PYSONEncoder()
        the_pyson = encoder.encode(safe_eval(self.pyson_choice, CONTEXT))

        env = EvalEnvironment(target, target.__class__)
        env.update(Transaction().context)
        env['current_date'] = datetime.datetime.today()
        env['time'] = time
        env['context'] = Transaction().context
        env['active_id'] = target.id
        result = PYSONDecoder(env).decode(the_pyson)

        if result:
            self.choice_if_true.execute(target)
        else:
            self.choice_if_false.execute(target)

    def get_rec_name(self, name):
        if self.transition_kind != 'choice':
            return super(StepTransition, self).get_rec_name(name)

        return self.pyson_description

    def build_button(self):
        if self.transition_kind != 'choice':
            return super(StepTransition, self).build_button()

        xml = '<button string="%s" name="_button_%s"/>' % (
            self.get_rec_name(''),
            self.id)

        return xml

    def check_pyson(self):
        if self.transition_kind != 'choice':
            return True

        if not self.pyson_choice or not self.pyson_description:
            return False

        return True

    def check_choices(self):
        if self.transition_kind !='choice':
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
        if not transition.transition_kind == 'choice':
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
        #true_edge.set('label', 'Yes')
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
        #false_edge.set('label', 'No')
        false_edge.set('color', 'red')

        edges[(
            'tr%s' % transition.id,
            transition.choice_if_false.to_step.id)] = false_edge

