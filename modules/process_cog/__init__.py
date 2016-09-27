# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.config import config
from .process import *
from .process_timings import *
from .models_for_test import *
from .event import *
from .document import *


def register():
    Pool.register(
        # From process
        Status,
        ProcessAction,
        ProcessLog,
        ProcessTransition,
        ProcessStepRelation,
        Process,
        ViewDescription,
        ProcessStep,
        ProcessStart,
        PostponeParameters,
        ProcessTimingDisplayer,
        ProcessTimingSelectDates,
        EventTypeAction,
        ReattachDocument,
        module='process_cog', type_='model')

    Pool.register(
        GenerateGraph,
        module='process_cog', type_='report')

    Pool.register(
        ProcessFinder,
        ProcessEnd,
        ProcessResume,
        PostponeTask,
        GetDatesForProcessTimings,
        ProcessTimings,
        ReceiveDocument,
        module='process_cog', type_='wizard')

    if config.get('env', 'testing') == 'True':
        Pool.register(
            ModelProcess,
            module='process_cog', type_='model')
