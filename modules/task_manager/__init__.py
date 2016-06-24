from trytond.pool import Pool
from .res import *
from .task_dispatcher import *


def register():
    Pool.register(
        Team,
        TeamGroupRelation,
        Priority,
        User,
        ProcessLog,
        UserTeamRelation,
        module='task_manager', type_='model')
    Pool.register(
        TaskDispatcher,
        LaunchTask,
        module='task_manager', type_='wizard')
