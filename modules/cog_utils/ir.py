import datetime
from sql.operators import Concat

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import fields as tryton_fields
from trytond.config import CONFIG

import fields
from export import ExportImportMixin


__metaclass__ = PoolMeta

__all__ = [
    'Sequence',
    'DateClass',
    'View',
    'UIMenu',
    'Rule',
    'RuleGroup',
    'Action',
    'ActionKeyword',
    'IrModel',
    'IrModelField',
    'IrModelFieldAccess',
    'ModelAccess',
    'Property',
    'Lang',
    ]


class Sequence(ExportImportMixin):
    __name__ = 'ir.sequence'

    @classmethod
    def _export_keys(cls):
        return set(['code', 'name'])

    @classmethod
    def _export_skips(cls):
        result = super(Sequence, cls)._export_skips()
        result.add('number_next_internal')
        return result


class DateClass:
    '''Overriden ir.date class for more accurate date management'''

    __name__ = 'ir.date'

    @classmethod
    def today(cls, timezone=None):
        ctx_date = Transaction().context.get('client_defined_date')
        if ctx_date:
            return ctx_date
        else:
            return super(DateClass, cls).today(timezone=timezone)

    @staticmethod
    def system_today():
        return datetime.date.today()


class View(ExportImportMixin):
    __name__ = 'ir.ui.view'

    @classmethod
    def _export_keys(cls):
        return set(['module', 'type', 'name'])


class UIMenu(ExportImportMixin):
    __name__ = 'ir.ui.menu'

    #XXX overide existing field and must create extension unaccent
    name = fields.UnaccentChar('Menu', required=True, translate=True)

    @classmethod
    def __register__(cls, module_name):
        super(UIMenu, cls).__register__(module_name)

        if CONFIG['db_type'] != 'postgresql':
            return

        with Transaction().new_cursor() as transaction:
            cursor = transaction.cursor
            cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent', ())
            cursor.commit()

    def get_rec_name(self, name):
        return self.name

    @classmethod
    def _export_keys(cls):
        return set(['xml_id'])


class Rule(ExportImportMixin):
    __name__ = 'ir.rule'

    @classmethod
    def _export_keys(cls):
        return set(['domain'])


class RuleGroup(ExportImportMixin):
    __name__ = 'ir.rule.group'

    @classmethod
    def _export_keys(cls):
        return set(['model.model', 'global_p', 'default_p', 'perm_read',
                'perm_write', 'perm_create', 'perm_delete'])

    @classmethod
    def _export_skips(cls):
        result = super(RuleGroup, cls)._export_skips()
        result.add('groups')
        result.add('users')
        return result

    @classmethod
    def _export_light(cls):
        result = super(RuleGroup, cls)._export_light()
        result.add('model')
        return result


class Action(ExportImportMixin):
    __name__ = 'ir.action'

    xml_id = fields.Function(
        fields.Char('Xml Id', states={'invisible': True}),
        'get_xml_id', searcher='search_xml_id')

    @classmethod
    def get_xml_id(cls, actions, name):
        cursor = Transaction().cursor
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Action = pool.get('ir.action')
        # Possible actions
        action_model_names = ['ir.action.wizard', 'ir.action.act_window',
            'ir.action.report']
        ActionModels = map(pool.get, action_model_names)
        data_table = ModelData.__table__()
        action_table = Action.__table__()
        action_tables = map(lambda x: x.__table__(), ActionModels)

        query_table = action_table.join(data_table, type_='LEFT', condition=(
                data_table.model == action_table.type))
        for table in action_tables:
            query_table = query_table.join(table, type_='LEFT', condition=(
                    table.action == action_table.id))

        condition = None
        for table in action_tables:
            if condition is None:
                condition = (
                    (table.action == action_table.id)
                    & (data_table.db_id == table.id))
            else:
                condition = condition | (
                    (table.action == action_table.id)
                    & (data_table.db_id == table.id))

        cursor.execute(*query_table.select(action_table.id,
                Concat(data_table.module, Concat('.', data_table.fs_id)),
                where=condition))
        # TODO : What do we do if some ids do not have a match ?
        return dict(cursor.fetchall())

    @classmethod
    def search_xml_id(cls, name, clause):
        cursor = Transaction().cursor
        _, operator, value = clause
        Operator = tryton_fields.SQL_OPERATORS[operator]
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Action = pool.get('ir.action')
        # Possible actions
        action_model_names = ['ir.action.wizard', 'ir.action.act_window',
            'ir.action.report']
        ActionModels = map(pool.get, action_model_names)
        data_table = ModelData.__table__()
        action_table = Action.__table__()
        action_tables = map(lambda x: x.__table__(), ActionModels)

        query_table = action_table.join(data_table, type_='LEFT', condition=(
                data_table.model == action_table.type))
        for table in action_tables:
            query_table = query_table.join(table, type_='LEFT', condition=(
                    table.action == action_table.id))

        condition = None
        for table in action_tables:
            if condition is None:
                condition = (
                    (table.action == action_table.id)
                    & (data_table.db_id == table.id))
            else:
                condition = condition | (
                    (table.action == action_table.id)
                    & (data_table.db_id == table.id))

        cursor.execute(*query_table.select(action_table.id,
                where=(condition)
                    & Operator(Concat(data_table.module,
                            Concat('.', data_table.fs_id)),
                        getattr(cls, name).sql_format(value))))
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    @classmethod
    def _export_keys(cls):
        return set(['xml_id'])


class ActionKeyword(ExportImportMixin):
    __name__ = 'ir.action.keyword'

    @classmethod
    def _export_keys(cls):
        return set(['keyword'])


class IrModel(ExportImportMixin):
    __name__ = 'ir.model'

    @classmethod
    def _export_keys(cls):
        return set(['model'])

    @classmethod
    def _export_skips(cls):
        result = super(IrModel, cls)._export_skips()
        result.add('fields')
        return result


class IrModelField(ExportImportMixin):
    __name__ = 'ir.model.field'

    @classmethod
    def _export_keys(cls):
        return set(['name', 'model.model'])


class IrModelFieldAccess(ExportImportMixin):
    __name__ = 'ir.model.field.access'

    @classmethod
    def _export_keys(cls):
        return set(['field.name', 'field.model.model', 'group.name',
                'perm_read', 'perm_write', 'perm_create', 'perm_delete'])

    @classmethod
    def _export_light(cls):
        result = super(IrModelFieldAccess, cls)._export_light()
        result.add('field')
        return result


class ModelAccess(ExportImportMixin):
    __name__ = 'ir.model.access'

    @classmethod
    def _export_keys(cls):
        return set(['model.model', 'group.name', 'perm_read', 'perm_write',
                'perm_create', 'perm_delete'])

    @classmethod
    def _export_light(cls):
        result = super(ModelAccess, cls)._export_light()
        result.add('model')
        return result


class Property(ExportImportMixin):
    __name__ = 'ir.property'

    @classmethod
    def _export_keys(cls):
        # Properties are only fit for export / import if they are "global",
        # meaning they are not set for a given instance. See
        # account.configuration default accounts.
        return set(['field.name', 'field.model.model', 'company.party.name'])

    @classmethod
    def _export_light(cls):
        return set(['field'])


class Lang(ExportImportMixin):
    __name__ = 'ir.lang'

    @classmethod
    def _export_keys(cls):
        return set(['code'])
