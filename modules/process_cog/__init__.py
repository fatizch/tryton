from trytond.pool import Pool
from trytond.config import config
from .process import *
from .process_timings import *
from .models_for_test import *
from .event import *


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
        module='process_cog', type_='wizard')

    if config.get('env', 'testing') == 'True':
        Pool.register(
            ModelProcess,
            module='process_cog', type_='model')
