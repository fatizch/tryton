# -*- coding: utf-8 -*-
from proteus import Model
from proteus_launcher import configure_proteus
import proteus_tools


config = configure_proteus()

StepDesc = Model.get('process.step_desc')

steps = StepDesc.find([])

data = ['[StepDesc]']
for step in steps:
    step_data = [
        '%s' % step.main_model.id,
        '%s' % step.id,
        ','.join(step.code_before.split('\n')) if step.code_before else '',
        ','.join(step.code_after.split('\n')) if step.code_after else '']
    data.append('|'.join(step_data))

StepTransition = Model.get('process.step_transition')

transitions = StepTransition.find([])

data.append('')
data.append('[StepTransition]')
for transition in transitions:
    transition_data = [
        '%s' % transition.on_process.on_model.id,
        '%s' % transition.id,
        ','.join(transition.methods.split(
            '\n')) if transition.methods else '']
    data.append('|'.join(transition_data))

data.append('')
proteus_tools.write_data_file('tmp_migrate_step_desc', data)
