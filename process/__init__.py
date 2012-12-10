from trytond.pool import Pool
from .test_process import *
from .test_process_framework import *


def register():
    Pool.register(
        # From process_labo :
        StepDesc,
        StepTransition,
        TransitionAuthorization,
        ProcessDesc,
        ProcessStepRelation,
        
        # From process :
        Model,
        ProcessFramework,
        module='process', type_='model')
