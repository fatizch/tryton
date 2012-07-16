#-*- coding:utf-8 -*-
import functools

from trytond.model import fields as fields
from trytond.pyson import Eval

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils, CoopView, CoopSQL
from trytond.modules.coop_party import Actor

__all__ = ['Party', 'Insurer', 'Broker', 'Customer', ]
__metaclass__ = PoolMeta


class Party:
    'Party'

    __name__ = 'party.party'

    insurer_role = fields.One2Many('party.insurer', 'party', 'Insurer', size=1)
    broker_role = fields.One2Many('party.broker', 'party', 'Broker', size=1)
    customer_role = fields.One2Many('party.customer', 'party', 'Customer',
        size=1)

    @staticmethod
    def get_is_actor_var_name(var_name):
        return 'is_' + var_name.split('_role')[0]

    @staticmethod
    def get_actor_var_name(var_name):
        return var_name.split('is_')[1] + '_role'

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        #this loop will add for each One2Many role, a function field is_role
        for field_name in (role for role in dir(cls) if role.endswith('role')):
            field = getattr(cls, field_name)
            if not hasattr(field, 'model_name'):
                continue
            is_actor_var_name = Party.get_is_actor_var_name(field_name)
            field = fields.Function(fields.Boolean(field.string,
                    on_change=[field_name, is_actor_var_name]),
                'get_is_actor',
                setter='set_is_actor')
            setattr(cls, is_actor_var_name, field)

            def get_on_change(name):
                # Use a method to create a new context different of the loop
                def on_change(self):
                    return self.on_change_generic(name)
                return on_change
            on_change_method = 'on_change_%s' % is_actor_var_name
            if not getattr(cls, on_change_method, None):
                setattr(cls, on_change_method,
                    get_on_change(is_actor_var_name))

    def get_is_actor(self, name):
        field_name = Party.get_actor_var_name(name)
        if hasattr(self, field_name):
            field = getattr(self, field_name)
            return len(field) > 0
        return False

    def on_change_generic(self, is_role=''):
        res = {}
        if is_role == '':
            return res
        role = Party.get_actor_var_name(is_role)
        if role == '' or is_role == '':
            return res
        res[role] = {}
        if type(self[role]) == bool:
            return res
        if self[is_role] == True and len(self[role]) == 0:
            res[role]['add'] = [{}]
        elif self[is_role] == False and len(self[role]) > 0:
            res[role].setdefault('remove', [])
            res[role]['remove'].append(self[role][0].id)
        return res

    @classmethod
    def set_is_actor(cls, parties, name, value):
        pass


class Insurer(CoopSQL, Actor):
    'Insurer'

    __name__ = 'party.insurer'


class Broker(CoopSQL, Actor):
    'Broker'

    __name__ = 'party.broker'


class Customer(CoopSQL, Actor):
    'Customer'

    __name__ = 'party.customer'
