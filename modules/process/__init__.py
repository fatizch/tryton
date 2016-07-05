# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .process import *
from .ir import *
from .process_framework import *


def register():
    Pool.register(
        # From process
        Status,
        ProcessStep,
        Process,
        ProcessTransition,
        ProcessAction,
        TransitionAuthorization,
        ProcessMenuRelation,
        ProcessStepRelation,
        StepGroupRelation,
        # From ir
        Model,
        # From process_framework
        ProcessActWindow,
        module='process', type_='model')

    Pool.register(
        # From process_desc
        GenerateGraphWizard,
        module='process', type_='wizard')

    Pool.register(
        # From process_desc
        GenerateGraph,
        module='process', type_='report')
