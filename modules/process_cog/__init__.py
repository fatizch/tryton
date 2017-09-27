# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.config import config
import process
import process_timings
import models_for_test
import event
import document
import wizard


def register():
    Pool.register(
        process.Status,
        process.ProcessAction,
        process.ProcessLog,
        process.ProcessTransition,
        process.ProcessStepRelation,
        process.Process,
        process.ViewDescription,
        process.ProcessStep,
        process.ProcessStart,
        process.PostponeParameters,
        process_timings.ProcessTimingDisplayer,
        process_timings.ProcessTimingSelectDates,
        event.EventTypeAction,
        document.ReattachDocument,
        wizard.ImportProcessDisplayer,
        wizard.ImportProcessSelect,
        module='process_cog', type_='model')

    Pool.register(
        process.GenerateGraph,
        module='process_cog', type_='report')

    Pool.register(
        process.ProcessFinder,
        process.ProcessEnd,
        process.ProcessResume,
        process.PostponeTask,
        process_timings.GetDatesForProcessTimings,
        process_timings.ProcessTimings,
        document.ReceiveDocument,
        wizard.ImportProcess,
        module='process_cog', type_='wizard')

    if config.get('env', 'testing') == 'True':
        Pool.register(
            models_for_test.ModelProcess,
            module='process_cog', type_='model')
