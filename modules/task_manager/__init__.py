# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import res
from . import configuration
from . import task_dispatcher
from . import test_case


def register():
    Pool.register(
        task_dispatcher.ProcessLog,
        res.Team,
        res.TeamGroupRelation,
        res.Priority,
        res.User,
        res.UserTeamRelation,
        res.ProcessStepRelation,
        configuration.ProcessConfiguration,
        test_case.TestCaseModel,
        module='task_manager', type_='model')
    Pool.register(
        task_dispatcher.TaskDispatcher,
        task_dispatcher.LaunchTask,
        module='task_manager', type_='wizard')
