# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import datetime
import polib
from lxml import etree
from sql.operators import Concat

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext
from trytond.cache import Cache
from trytond.pyson import Eval, PYSONEncoder, Not, In, If
from trytond.transaction import Transaction
from trytond.model import fields as tryton_fields, ModelView, Model
from trytond.wizard import Wizard, StateView, Button, StateAction

import fields
import utils
import model
from historizable import Historizable
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
    'IrModule',
    'IrModel',
    'IrModelField',
    'IrModelFieldAccess',
    'ModelAccess',
    'Lang',
    'Icon',
    'Translation',
    'TranslationOverride',
    'TranslationOverrideStart'
]
SEPARATOR = ' / '

FORM_WIDGETS = ['icon', 'many2many_selection']
FORM_ATTRIBUTES = """
<grammar xmlns:a="http://relaxng.org/ns/compatibility/annotations/1.0"
    xmlns="http://relaxng.org/ns/structure/1.0">
    <define name="attlist.field" combine="interleave">
        <optional>
            <attribute name="context_tree"/>
        </optional>
    </define>
    <define name="attlist.field" combine="interleave">
        <optional>
            <attribute name="no_command">
                <choice>
                    <value>0</value>
                    <value>1</value>
                </choice>
            </attribute>
        </optional>
    </define>
    <define name="attlist.field" combine="interleave">
        <optional>
            <attribute name="relation"/>
        </optional>
    </define>
    <define name="attlist.field" combine="interleave">
        <optional>
            <attribute name="relation_field"/>
        </optional>
    </define>
    <define name="attlist.field" combine="interleave">
        <optional>
            <attribute name="group"/>
        </optional>
    </define>
    <define name="attlist.field" combine="interleave">
        <optional>
            <attribute name="states"/>
        </optional>
    </define>
    <define name="attlist.field" combine="interleave">
        <optional>
            <attribute name="expand_toolbar" a:defaultValue="0">
                <choice>
                    <value>0</value>
                    <value>1</value>
                </choice>
            </attribute>
        </optional>
    </define>
    <define name="attlist.button" combine="interleave">
        <optional>
            <attribute name="keywords"/>
        </optional>
    </define>
</grammar>
"""

TREE_ATTRIBUTES = """
<grammar xmlns:a="http://relaxng.org/ns/compatibility/annotations/1.0"
        xmlns="http://relaxng.org/ns/structure/1.0">
    <define name="attlist.tree" combine="interleave">
        <optional>
            <attribute name="always_expand">
                <choice>
                    <value>0</value>
                    <value>1</value>
                </choice>
            </attribute>
        </optional>
    </define>
    <define name="attlist.tree" combine="interleave">
        <optional>
            <attribute name="editable_open">
                <choice>
                    <value>0</value>
                    <value>1</value>
                </choice>
            </attribute>
        </optional>
    </define>
    <define name="attlist.tree" combine="interleave">
        <optional>
            <attribute name="colors"/>
        </optional>
    </define>
    <define name="attlist.button" combine="interleave">
        <optional>
            <attribute name="keywords"/>
        </optional>
    </define>
</grammar>
"""


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


class SequenceStrict(ExportImportMixin, model.TaggedMixin):
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

    _view_id_cache = Cache('ir_ui_view_id')

    @classmethod
    def get_view_from_xml_id(cls, xml_id):
        view = cls._view_id_cache.get(xml_id, None)
        if view is None:
            view, = cls.search([('xml_id', '=', xml_id)], limit=1)
            cls._view_id_cache.set(xml_id, view.id)
            return view.id
        return view

    @classmethod
    def get_rng(cls, type_):
        rng = super(View, cls).get_rng(type_)
        key = (cls.__name__, type_, 'override')
        cache_rng = cls._get_rng_cache.get(key, None)
        if cache_rng is None:
            if type_ == 'tree':
                attributes = etree.fromstring(TREE_ATTRIBUTES)
                for attr in attributes.iterchildren("*"):
                    rng.append(attr)
            elif type_ == 'form':
                widgets = rng.xpath(
                    '//ns:define/ns:optional/ns:attribute'
                    '[@name="widget"]/ns:choice',
                    namespaces={'ns': 'http://relaxng.org/ns/structure/1.0'})[0]
                for widget_name in FORM_WIDGETS:
                    subelem = etree.SubElement(widgets,
                        '{http://relaxng.org/ns/structure/1.0}value')
                    subelem.text = widget_name
                attributes = etree.fromstring(FORM_ATTRIBUTES)
                for attr in attributes.iterfind('*'):
                    rng.append(attr)
            cls._get_rng_cache.set(key, rng)
        return rng


