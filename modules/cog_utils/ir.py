import datetime
import polib
from sql.operators import Concat

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, PYSONEncoder
from trytond.transaction import Transaction
from trytond.model import fields as tryton_fields, ModelView
from trytond.wizard import Wizard, StateView, Button, StateAction

import fields
import utils
import model
from export import ExportImportMixin

__metaclass__ = PoolMeta

__all__ = [
    'Sequence',
    'SequenceStrict',
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
    'Icon',
    'Translation',
    'TranslationOverride',
    'TranslationOverrideStart'
]
SEPARATOR = ' / '


class Sequence(ExportImportMixin, model.TaggedMixin):
    __name__ = 'ir.sequence'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def _export_skips(cls):
        result = super(Sequence, cls)._export_skips()
        result.add('number_next_internal')
        return result

    def get_func_key(self, values):
        return '|'.join((self.code, self.name))

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        operands = clause[2].split('|')
        if len(operands) == 2:
            code, name = operands
            res = []
            if code != 'None':
                res.append(('code', clause[1], code))
            if name != 'None':
                res.append(('name', clause[1], name))
            return res
        else:
            return ['OR',
                [('code',) + tuple(clause[1:])],
                [('name',) + tuple(clause[1:])],
                ]

    @classmethod
    def is_master_object(cls):
        return True


class SequenceStrict(ExportImportMixin):
    __name__ = 'ir.sequence.strict'

    @classmethod
    def _export_skips(cls):
        result = super(SequenceStrict, cls)._export_skips()
        result.add('number_next_internal')
        return result

    @classmethod
    def is_master_object(cls):
        return True


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

    @staticmethod
    def date_as_string(date, lang=None):
        Lang = Pool().get('ir.lang')
        if not lang:
            lang = utils.get_user_language()
        return Lang.strftime(date, lang.code, lang.date)

    @staticmethod
    def datetime_as_string(date, lang=None):
        Lang = Pool().get('ir.lang')
        if lang is None:
            lang = utils.get_user_language()
        return Lang.strftime(date, lang.code, lang.date + ' %H:%M:%S')


class View(ExportImportMixin):
    __name__ = 'ir.ui.view'
    _func_key = 'name'


class UIMenu(ExportImportMixin):
    __name__ = 'ir.ui.menu'
    _func_key = 'xml_id'

    @classmethod
    def __register__(cls, module_name):
        super(UIMenu, cls).__register__(module_name)

        if backend.name() != 'postgresql':
            return

        with Transaction().new_cursor() as transaction:
            cursor = transaction.cursor
            cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent', ())
            cursor.commit()

    @classmethod
    def __setup__(cls):
        super(UIMenu, cls).__setup__()
        cls.complete_name.getter = 'get_full_name'
        cls.name = fields.UnaccentChar('Menu', required=True, translate=True)

    def get_rec_name(self, name):
        return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        # Bypass Tryton default search on parent
        return [('name',) + tuple(clause[1:])]

    def get_full_name(self, name):
        parent = self.parent
        name = self.name
        while parent:
            name = parent.name + SEPARATOR + name
            parent = parent.parent
        return name


class Rule(ExportImportMixin):
    __name__ = 'ir.rule'
    _func_key = 'domain'


class RuleGroup(ExportImportMixin):
    __name__ = 'ir.rule.group'

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
    _func_key = 'xml_id'

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
                    (table.action == action_table.id) &
                    (data_table.db_id == table.id))
            else:
                condition = condition | (
                    (table.action == action_table.id) &
                    (data_table.db_id == table.id))

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
                    (table.action == action_table.id) &
                    (data_table.db_id == table.id))
            else:
                condition = condition | (
                    (table.action == action_table.id) &
                    (data_table.db_id == table.id))

        cursor.execute(*query_table.select(action_table.id,
                where=(condition) &
                Operator(Concat(data_table.module,
                        Concat('.', data_table.fs_id)),
                    getattr(cls, name).sql_format(value))))
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    @classmethod
    def _export_skips(cls):
        res = super(Action, cls)._export_skips()
        res.add('keywords')
        return res

    @classmethod
    def _export_light(cls):
        result = super(Action, cls)._export_light()
        result.add('icon')
        return result


class ActionKeyword(ExportImportMixin):
    __name__ = 'ir.action.keyword'


class IrModel(ExportImportMixin):
    __name__ = 'ir.model'
    _func_key = 'model'

    @classmethod
    def _export_skips(cls):
        result = super(IrModel, cls)._export_skips()
        result.add('fields')
        return result


class IrModelField(ExportImportMixin):
    __name__ = 'ir.model.field'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    def get_func_key(self, values):
        return '|'.join((self.name, self.model.model))

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        operands = clause[2].split('|')
        if len(operands) == 2:
            name, model_model = operands
            res = []
            if name != 'None':
                res.append(('name', clause[1], name))
            if model_model != 'None':
                res.append(('model.model', clause[1], model_model))
            return res
        else:
            return ['OR',
                [('name',) + tuple(clause[1:])],
                [('model.model',) + tuple(clause[1:])],
                ]


class IrModelFieldAccess(ExportImportMixin):
    __name__ = 'ir.model.field.access'

    @classmethod
    def _export_light(cls):
        result = super(IrModelFieldAccess, cls)._export_light()
        result.add('field')
        return result


class ModelAccess(ExportImportMixin):
    __name__ = 'ir.model.access'

    @classmethod
    def _export_light(cls):
        result = super(ModelAccess, cls)._export_light()
        result.add('model')
        return result


