# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import ir
import process
import configuration

from process_framework import ProcessFramework, ClassAttr  # NOQA


def register():
    Pool.register(
        process.Status,
        process.ProcessStep,
        process.Process,
        process.ProcessTransition,
        process.ProcessAction,
        process.TransitionAuthorization,
        process.ProcessMenuRelation,
        process.ProcessStepRelation,
        process.StepGroupRelation,
        process.ProcessActWindow,
        ir.Model,
        configuration.ProcessConfiguration,
        module='process', type_='model')

    Pool.register(
        process.GenerateGraphWizard,
        module='process', type_='wizard')

    Pool.register(
        process.GenerateGraph,
        module='process', type_='report')