class UIMenu(ExportImportMixin):
    __name__ = 'ir.ui.menu'
    _func_key = 'xml_id'

    @classmethod
    def __register__(cls, module_name):
        super(UIMenu, cls).__register__(module_name)

        if backend.name() != 'postgresql':
            return

        with Transaction().new_transaction() as transaction, \
                transaction.connection.cursor() as cursor:
            cursor = transaction.connection.cursor()
            cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent', ())
            transaction.commit()

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
        cursor = Transaction().connection.cursor()
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
        cursor = Transaction().connection.cursor()
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


class IrModule:
    __name__ = 'ir.module'

    _is_module_installed_cache = Cache('is_module_installed')

    @classmethod
    def is_module_installed(cls, module_name):
        module_installed = cls._is_module_installed_cache.get(module_name,
            default=-1)
        if module_installed != -1:
            return module_installed
        if cls._is_module_installed_cache.get('_check_initialized', False):
            # Cache was initialized, module does not exist
            return False
        cls._is_module_installed_cache.clear()
        cursor = Transaction().connection.cursor()
        module = cls.__table__()
        cursor.execute(*module.select(module.name, module.state))
        for name, state in cursor.fetchall():
            cls._is_module_installed_cache.set(name,
                state in ('activated', 'to upgrade', 'to activate'))
        cls._is_module_installed_cache.set('_check_initialized', True)
        return cls._is_module_installed_cache.get(module_name, False)

    @classmethod
    def view_attributes(cls):
        return [('/tree', 'colors',
                If(Eval('state').in_(['to upgrade', 'to install']),
                    'blue',
                    If(Eval('state') == 'uninstalled',
                        'grey',
                        'black')))]


