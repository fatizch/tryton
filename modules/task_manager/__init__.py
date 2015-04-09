from trytond.pool import Pool
from .ir import *
from .res import *
from .task_dispatcher import *


def register():
    Pool.register(
        Team,
        TeamGroupRelation,
        Priority,
        Session,
        User,
        ProcessLog,
        UserTeamRelation,
        module='task_manager', type_='model')
    Pool.register(
        TaskDispatcher,
        LaunchTask,
        module='task_manager', type_='wizard')
