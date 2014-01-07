from trytond.pool import Pool
from .process import *
from .ir import *
from .process_framework import *


def register():
    Pool.register(
        # From process
        Status,
        StepDesc,
        ProcessDesc,
        StepTransition,
        Code,
        TransitionAuthorization,
        ProcessMenuRelation,
        ProcessStepRelation,
        StepDescAuthorization,
        # From ir
        WorkflowModel,
        # From process_framework
        ProcessFramework,
        module='process', type_='model')

    Pool.register(
        # From process_desc
        GenerateGraphWizard,
        module='process', type_='wizard')

    Pool.register(
        # From process_desc
        GenerateGraph,
        module='process', type_='report')
