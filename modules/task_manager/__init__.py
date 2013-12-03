from trytond.pool import Pool
from .task_manager import *
from .ir import *
from .res import *
from .task_dispatcher import *


def register():
    Pool.register(
        # From task_manager
        Team,
        TeamGroupRelation,
        Priority,
        SelectUser,
        # From ir
        Session,
        # From res
        User,
        # From task_dispatcher
        ProcessLog,
        TaskDisplayer,
        TaskSelector,
        module='task_manager', type_='model')

    Pool.register(
        # From task_manager
        AddTeamUser,
        # From task_dispatcher
        TaskDispatcher,
        LaunchTask,
        module='task_manager', type_='wizard')
