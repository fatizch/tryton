# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.config import config
from . import process
from . import process_timings
from . import models_for_test
from . import event
from . import document
from . import wizard


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
        wizard.ImportProcess,
        module='process_cog', type_='wizard')

    Pool.register(
        document.ReattachDocument,
        module='process_cog', type_='model',
        depends=['document_request'])

    Pool.register(
        document.ReceiveDocument,
        module='process_cog', type_='wizard',
        depends=['document_request'])

    if config.getboolean('env', 'testing') is True:
        Pool.register(
            models_for_test.ModelProcess,
            module='process_cog', type_='model')
