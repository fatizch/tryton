# This file is part of Coog.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.aggregate import Max
from sql.conditionals import Case

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


__all__ = [
    'Model',
    'ModelField',
    'UIMenuAccess',
    ]


class Model(metaclass=PoolMeta):
    __name__ = 'ir.model'

    perm_read = fields.Function(fields.Boolean('Read Access'), 'get_perms')
    perm_write = fields.Function(fields.Boolean('Write Access'), 'get_perms')
    perm_create = fields.Function(fields.Boolean('Create Access'), 'get_perms')
    perm_delete = fields.Function(fields.Boolean('Delete Access'), 'get_perms')

    perm_rule_read = fields.Function(fields.Boolean('Rule Read Access'),
        'get_rule_perms')
    perm_rule_write = fields.Function(fields.Boolean('Rule Write Access'),
        'get_rule_perms')
    perm_rule_create = fields.Function(fields.Boolean('Rule Create Access'),
        'get_rule_perms')
    perm_rule_delete = fields.Function(fields.Boolean('Rule Delete Access'),
        'get_rule_perms')

    @classmethod
    def get_perms(cls, instances, name):
        active_model = Transaction().context.get('active_model')
        if active_model != 'res.user':
            return {x.id: None for x in instances}
        ModelAccess = Pool().get('ir.model.access')
        with Transaction().set_user(Transaction().context.get('active_id')):
            rights = ModelAccess.get_access([i.model for i in instances])
        return {i.id: rights[i.model][name[5:]] for i in instances}

    @classmethod
    def get_rule_perms(cls, instances, name):
        active_model = Transaction().context.get('active_model')
        if active_model != 'res.user':
            return {x.id: None for x in instances}
        Rule = Pool().get('ir.rule')
        with Transaction().set_user(Transaction().context.get('active_id')):
            return {i.id: bool(Rule.domain_get(i.model, name[10:]))
                for i in instances}


class ModelField(metaclass=PoolMeta):
    __name__ = 'ir.model.field'

    perm_field_read = fields.Function(fields.Boolean('Read Access'),
        'get_perms')
    perm_field_write = fields.Function(fields.Boolean('Write Access'),
        'get_perms')
    perm_field_create = fields.Function(fields.Boolean('Create Access'),
        'get_perms')
    perm_field_delete = fields.Function(fields.Boolean('Delete Access'),
        'get_perms')
    perm_field_default = fields.Function(fields.Boolean('Default Rights'),
        'get_perms')
    model_name = fields.Function(fields.Char('Model Description'),
        'on_change_with_model_name')

    @fields.depends('model')
    def on_change_with_model_name(self, name=None):
        return self.model.name if self.model else ''

    @classmethod
    def get_perms(cls, instances, name):
        active_model = Transaction().context.get('active_model')
        if active_model != 'res.user':
            return {x.id: None for x in instances}
        ModelFieldAccess = Pool().get('ir.model.field.access')
        with Transaction().set_user(Transaction().context.get('active_id')):
            model_rights = ModelFieldAccess.get_access(
                [i.model.model for i in instances])
        perms = {}
        for i in instances:
            if (i.model.model in list(model_rights.keys()) and
                    i.name in list(model_rights[i.model.model].keys())):
                perm = name[11:]
                if perm != 'default':
                    perms[i.id] = model_rights[i.model.model][i.name][perm]
                else:
                    perms[i.id] = False
            else:
                perms[i.id] = True
        return perms

    @classmethod
    def get_field_display_access_for_model(cls, field_name, model_name):
        res = False
        user = Transaction().user
        if user == 0:
            return True

        pool = Pool()
        ir_model = pool.get('ir.model').__table__()
        model_field = cls.__table__()
        field_access = pool.get('ir.model.field.access').__table__()
        user_group = pool.get('res.user-res.group').__table__()

        cursor = Transaction().connection.cursor()

        cursor.execute(*field_access.join(model_field,
                condition=field_access.field == model_field.id
                ).join(ir_model,
                condition=model_field.model == ir_model.id
                ).join(user_group, 'LEFT',
                condition=user_group.group == field_access.group
                ).select(
                ir_model.model,
                model_field.name,
                Max(Case((field_access.perm_read == True, 1), else_=0)),
                where=((ir_model.model == model_name)
                    & (model_field.name == field_name)
                    & ((user_group.user == user) | (field_access.group == Null)
                        )), group_by=[ir_model.model, model_field.name]))
        for model, field, perm_read in cursor.fetchall():
            if perm_read == 1:
                res |= True
        return res


class UIMenuAccess(metaclass=PoolMeta):
    __name__ = 'ir.ui.menu'

    perm_menu = fields.Function(fields.Boolean('Access To Menu'), 'get_perms')

    @classmethod
    def get_perms(cls, instances, name):
        active_model = Transaction().context.get('active_model')
        if active_model != 'res.user':
            return {x.id: None for x in instances}
        Menu = Pool().get('ir.ui.menu')
        with Transaction().set_user(Transaction().context.get('active_id')):
            return {i.id: i in Menu.search([]) for i in instances}