class IrModel(ExportImportMixin):
    __name__ = 'ir.model'
    _func_key = 'model'

    _models_per_name = Cache('models_per_name')

    manual_history = fields.Boolean('Manual History')
    history_status = fields.Function(
        fields.Selection([
                ('never_activated', 'Never Activated'),
                ('partially_deactivated', 'Deactivated'),
                ('hardcoded', 'Hardcoded'),
                ('manual', 'Manually Set'),
                ('unavailable', ''),
                ('waiting_for_activation', 'Waiting for Activation'),
                ('waiting_for_removal', 'Waiting for Removal'),
                ], 'History Status'),
        'get_history_status')

    _models_get_cache = Cache('models_get')

    @classmethod
    def __setup__(cls):
        super(IrModel, cls).__setup__()
        cls._error_messages.update({
                'force_set_warning': 'This will forcefully set the history for'
                ' this model, a full database update will be required.',
                'force_unset_warning': 'This will deactivate the history for '
                'this model, the history table will be kept in the database '
                'until it is manually removed.',
                })
        cls._buttons.update({
                'force_set_history': {
                    'invisible':
                    Eval('history_status', 'unavailable') == 'unavailable',
                    'readonly': Not(In(Eval('history_status', ''),
                            ['never_activated', 'partially_deactivated',
                                'waiting_for_removal'])),
                    },
                'force_unset_history': {
                    'invisible':
                    Eval('history_status', 'unavailable') == 'unavailable',
                    'readonly': Not(In(Eval('history_status', ''),
                            ['manual', 'waiting_for_activation'])),
                    },
                })

    @classmethod
    def _export_skips(cls):
        result = super(IrModel, cls)._export_skips()
        result.add('fields')
        return result

    @classmethod
    def models_get(cls):
        models = cls._models_get_cache.get(None)
        if models:
            return models

        models = sorted([(x.model, x.name) for x in cls.search([])],
            key=lambda x: x[1]) + [('', '')]
        cls._models_get_cache.set(None, models)
        return models

    @classmethod
    def get_history_status(cls, models, name):
        logger = logging.getLogger(__name__)
        pool = Pool()
        result = {}
        TableHandler = backend.get('TableHandler')
        for cur_model in models:
            try:
                Target = pool.get(cur_model.model)
                if not issubclass(Target, Historizable) or not Target._table:
                    result[cur_model.id] = 'unavailable'
                    continue
                history_exists = TableHandler.table_exist(Target._table +
                    '__history')
                if Target._code_history:
                    result[cur_model.id] = 'hardcoded'
                elif (cur_model.manual_history and Target._history and
                        history_exists):
                    result[cur_model.id] = 'manual'
                elif cur_model.manual_history:
                    result[cur_model.id] = 'waiting_for_activation'
                elif Target._history:
                    result[cur_model.id] = 'waiting_for_removal'
                elif history_exists:
                    result[cur_model.id] = 'partially_deactivated'
                else:
                    result[cur_model.id] = 'never_activated'
            except KeyError:
                logger.warning('Cannot get model %s' % cur_model.model)
                result[cur_model.id] = 'unavailable'
        return result

    @classmethod
    @model.CoogView.button
    def force_set_history(cls, models):
        for cur_model in models:
            assert cur_model.history_status in ('never_activated',
                'partially_deactivated', 'waiting_for_removal')
        cls.raise_user_warning('force_set_warning', 'force_set_warning', ())
        cls.write(models, {'manual_history': True})
        cls.update_ir_status()

    @classmethod
    @model.CoogView.button
    def force_unset_history(cls, models):
        for cur_model in models:
            assert cur_model.history_status in ('manual',
                'waiting_for_activation')
        cls.raise_user_warning('force_unset_warning',
            'force_unset_warning', ())
        cls.write(models, {'manual_history': False})
        cls.update_ir_status()

    @classmethod
    def update_ir_status(cls):
        Module = Pool().get('ir.module')
        must_update = any((x.history_status in ('waiting_for_activation',
                    'waiting_for_removal'))
            for x in cls.search([]))
        ir = Module.search([('name', '=', 'ir')])[0]
        if (must_update and ir.state == 'to upgrade') or (
                not must_update and ir.state == 'installed'):
            return
        ir.state = 'to upgrade' if must_update else 'installed'
        ir.save()

    @classmethod
    def model_id_per_name(cls, model_name):
        model_id = cls._models_per_name.get(model_name, default=-1)
        if model_id != -1:
            return model_id
        cls._models_per_name.clear()
        models = cls.search([])
        for cur_model in models:
            cls._models_per_name.set(cur_model.model, cur_model.id)
        return cls._models_per_name.get(model_name)

    @classmethod
    def global_search(cls, text, limit, menu='ir.ui.menu'):
        with ServerContext().set_context(global_search_limit=limit):
            return super(IrModel, cls).global_search(text, limit, menu)


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


class Lang(ExportImportMixin):
    __name__ = 'ir.lang'
    _func_key = 'code'

    @classmethod
    def get_from_code(cls, code):
        res = cls._lang_cache.get(code)
        if res is None:
            res = cls.search_read([('code', '=', code)], limit=1)[0]
            cls._lang_cache.set(code, res)
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
            ('code', '!=', 'en'),
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
        'coog_core.override_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Edit', 'edit', 'tryton-ok', default=True),
            ])
    edit = StateAction('coog_core.act_override_translation_form')

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
    def delete(cls, translations):
        if not translations:
            return
        Model._fields_get_cache.clear()
        return super(Translation, cls).delete(translations)

    @classmethod
    def write(cls, translations, values, *args):
        # TranslationOverride wizard set target_module to '' in product mode or
        # a module name in client mode. Assign None to target_module if no info
        # in context ie TranslationOverride wizard hasn't been called.
        Model._fields_get_cache.clear()
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
    def create(cls, vlist):
        Model._fields_get_cache.clear()
        return super(Translation, cls).create(vlist)

    @classmethod
    def translation_export(cls, lang, module):
        # This import cannot be done at the top of the file, because it forces
        # the import of ir/sequence.py before batch configuration is loaded.
        # TODO : Fix this, for instance by moving batch_launcher.py outside of
        # coog_core
        from trytond.ir.translation import TrytonPOFile
        # first pass: extract plain module translations
        res = super(Translation, cls).translation_export(lang, module) or ''

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
