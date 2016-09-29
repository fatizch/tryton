# This file is part of Coog.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields


__all__ = [
    'Model',
    'ModelField',
    'UIMenuAccess',
    ]


class Model:
    __metaclass__ = PoolMeta
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
        assert active_model == 'res.user'
        ModelAccess = Pool().get('ir.model.access')
        with Transaction().set_user(Transaction().context.get('active_id')):
            rights = ModelAccess.get_access([i.model for i in instances])
        return {i.id: rights[i.model][name[5:]] for i in instances}

    @classmethod
    def get_rule_perms(cls, instances, name):
        active_model = Transaction().context.get('active_model')
        assert active_model == 'res.user'
        Rule = Pool().get('ir.rule')
        with Transaction().set_user(Transaction().context.get('active_id')):
            return {i.id: bool(Rule.domain_get(i.model, name[10:]))
                for i in instances}


class ModelField:
    __metaclass__ = PoolMeta
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
        'on_change_with_model_desc')

    @fields.depends('model')
    def on_change_with_model_desc(self, name=None):
        return self.model.name

    @classmethod
    def get_perms(cls, instances, name):
        active_model = Transaction().context.get('active_model')
        assert active_model == 'res.user'
        ModelFieldAccess = Pool().get('ir.model.field.access')
        with Transaction().set_user(Transaction().context.get('active_id')):
            model_rights = ModelFieldAccess.get_access(
                [i.model.model for i in instances])
        perms = {}
        for i in instances:
            if (i.model.model in model_rights.keys() and
                    i.name in model_rights[i.model.model].keys()):
                perm = name[11:]
                if perm != 'default':
                    perms[i.id] = model_rights[i.model.model][i.name][perm]
                else:
                    perms[i.id] = False
            else:
                perms[i.id] = True
        return perms


class UIMenuAccess:
    __metaclass__ = PoolMeta
    __name__ = 'ir.ui.menu'

    perm_menu = fields.Function(fields.Boolean('Access To Menu'), 'get_perms')

    @classmethod
    def get_perms(cls, instances, name):
        active_model = Transaction().context.get('active_model')
        assert active_model == 'res.user'
        Menu = Pool().get('ir.ui.menu')
        with Transaction().set_user(Transaction().context.get('active_id')):
            return {i.id: i in Menu.search([]) for i in instances}
