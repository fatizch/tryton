from trytond.pool import Pool
from .process_desc import *
from .process_framework import *


def register():
    Pool.register(
        # From process_labo :
        Status,
        StepDesc,
        ProcessDesc,
        StepTransition,
        Code,
        TransitionAuthorization,
        ProcessMenuRelation,
        ProcessStepRelation,
        StepDescAuthorization,

        # From process :
        WorkflowModel,
        ProcessFramework,
        module='process', type_='model')

    Pool.register(
        GenerateGraphWizard,
        module='process', type_='wizard')

    Pool.register(
        GenerateGraph,
        module='process', type_='report')
