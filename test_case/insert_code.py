# -*- coding: utf-8 -*-
from proteus import Model
from proteus_launcher import configure_proteus
import proteus_tools


config = configure_proteus()

Code = Model.get('process.code')
StepDesc = Model.get('process.step_desc')
TransitionDesc = Model.get('process.step_transition')
ModelData = Model.get('ir.model')

for k, v in proteus_tools.read_data_file('tmp_migrate_step_desc').iteritems():
    if k == 'StepDesc':
        sequence = 1
        for line in v:
            model_id, step_id, before, after = line
            if not (before or after):
                continue
            for method_name in before.split(','):
                if not method_name:
                    continue
                the_code = Code()
                the_code.on_model = ModelData(model_id)
                the_code.technical_kind = 'step_before'
                the_code.parent_step = StepDesc(step_id)
                the_code.sequence = sequence
                the_code.method_name = method_name
                the_code.save()
                sequence += 1
            for method_name in after.split(','):
                if not method_name:
                    continue
                the_code = Code()
                the_code.on_model = ModelData(model_id)
                the_code.technical_kind = 'step_after'
                the_code.parent_step = StepDesc(step_id)
                the_code.sequence = sequence
                the_code.method_name = method_name
                the_code.save()
                sequence += 1
    elif k == 'StepTransition':
        sequence = 1
        for line in v:
            model_id, step_id, methods = line
            if not methods:
                continue
            for method_name in methods.split(','):
                if not method_name:
                    continue
                the_code = Code()
                the_code.on_model = ModelData(model_id)
                the_code.technical_kind = 'transition'
                the_code.parent_step = TransitionDesc(step_id)
                the_code.sequence = sequence
                the_code.method_name = method_name
                the_code.save()
                sequence += 1