class Property(ExportImportMixin):
    __name__ = 'ir.property'

    @classmethod
    def _export_light(cls):
        return set(['field'])

    @classmethod
    def _export_skips(cls):
        result = super(Property, cls)._export_skips()
        result.add('res')
        return result


class Lang(ExportImportMixin):
    __name__ = 'ir.lang'
    _func_key = 'code'

    @classmethod
    def get_from_code(cls, code):
        res = cls._lang_cache.get(code)
        if res is None:
            res = cls.search_read([('code', '=', code)], limit=1)[0]
            cls._lang_cache.set(code, res)
        else:
            res = cls(**res)
        return res


class Icon(ExportImportMixin):
    __name__ = 'ir.ui.icon'


class TranslationOverrideStart(ModelView):
    """Select translation override method"""

    __name__ = 'ir.translation.override.start'

    language = fields.Many2One('ir.lang', 'Language', required=True,
        domain=[
            ('translatable', '=', True),
            ('code', '!=', 'en_US'),
            ])
    export_kind = fields.Selection([
            ('product', 'Product'),
            ('client', 'Client')], 'Export kind', required=True)
    target_module = fields.Char('Target module', states={
            'invisible': Eval('export_kind') == 'product',
            'required': Eval('export_kind') == 'client',
            })


class TranslationOverride(Wizard):
    """Override translations Wizard"""

    __name__ = 'ir.translation.override'

    start = StateView('ir.translation.override.start',
        'cog_utils.override_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Edit', 'edit', 'tryton-ok', default=True),
            ])
    edit = StateAction('cog_utils.act_override_translation_form')

    def do_edit(self, action):
        domain = [('lang', '=', self.start.language.code)]
        context = {'target_module': ''}
        if self.start.export_kind == 'client':
            context['target_module'] = self.start.target_module
        else:
            domain.append(('module', 'in', utils.get_trytond_modules()))
        encoder = PYSONEncoder()
        action['pyson_context'] = encoder.encode(context)
        action['pyson_domain'] = encoder.encode(domain)
        return action, {}


class Translation:
    __name__ = 'ir.translation'

    @classmethod
    def write(cls, translations, values, *args):
        # TranslationOverride wizard set target_module to '' in product mode or
        # a module name in client mode. Assign None to target_module if no info
        # in context ie TranslationOverride wizard hasn't been called.
        target_module = Transaction().context.get('target_module', None)
        if target_module is None:
            return super(Translation, cls).write(translations, values, *args)

        new_args = []
        for translation in translations:
            new_args.append([translation])
            new_values = values
            if target_module:
                if target_module != translation.module:
                    new_values = values.copy()
                    new_values['overriding_module'] = target_module
            else:
                new_values = values.copy()
                overriding_module = translation.module + '_cog'
                new_values['overriding_module'] = overriding_module
            new_args.append(new_values)
        args = list(new_args + list(args))
        super(Translation, cls).write(*args)

    @classmethod
    def translation_export(cls, lang, module):
        # This import cannot be done at the top of the file, because it forces
        # the import of ir/sequence.py before batch configuration is loaded.
        # TODO : Fix this, for instance by moving batch_launcher.py outside of
        # cog_utils
        from trytond.ir.translation import TrytonPOFile
        # first pass: extract plain module translations
        res = super(Translation, cls).translation_export(lang, module)

        # second pass: append translations overwritten by this module
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Config = pool.get('ir.configuration')

        pofile = TrytonPOFile(wrapwidth=78)
        pofile.metadata = {
            'Content-Type': 'text/plain; charset=utf-8',
            }

        with Transaction().set_context(language=Config.get_language()):
            translations = cls.search([
                    ('lang', '=', lang),
                    ('overriding_module', '=', module)],
                    order=[('type', 'ASC'), ('name', 'ASC')])

        if not translations:
            return res

        models_data = ModelData.search(
            [('module', 'in', [module] + [t.module for t in translations])])
        db_id2fs_id = {}
        for model_data in models_data:
            db_id2fs_id.setdefault(model_data.model, {})
            db_id2fs_id[model_data.model][model_data.db_id] = \
                model_data.fs_id
            for extra_model in cls.extra_model_data(model_data):
                db_id2fs_id.setdefault(extra_model, {})
                db_id2fs_id[extra_model][model_data.db_id] = \
                    model_data.fs_id
        for translation in translations:
            flags = [] if not translation.fuzzy else ['fuzzy']
            trans_ctxt = '%(type)s:%(name)s:' % {
                'type': translation.type,
                'name': translation.name,
                }
            res_id = translation.res_id

            if res_id >= 0:
                model, _ = translation.name.split(',')
                if model in db_id2fs_id:
                    res_id = db_id2fs_id[model].get(res_id)
                else:
                    continue
                trans_ctxt += '%s' % (res_id or '')
            tokens = trans_ctxt.split(':')
            trans_ctxt = '%s:%s.%s' % (':'.join(tokens[:-1]),
                translation.module, tokens[-1])
            entry = polib.POEntry(msgid=(translation.src or ''),
                msgstr=(translation.value or ''), msgctxt=trans_ctxt,
                flags=flags)
            pofile.append(entry)

        noheader_pofile = '\n'.join(unicode(pofile).split('\n')[3:])
        msg = '\n# Custom translations below\n'
        return res + (msg + noheader_pofile).encode('utf-8')
