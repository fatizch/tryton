import gettext

from tryton.common import RPCExecute, RPCException
from tryton.action import Action

_ = gettext.gettext


def revision_blame(data):

    try:
        ret = RPCExecute('model', 'ir.model.data', 'search_read', [
                ('module', '=', 'coog_core'),
                ('fs_id', '=', 'revision_blame')
                ])[0]
        Action.execute(ret['db_id'], data, 'ir.action.wizard')
    except KeyError:
        return
    except RPCException:
        return


def get_plugins(model):
    return [
        (_('Show Revision History'), revision_blame),
    ]
