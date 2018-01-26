# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json

from trytond.pool import PoolMeta, Pool
from trytond.pyson import PYSONEncoder
from trytond.modules.coog_core import fields

__all__ = ['User']
__metaclass__ = PoolMeta


class User:
    __metaclass__ = PoolMeta
    __name__ = 'res.user'
    party_synthesis = fields.Char('Synthesis Parties')
    party_synthesis_previous = fields.Char('Previous Synthesis Parties')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls.__rpc__['get_preferences'].readonly = False

    def get_pyson_menu(self, name):
        pool = Pool()
        Action = pool.get('ir.action')
        ModelData = pool.get('ir.model.data')

        menu = super(User, self).get_pyson_menu(name)

        if self.party_synthesis:
            encoder = PYSONEncoder()
            action_id = Action.get_action_id(
                ModelData.get_id('party_cog', 'act_menu_form'))
            action = Action(action_id)
            action, = Action.get_action_values(action.type, [action.id])
            ids = json.loads(self.party_synthesis)
            action['pyson_domain'] = encoder.encode(
                [('party', 'in', ids), ('parent', '=', None)])
            action['pyson_context'] = encoder.encode({
                    'party_synthesis': ids,
                    })
            return encoder.encode(action)
        return menu
