# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gettext

from tryton.action import Action
from tryton.common import RPCExecute, RPCException

_ = gettext.gettext


def debug_object(data):
    model = data['model']
    record_ids = data['ids']

    if not model or not record_ids:
        return

    try:
        wiz_info, = RPCExecute('model', 'ir.model.data', 'search_read', [
                ('module', '=', 'debug'),
                ('fs_id', '=', 'act_model_debug'),
                ])
        Action.execute(wiz_info['db_id'], data, 'ir.action.wizard')
    except RPCException:
        return


def get_plugins(model):
    return [
        (_('Debug Object'), debug_object),
        ]
