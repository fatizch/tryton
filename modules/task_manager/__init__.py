from trytond.pool import Pool
from .task_manager import *
from .task_dispatcher import *


def register():
    Pool.register(
        # From file task_manager :
        Team,
        TeamGroupRelation,
        Priority,
        User,
        Session,
        SelectUser,
        # From file task_dispatcher
        ProcessLog,
        TaskDisplayer,
        TaskSelector,
        module='task_manager', type_='model')

    Pool.register(
        # From file task_manager :
        AddTeamUser,
        # From file task_dispatcher
        TaskDispatcher,
        LaunchTask,
        module='task_manager', type_='wizard')
