import copy
from datetime import datetime
from decimal import Decimal
from functools import partial
try:
    import simplejson as json
except ImportError:
    import json

from lxml import etree
from sql import Column, Literal
from sql.functions import Function, CurrentTimestamp

from trytond.protocols.jsonrpc import JSONEncoder, JSONDecoder
from trytond.config import config
from trytond import backend
from trytond.cache import Cache
from trytond.pool import Pool
from trytond.model import Unique
from trytond.pyson import Eval, Bool, PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.tools import memoize

from trytond.modules.cog_utils.model import CoopSQL as ModelSQL
from trytond.modules.cog_utils.model import CoopView as ModelView
from trytond.modules.cog_utils import fields
from trytond.modules.cog_utils import utils, coop_string, model
from trytond.modules.cog_utils.cache import CoogCache, get_cache_holder

__all__ = [
    'TableCell',
    'TableDefinition',
    'TableDefinitionDimension',
    'TableDefinitionDimensionOpenAskType',
    'TableDefinitionDimensionOpen',
    'TableOpen2DAskDimensions',
    'TableOpen2D',
    'Table2D',
    ]

TYPE = [
    ('', ''),
    ('numeric', 'Numeric'),
    ('char', 'Char'),
    ('integer', 'Integer'),
    ('boolean', 'Boolean'),
    ('date', 'Date'),
    ]

KIND = [
    (None, ''),
    ('value', 'Value'),
    ('date', 'Date'),
    ('range', 'Range'),
    ('range-date', 'Range-Date'),
    ]

ORDER = [
    ('alpha', 'Alphabetical'),
    ('sequence', 'Sequence'),
    ]

DIMENSION_MAX = int(config.get('options', 'table_dimension', default=4))


class TableDefinition(ModelSQL, ModelView, model.TaggedMixin):
    "Table Definition"

    __name__ = 'table'
    _func_key = 'code'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    type_ = fields.Selection(TYPE, 'Type', required=True, sort=False)
    type_string = type_.translated('type_')
    kind = fields.Function(fields.Char('Kind'), 'get_kind')
    cells = fields.One2Many('table.cell', 'definition', 'Cells',
        delete_missing=True, target_not_indexed=True)
    number_of_digits = fields.Integer('Number of Digits', states={
            'invisible': Eval('type_', '') != 'numeric'})
    number_of_dimensions = fields.Function(
        fields.Integer('Number of dimension'),
        'get_number_of_dimensions')

    @classmethod
    def __setup__(cls):
        super(TableDefinition, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('code_unique', Unique(t, t.code),
                'The code of "Table Definition" must be unique'),
        ]
        cls._order.insert(0, ('name', 'ASC'))
        cls._error_messages.update({
                'existing_clone': ('A clone record already exists : %s(%s)'),
                'multiple_tables': 'Multiple tables found'})

    @classmethod
    def __register__(cls, module_name):
        super(TableDefinition, cls).__register__(module_name)

        if backend.name() != 'postgresql':
            return

        with Transaction().new_transaction() as transaction, \
                transaction.connection.cursor() as cursor:
            try:
                cursor.execute('CREATE EXTENSION IF NOT EXISTS tablefunc', ())
                transaction.commit()
            except:
                import logging
                logger = logging.getLogger('database')
                logger.warning('Unable to activate tablefunc extension, '
                    '2D displaying of tables will not be available')
                transaction.rollback()

    @classmethod
    def copy(cls, records, default=None):
        result = []

        for record in records:
            output = []
            existings = cls.search(['OR',
                    [('code', '=', '%s_clone' % record.code)],
                    [('name', '=', '%s Clone' % record.name)]])
            for existing in existings:
                cls.raise_user_error('existing_clone',
                    (existing.name, existing.code))
            record.export_json(output=output)
            values = json.dumps(output[0], cls=JSONEncoder)
            values = values.replace('"_func_key": "%s"' % record.code,
                '"_func_key": "%s_clone"' % record.code)
            values = values.replace('"code": "%s"' % record.code,
                '"code": "%s_clone"' % record.code)
            values = values.replace(u'"name": "%s"' % record.name,
                u'"name": "%s Clone"' % record.name)
            tmp = record.import_json(json.loads(values,
                    object_hook=JSONDecoder()))
            result.append(tmp)
        return result

    @classmethod
    def delete(cls, tables):
        Cell = Pool().get('table.cell')
        Cell.delete(sum([list(x.cells) for x in tables], []))
        super(TableDefinition, cls).delete(tables)

    @classmethod
    def is_master_object(cls):
        return True

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        if skip_fields:
            skip_fields.add('cells')
        else:
            skip_fields = set(['cells'])
        result = super(TableDefinition, self).export_json(skip_fields,
            already_exported, output, main_object, configuration)
        pool = Pool()
        Cell = pool.get('table.cell')
        DimensionValue = pool.get('table.dimension.value')

        cursor = Transaction().connection.cursor()

        cell = Cell.__table__()
        dimension_tables = [DimensionValue.__table__()
            for i in range(0, self.number_of_dimensions)]

        query_table = None
        for idx, table in enumerate(dimension_tables, 1):
            query_table = (query_table if query_table else cell).join(table,
                condition=(getattr(cell, 'dimension%s' % idx) == table.id))

        if query_table is None:
            return result

        columns = [x.name for x in dimension_tables] + [cell.value]
        cursor.execute(*query_table.select(*columns,
                where=(cell.definition == self.id)))
        result['cells'] = cursor.fetchall()
        return result

    @classmethod
    def _export_light(cls):
        return super(TableDefinition, cls)._export_light() | {'tags'}

    @classmethod
    def do_import(cls, value):
        if value['imported']:
            return value['record']
        values = value['data']
        if 'cells' not in values:
            return super(TableDefinition, cls).do_import(value)
        pool = Pool()
        Cell = pool.get('table.cell')
        cells = values.pop('cells')
        tables = cls.search_for_export_import(values)
        if len(tables) > 1:
            cls.raise_user_error('multiple_tables')
        if tables:
            Cell.delete(Cell.search([('definition', '=', tables[0].id)]))
        table = super(TableDefinition, cls).do_import(value)
        dimension_matcher = {}
        for i in range(1, DIMENSION_MAX + 1):
            dimension_values = getattr(table, 'dimension%s' % i)
            dimension_matcher[i] = dict([
                    (x.name, x.id) for x in dimension_values])
        to_create = []
        for elem in cells:
            to_create.append(dict([
                        ('dimension%s' % i, dimension_matcher[i][x])
                        for i, x in enumerate(elem[:-1], 1)] +
                    [('value', elem[-1])] +
                    [('definition', table.id)]))
        Cell.create(to_create)
        value['record'] = table
        return table

    @classmethod
    def _default_dimension_order(cls):
        return 'alpha'

    @staticmethod
    def default_type_():
        return ''

    def get_number_of_dimensions(self, name):
        for i in range(1, DIMENSION_MAX + 1):
            if not getattr(self, 'dimension%s' % i):
                return i - 1
        return i

    @classmethod
    def _view_look_dom_arch(cls, tree, type, field_children=None):
        if tree.tag == 'form':
            result = tree.xpath("//field[@name='dimensions']")
            if result:
                dimensions, = result
                for i in range(1, DIMENSION_MAX + 1):
                    group = etree.Element('group')
                    group.set('id', 'dim%s' % i)
                    group.set('colspan', '2')
                    group.set('col', '2')
                    group.set('yfill', '1')
                    group.set('yexpand', '1')
                    label_kind = etree.Element('label')
                    label_kind.set('name', 'dimension_kind%s' % i)
                    group.append(label_kind)
                    field_kind = etree.Element('field')
                    field_kind.set('name', 'dimension_kind%s' % i)
                    group.append(field_kind)
                    label_name = etree.Element('label')
                    label_name.set('name', 'dimension_name%s' % i)
                    group.append(label_name)
                    field_name = etree.Element('field')
                    field_name.set('name', 'dimension_name%s' % i)
                    group.append(field_name)
                    dimensions.addprevious(group)
                dimensions.getparent().remove(dimensions)
        return super(TableDefinition, cls)._view_look_dom_arch(tree,
            type, field_children=field_children)

    @classmethod
    def write(cls, *args):
        pool = Pool()
        TableDefinitionDimension = pool.get('table.dimension.value')
        super(TableDefinition, cls).write(*args)

        actions = iter(args)
        for records, values in zip(actions, actions):
            if any(k for k in values if k.startswith('dimension_order')):
                dimensions = [d for r in records
                    for i in xrange(DIMENSION_MAX)
                    for d in getattr(r, 'dimension%s' % (i + 1)) or []]
                TableDefinitionDimension.clean_sequence(dimensions)

    @classmethod
    def get(cls, name):
        """
        Return the definition instance for the name.
        """
        return cls.search([
            ('name', '=', name),
        ])[0]

    def get_kind(self, name):
        nb_dim = 0
        has_date_range = False
        for i in range(1, DIMENSION_MAX + 1):
            if getattr(self, 'dimension_kind%s' % i):
                nb_dim += 1
                if getattr(self, 'dimension_kind%s' % i) == 'range-date':
                    has_date_range = True
        if nb_dim == 1 and has_date_range:
            return 'Index'
        elif nb_dim == 2:
            return 'Table'
        else:
            return 'Table %sD' % nb_dim

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    @classmethod
    def default_number_of_digits(cls):
        return 2

    def get_index_value(self, at_date=None):
        Cell = Pool().get('table.cell')
        if not at_date:
            at_date = utils.today()
        cell = Cell.get_cell(self, at_date)
        return cell.get_value_with_type() if cell else None

    def get_rec_name(self, name):
        res = super(TableDefinition, self).get_rec_name(name)
        if self.kind == 'Index':
            cell = self.get_index_value()
            if cell:
                res = '%s (%s)' % (res, cell)
        return res

for i in range(1, DIMENSION_MAX + 1):
    setattr(TableDefinition, 'dimension_order%s' % i,
        fields.Selection(ORDER, 'Dimension Order %s' % i,
            states={
                'invisible': ~Eval('dimension_kind%s' % i),
                'required': Bool(Eval('dimension_kind%s' % i)),
                },
            depends=['dimension_kind%s' % i]))
    setattr(TableDefinition, 'dimension_kind%s' % i,
        fields.Selection(KIND, 'Dimension Kind %s' % i,
            states={
                'readonly': Bool(Eval('dimension%s' % i)),
                }))
    setattr(TableDefinition, 'dimension_name%s' % i,
        fields.Char('Name',
            states={
                'invisible': ~Eval('dimension_kind%s' % i),
                }))

    setattr(TableDefinition, 'default_dimension_order%s' % i,
        TableDefinition._default_dimension_order)

    setattr(TableDefinition, 'dimension%s' % i,
        fields.One2ManyDomain('table.dimension.value', 'definition',
            'Dimension %s' % i, domain=[('type', '=', 'dimension%s' % i)],
            delete_missing=True, target_not_indexed=True))


def dimension_state(kind):
    return {
        'invisible': Eval('dimension_kind') != kind,
        }

DIMENSION_DEPENDS = ['dimension_kind']


class TableDefinitionDimension(ModelSQL, ModelView):
    "Table Definition Dimension"

    __name__ = 'table.dimension.value'

    name = fields.Char('Name', select=True, translate=True)
    sequence = fields.Integer('Sequence',
        states={
            'invisible': Eval('dimension_order') == 'alpha',
            }, depends=['dimension_order'])
    definition = fields.Many2One('table', 'Definition', required=True,
        ondelete='CASCADE')
    type = fields.Selection(
        [('dimension%s' % i, 'Dimension %s' % i)
            for i in range(1, DIMENSION_MAX + 1)],
        'Type', required=True)
    dimension_kind = fields.Function(
        fields.Selection(KIND, 'Dimension Kind'),
        'on_change_with_dimension_kind')
    dimension_order = fields.Function(
        fields.Selection(ORDER, 'Dimension Order'),
        'on_change_with_dimension_order')
    value = fields.Char(
        'Value', states=dimension_state('value'),
        depends=DIMENSION_DEPENDS)
    date = fields.Date(
        'Date', states=dimension_state('date'),
        depends=DIMENSION_DEPENDS)
    start = fields.Float(
        'Start', states=dimension_state('range'),
        depends=DIMENSION_DEPENDS, help='Value Included')
    end = fields.Float(
        'End', states=dimension_state('range'),
        depends=DIMENSION_DEPENDS, help='Value Excluded')
    start_date = fields.Date(
        'Start Date',
        states=dimension_state('range-date'), depends=DIMENSION_DEPENDS,
        help='Date Included')
    end_date = fields.Date(
        'End Date',
        states=dimension_state('range-date'), depends=DIMENSION_DEPENDS,
        help='Date Excluded')
    _get_dimension_cache = Cache('get_dimension_id')

    @classmethod
    def __setup__(cls):
        super(TableDefinitionDimension, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')

        super(TableDefinitionDimension, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        table.index_action(['definition', 'type'], 'add')

    @fields.depends('definition', 'type')
    def on_change_with_dimension_kind(self, name=None):
        if getattr(self, 'definition', None) and getattr(self, 'type', None):
            idx = int(self.type[len('dimension'):])
            return getattr(self.definition, 'dimension_kind%s' % idx)

    @fields.depends('definition', 'type')
    def on_change_with_dimension_order(self, name=None):
        if getattr(self, 'definition', None) and getattr(self, 'type', None):
            idx = int(self.type[len('dimension'):])
            return getattr(self.definition, 'dimension_order%s' % idx)

    @classmethod
    def clean_sequence(cls, records):
        to_clean = []
        for record in records:
            order_name = 'dimension_order' + record.type[len('dimension'):]
            order = getattr(record.definition, order_name)
            if order == 'alpha' and record.sequence is not None:
                to_clean.append(record)
        if to_clean:
            cls.write(to_clean, {'sequence': None})

    @classmethod
    def create(cls, vlist):
        cls._get_dimension_cache.clear()
        records = super(TableDefinitionDimension, cls).create(vlist)
        cls.clean_sequence(records)
        cls.set_name(records)
        return records

    @classmethod
    def write(cls, *args):
        cls._get_dimension_cache.clear()
        super(TableDefinitionDimension, cls).write(*args)
        records = sum(args[0::2], [])
        cls.clean_sequence(records)
        cls.set_name(records)

    @classmethod
    def _view_look_dom_arch(cls, tree, type, field_children=None):
        pool = Pool()
        TableDefinition = pool.get('table')
        context = Transaction().context
        if type == 'tree' and 'table' in context and 'type' in context:
            result = tree.xpath("//field[@name='rec_name']")
            table = TableDefinition(context['table'])
            if result:
                rec_name, = result
                kind = getattr(table, 'dimension_kind%s' %
                    context['type'][len('dimension'):])
                if kind in ('value', 'date'):
                    value = copy.copy(rec_name)
                    value.set('name', kind)
                    rec_name.addnext(value)
                elif kind in ('range', 'range-date'):
                    if kind == 'range-date':
                        suffix = '_date'
                    else:
                        suffix = ''
                    start = copy.copy(rec_name)
                    start.set('name', 'start' + suffix)
                    rec_name.addnext(start)
                    end = copy.copy(start)
                    end.set('name', 'end' + suffix)
                    start.addnext(end)
                if kind is not None:
                    rec_name.getparent().remove(rec_name)
        return super(TableDefinitionDimension, cls)._view_look_dom_arch(tree,
            type, field_children=field_children)

    @classmethod
    def set_name(cls, dimensions):
        pool = Pool()
        Lang = pool.get('ir.lang')

        lang, = Lang.search([('code', '=',
            config.get('database', 'language'))])
        for dimension in dimensions:
            kind = 'dimension_kind%s' % dimension.type[9:]
            name = ''
            if getattr(dimension.definition, kind) == 'value':
                name = dimension.value
            elif getattr(dimension.definition, kind) == 'date':
                if dimension.date:
                    name = Lang.strftime(
                        dimension.date, lang.code, lang.date)
                else:
                    name = str(dimension.id)
            elif getattr(dimension.definition, kind) == 'range':
                name = '%s - %s' % (
                    dimension.start if dimension.start else '',
                    dimension.end if dimension.end else '')
            elif getattr(dimension.definition, kind) == 'range-date':
                if dimension.start_date:
                    name = '%s -' % (
                        Lang.strftime(
                            dimension.start_date, lang.code, lang.date))
                    if dimension.end_date:
                        name += ' %s' % (
                            Lang.strftime(
                                dimension.end_date, lang.code, lang.date))
                elif dimension.end_date:
                    name = '- %s' % (
                        Lang.strftime(
                            dimension.end_date, lang.code, lang.date))
            if (getattr(dimension.definition, kind)
                    and getattr(
                        dimension.definition, kind).startswith('range')):
                name = '[%s[' % name
            if name != dimension.name:
                dimension.name = name
                dimension.save()

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator == '=' and isinstance(value, (int, long)):
            return [('id', '=', value)]
        if operator == 'ilike':
            return [('name', 'ilike', value.strip('%'))]
        return [('name',) + tuple(clause[1:])]

    @classmethod
    def get_dimension_id(cls, definition, dimension_idx, value):
        key = (definition.id, dimension_idx, value)
        dimension_id = cls._get_dimension_cache.get(key, default=-1)
        if dimension_id != -1:
            return dimension_id

        kind = getattr(definition, 'dimension_kind%d' % (dimension_idx + 1))
        dimension = None
        clause = [
            ('definition', '=', definition.id),
            ('type', '=', 'dimension%d' % (dimension_idx + 1)),
        ]
        if kind == 'value':
            clause.append(('value', '=', str(value)))
        elif kind == 'date':
            clause.append(('date', '=', value))
        elif kind == 'range':
            clause.extend([
                ['OR',
                    ('start', '=', None),
                    ('start', '<=', float(value)),
                ],
                ['OR',
                    ('end', '=', None),
                    ('end', '>', float(value)),
                ],
            ])
        elif kind == 'range-date':
            clause.extend([
                    ['OR',
                        ('start_date', '=', None),
                        ('start_date', '<=', value),
                        ],
                    ['OR',
                        ('end_date', '=', None),
                        ('end_date', '>', value),
                        ],
                    ])
        dimensions = cls.search(clause)
        if dimensions:
            dimension, = dimensions
            dimension_id = dimension.id
        else:
            dimension_id = None
        cls._get_dimension_cache.set(key, dimension_id)
        return dimension_id


class TableDefinitionDimensionOpenAskType(ModelView):
    'Open Table Value Dimension'
    __name__ = 'table.dimension.value.open.ask_type'
    table = fields.Many2One('table', 'Table', required=True)
    type = fields.Selection('get_types', 'Type', required=True, sort=False)

    @staticmethod
    def default_table():
        return Transaction().context.get('active_id', None)

    @fields.depends('table')
    def get_types(self):
        if not self.table:
            return []
        types = []
        for i in range(1, DIMENSION_MAX + 1):
            if getattr(self.table, 'dimension_kind%s' % i):
                types.append(('dimension%s' % i,
                        getattr(self.table, 'dimension_name%s' % i)))
        return types


class TableDefinitionDimensionOpen(Wizard):
    'Table Open Definition Dimension'
    __name__ = 'table.dimension.value.open'
    start_state = 'ask_type'
    ask_type = StateView('table.dimension.value.open.ask_type',
        'table.table_dimension_value_open_ask_type_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', True),
            ])
    open_ = StateAction('table.act_definition_dimension_form')

    def do_open_(self, action):
        context = {
            'table': self.ask_type.table.id,
            'type': self.ask_type.type,
            }
        domain = [
            ('definition', '=', self.ask_type.table.id),
            ('type', '=', self.ask_type.type),
            ]
        action['pyson_context'] = PYSONEncoder().encode(context)
        action['pyson_domain'] = PYSONEncoder().encode(domain)
        return action, {}


class TableCell(ModelSQL, ModelView):
    "Cell"
    __name__ = 'table.cell'
    definition = fields.Many2One('table', 'Definition', ondelete='CASCADE',
        required=True)
    value = fields.Char('Value')

    @classmethod
    def __setup__(cls):
        super(TableCell, cls).__setup__()
        cls._error_messages.update({
                'too_many_dimension_value':
                'Too many dimension values "%s" for "%s"',
                'too_few_dimension_value':
                'Too few dimension value "%s" for "%s"',
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')

        super(TableCell, cls).__register__(module_name)

        table = TableHandler(cls, module_name)
        table.index_action(['definition']
            + ['dimension%s' % i for i in range(1, DIMENSION_MAX + 1)], 'add')

    @classmethod
    def _view_look_dom_arch(cls, tree, type, field_children=None):
        pool = Pool()
        TableDefinition = pool.get('table')
        result = tree.xpath("//field[@name='dimensions']")
        if result:
            dimensions, = result
            dimension_max = DIMENSION_MAX
            table_id = Transaction().context.get('table')
            if table_id:
                table = TableDefinition(table_id)
                for i in range(DIMENSION_MAX, 0, -1):
                    field = 'dimension_kind%s' % i
                    if getattr(table, field):
                        dimension_max = i
                        break
            for i in range(1, dimension_max + 1):
                if tree.tag == 'form':
                    new_dimension = copy.copy(dimensions)
                    new_dimension.tag = 'label'
                    new_dimension.set('name', 'dimension%s' % i)
                    dimensions.addprevious(new_dimension)
                new_dimension = copy.copy(dimensions)
                new_dimension.set('name', 'dimension%s' % i)
                dimensions.addprevious(new_dimension)
            dimensions.getparent().remove(dimensions)
        return super(TableCell, cls)._view_look_dom_arch(tree, type,
            field_children=field_children)

    @staticmethod
    def default_definition():
        return Transaction().context.get('table')

    @classmethod
    def fields_get(cls, fields_names=None):
        pool = Pool()
        TableDefinition = pool.get('table')
        result = super(TableCell, cls).fields_get(fields_names=fields_names)
        table_id = Transaction().context.get('table')
        if table_id:
            table_definition = TableDefinition(table_id)
            if 'value' in result:
                result['value']['type'] = table_definition.type_
                if table_definition.type_ == 'numeric':
                    result['value']['digits'] = (12,
                        table_definition.number_of_digits)
            for i in range(1, DIMENSION_MAX + 1):
                dimension_field = 'dimension%s' % i
                dimension_name = 'dimension_name%s' % i
                if dimension_field in result:
                    result[dimension_field]['string'] = \
                        getattr(table_definition, dimension_name)

        return result

    @staticmethod
    def _dump_value(values):
        if 'value' in values:
            values = values.copy()
            if values['value'] is not None:
                values['value'] = str(values['value'])
        return values

    @staticmethod
    def _load_value(value, type_):
        if value is None:
            return value
        elif type_ == 'integer':
            return int(value)
        elif type_ == 'numeric':
            return Decimal(value)
        elif type_ == 'boolean':
            if value == 'True':
                return True
            return False
        elif type_ == 'date':
            return datetime.strptime(value, '%Y-%m-%d').date()
        return value

    def get_value_with_type(self):
        if not self.definition:
            return
        return self._load_value(self.value, self.definition.type_)

    def get_rec_name(self, name=None):
        if self.definition:
            return str(self.get_value_with_type())
        return super(TableCell, self).get_rec_name(name)

    @classmethod
    def import_data(cls, fields_names, data):
        pool = Pool()
        DimensionValue = pool.get('table.dimension.value')

        @memoize(1000)
        def search_dimension_value(field_name, dimension_name, table_id):
            domain = [
                ('type', '=', field_name),
                ('rec_name', '=', dimension_name),
                ]
            if table_id:
                domain += [('definition', '=', table_id)]
            dimension_values = DimensionValue.search(domain)
            try:
                dimension_value, = dimension_values
            except ValueError:
                if dimension_values:
                    cls.raise_user_error('too_many_dimension_value',
                        (dimension_name, field_name))
                else:
                    cls.raise_user_error('too_few_dimension_value',
                        (dimension_name, field_name))
            return dimension_value.id

        table_id = Transaction().context.get('table')
        for row in data:
            for i, field_name in enumerate(fields_names):
                dimension_name = row[i]
                if field_name.startswith('dimension'):
                    row[i] = search_dimension_value(field_name, dimension_name,
                        table_id)
        r = super(TableCell, cls).import_data(fields_names, data)
        return r

    @classmethod
    def delete(cls, entities):
        super(TableCell, cls).delete(entities)
        cls.table_cell_cache().clear()

    @classmethod
    def create(cls, values):
        values = [cls._dump_value(v) for v in values]
        ret = super(TableCell, cls).create(values)
        cls.table_cell_cache().clear()
        return ret

    @classmethod
    def write(cls, *args):
        new_args = []
        actions = iter(args)
        for records, values in zip(actions, actions):
            new_values = cls._dump_value(values)
            new_args.extend([records, new_values])
        super(TableCell, cls).write(*new_args)
        cls.table_cell_cache().clear()

    @classmethod
    def read(cls, ids, fields_names=None):
        pool = Pool()
        TableDefinition = pool.get('table')
        to_remove = []
        if fields_names and 'definition' not in fields_names:
            fields_names = fields_names[:]
            fields_names.append('definition')
            to_remove.append('definition')
        result = super(TableCell, cls).read(ids, fields_names=fields_names)
        if not fields_names or 'value' in fields_names:
            definitions = TableDefinition.browse(
                list(set(v['definition'] for v in result)))
            id2definition = dict((d.id, d) for d in definitions)
            for value in result:
                definition = id2definition[value['definition']]
                value['value'] = cls._load_value(
                    value['value'], definition.type_)
                for field in to_remove:
                    del value[field]
        return result

    @classmethod
    def table_cell_cache(cls):
        cache_holder = get_cache_holder()
        cell_cache = cache_holder.get('table_cell_cache')
        if cell_cache is None:
            cell_cache = CoogCache()
            cache_holder['table_cell_cache'] = cell_cache
        return cell_cache

    @classmethod
    def get_cell(cls, definition, *values):
        pool = Pool()
        Definition = pool.get('table')
        Dimension = pool.get('table.dimension.value')

        if not isinstance(definition, Definition):
            definition = Definition.get(definition)
        values = (values + (None,) * DIMENSION_MAX)[:DIMENSION_MAX]

        cache = cls.table_cell_cache()
        key = (definition.id, values)
        try:
            cell = cache[key]
        except KeyError:
            domain = [('definition', '=', definition.id)]
            for i in range(DIMENSION_MAX):
                value = values[i]
                dimension_id = Dimension.get_dimension_id(definition, i, value)
                domain.append(('dimension%d' % (i + 1), '=', dimension_id))
            cells = cls.search(domain)
            if not cells:
                cache[key] = None
                return None
            if len(cells) == 1:
                cell = cells[0]
                cache[key] = cell
            else:
                raise Exception('Several cells with same dimensions (%s)' %
                    domain)
        return cell

    @classmethod
    def get(cls, definition, *values):
        """
        Return the value for the tuple dimensions values.
        """
        cell = cls.get_cell(definition, *values)
        if cell:
            return cls._load_value(cell.value, definition.type_)

for i in range(1, DIMENSION_MAX + 1):
    setattr(TableCell, 'dimension%s' % i,
        fields.Many2One('table.dimension.value', 'Dimension %s' % i,
            ondelete='RESTRICT',
            domain=[
                ('definition', '=', Eval('definition')),
                ('type', '=', 'dimension%s' % i),
                ],
            depends=['definition']))


class TableOpen2DAskDimensions(ModelView):
    "Table Open 2D Ask Dimensions"
    __name__ = 'table.2d.open.ask_dimensions'
    definition = fields.Many2One(
        'table', 'Definition',
        readonly=True)

    @staticmethod
    def default_definition():
        return Transaction().context.get('active_id')

    @staticmethod
    def _default_dimension_required(dimension=0):
        TableDefinition = Pool().get('table')
        definition_id = Transaction().context.get('active_id')
        if definition_id:
            definition = TableDefinition(definition_id)
            return bool(getattr(definition, 'dimension_kind%s' % dimension))
        return False

    @classmethod
    def _view_look_dom_arch(cls, tree, type, field_children=None):
        dimensions, = tree.xpath("//field[@name='dimensions']")
        for i in range(3, DIMENSION_MAX + 1):
            label = etree.Element('label')
            label.set('name', 'dimension%s' % i)
            dimensions.addprevious(label)
            field = etree.Element('field')
            field.set('name', 'dimension%s' % i)
            field.set('widget', 'selection')
            dimensions.addprevious(field)
        dimensions.getparent().remove(dimensions)
        return super(TableOpen2DAskDimensions, cls)._view_look_dom_arch(tree,
            type, field_children=field_children)

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        'Dynamically use the current table dimension names'
        result = super(TableOpen2DAskDimensions, cls).fields_view_get(view_id,
            view_type)
        TableDefinition = Pool().get('table')
        definition_id = Transaction().context.get('active_id')
        if definition_id:
            definition = TableDefinition(definition_id)
            view_fields = result['fields']
            for i in range(3, DIMENSION_MAX + 1):
                view_fields['dimension%s' % i]['string'] = getattr(
                    definition, 'dimension_name%s' % i)
        return result

for i in range(3, DIMENSION_MAX + 1):
    setattr(TableOpen2DAskDimensions, 'dimension%s' % i,
        fields.Many2One('table.dimension.value', 'Dimension %s' % i,
            domain=[
                ('definition', '=', Eval('definition')),
                ('type', '=', 'dimension%s' % i),
                ],
            states={
                'required': Eval('dimension%s_required' % i, False),
                'invisible': ~Eval('dimension%s_required' % i),
                },
            depends=['definition', 'dimension%s_required' % i]))
    setattr(TableOpen2DAskDimensions, 'dimension%s_required' % i,
        fields.Boolean('Dimension %s Required', readonly=True))

    setattr(TableOpen2DAskDimensions, 'default_dimension%s_required' % i,
        staticmethod(partial(
                TableOpen2DAskDimensions._default_dimension_required,
                dimension=i)))


class TableOpen2D(Wizard):
    "Table Open 2D"
    __name__ = 'table.2d.open'
    start = StateTransition()
    ask_dimensions = StateView('table.2d.open.ask_dimensions',
        'table.table_2d_open_ask_dimensions_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', True),
            ])
    open_ = StateAction('table.act_table_2d_relate_form')

    def transition_start(self):
        TableDefinition = Pool().get('table')
        definition_id = int(Transaction().context['active_id'])
        if definition_id != -1:
            definition = TableDefinition(definition_id)
            if (not definition.dimension_kind1
                    or not definition.dimension_kind2
                    or definition.dimension_kind3
                    or definition.dimension_kind4):
                return 'ask_dimensions'
        return 'open_'

    def do_open_(self, action):
        context = {
            'table': Transaction().context['active_id'],
        }
        for i in range(3, DIMENSION_MAX + 1):
            if getattr(self.ask_dimensions, 'dimension%s' % i, None):
                context['dimension%s' % i] = getattr(
                    self.ask_dimensions, 'dimension%s' % i).id
        action['pyson_context'] = PYSONEncoder().encode(context)
        return action, {}


class Table2DDict(dict):

    def __getitem__(self, key):
        pool = Pool()
        TableCell = pool.get('table.cell')
        if key.startswith('col'):
            field = copy.copy(TableCell.value)
            field.string = ''
            return field
        return super(Table2DDict, self).__getitem__(key)

    def __contains__(self, key):
        if key.startswith('col'):
            return True
        return super(Table2DDict, self).__contains__(key)

    def keys(self):
        pool = Pool()
        TableDefinitionDimension = pool.get(
            'table.dimension.value')
        definition_id = int(
            Transaction().context.get('table', -1))
        dimensions2 = TableDefinitionDimension.search([
                ('type', '=', 'dimension2'),
                ('definition', '=', definition_id),
                ])
        result = super(Table2DDict, self).keys()
        result += ['col%d' % d.id for d in dimensions2]
        return result


class Crosstab(Function):
    _function = 'CROSSTAB'


class Table2D(ModelSQL, ModelView):
    "Table 2D"
    __name__ = 'table.2d'

    row = fields.Many2One('table.dimension.value', 'Row', ondelete='CASCADE',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(Table2D, cls).__setup__()
        cls._error_messages.update({
                'not_2d': 'The table is not 2D',
                })

    @classmethod
    def __post_setup__(cls):
        super(Table2D, cls).__post_setup__()
        cls._fields = Table2DDict(cls._fields)

    @classmethod
    def table_query(cls):
        if not backend.name() == 'postgresql':
            return super(Table2D, cls).table_query()
        pool = Pool()
        TableCell = pool.get('table.cell')
        TableDefinition = pool.get('table')
        TableDefinitionDimension = pool.get(
            'table.dimension.value')
        context = Transaction().context
        cursor = Transaction().connection.cursor()
        definition_id = int(context.get('table', -1))
        if definition_id != -1:
            definition = TableDefinition(definition_id)
            dim_test = False
            for i in range(3, DIMENSION_MAX + 1):
                dim_test = (dim_test
                    or (getattr(definition, 'dimension_kind%s' % i)
                        and not context.get('dimension%s' % i)))
            if (not definition.dimension_kind1
                    or not definition.dimension_kind2
                    or dim_test):
                cls.raise_user_error('not_2d')

        dimension = TableDefinitionDimension.__table__()
        cell = TableCell.__table__()

        dimensions2 = TableDefinitionDimension.search([
                ('type', '=', 'dimension2'),
                ('definition', '=', definition_id),
                ])
        columns_definitions = [('id', cls.id.sql_type().base)]
        columns_definitions += [
            ('col%d' % d.id, TableCell.value.sql_type().base)
            for d in dimensions2]
        dimensions_clause = Literal(True)
        for i in range(3, DIMENSION_MAX + 1):
            dimension_name = 'dimension%s' % i
            column = Column(cell, dimension_name)
            if context.get(dimension_name) is not None:
                dimensions_clause &= column == context[dimension_name]
            else:
                dimensions_clause &= column == None

        source = dimension.join(cell, 'LEFT',
            (dimension.id == cell.dimension1) & dimensions_clause
            ).select(dimension.id, cell.dimension2, cell.value,
                where=(dimension.definition == definition_id)
                & (dimension.type == 'dimension1'),
                order_by=dimension.id)
        category = dimension.select(dimension.id,
            where=(dimension.type == 'dimension2')
            & (dimension.definition == definition_id),
            order_by=[
                dimension.sequence == None,
                dimension.sequence.asc,
                dimension.value.asc,
                dimension.date.asc,
                dimension.start.asc, dimension.end.asc,
                dimension.start_date.asc, dimension.end_date.asc])

        cursor.execute(*source)
        source_text = cursor.query
        cursor.execute(*category)
        category_text = cursor.query

        func = Crosstab(source_text, category_text,
            columns_definitions=columns_definitions)
        columns = [Column(func, c).as_(c) for c, _ in columns_definitions]
        columns += [func.id.as_('row'),
            Literal(0).as_('create_uid'), Literal(None).as_('write_uid'),
            CurrentTimestamp().as_('create_date'),
                    Literal(None).as_('write_date')]
        return func.select(*columns)

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        pool = Pool()
        TableCell = pool.get('table.cell')
        TableDefinition = pool.get('table')
        TableDefinitionDimension = pool.get(
            'table.dimension.value')

        definition_id = int(
            Transaction().context.get('table', -1))
        definition = TableDefinition(definition_id)
        value_field = TableCell.fields_get(['value'])['value']
        dimensions2 = TableDefinitionDimension.search([
                ('type', '=', 'dimension2'),
                ('definition', '=', definition_id),
                ])
        fields = {}
        fields['row'] = cls.fields_get(['row'])['row']
        xml = '<?xml version="1.0"?>'
        title = definition.rec_name
        dimension_title = []
        for i in range(3, DIMENSION_MAX + 1):
            dimension = 'dimension%s' % i
            if Transaction().context.get(dimension):
                dimension = TableDefinitionDimension(
                    Transaction().context[dimension])
                dimension_title.append(dimension.rec_name)
        if dimension_title:
            title += ' (' + ', '.join(dimension_title) + ')'
        if view_type == 'tree':
            xml += '<tree string="%s" editable="bottom">' % title
            xml += '<field name="row"/>'
        elif view_type == 'form':
            xml += '<form string="%s" col="2">' % title
            xml += '<label name="row"/><field name="row"/>'
        for dimension in dimensions2:
            field_name = 'col%d' % dimension.id
            if view_type == 'form':
                xml += '<label name="%s"/>' % field_name
            xml += '<field name="%s"/>' % field_name
            field = value_field.copy()
            field['string'] = dimension.rec_name
            fields[field_name] = field
        if view_type == 'tree':
            xml += '</tree>'
        elif view_type == 'form':
            xml += '</form>'
        return {
            'type': 'tree',
            'arch': xml,
            'fields': fields,
            'field_childs': None,
            'view_id': 0,
        }

    @classmethod
    def write(cls, rows, values):
        pool = Pool()
        TableCell = pool.get('table.cell')
        context = Transaction().context
        super(Table2D, cls).write(rows, values)
        dim1_ids = [r.id for r in rows]
        definition_id = int(context.get('table', -1))
        to_creates = []
        for col, value in values.iteritems():
            dim2_id = int(col[3:])
            domain = [
                ('definition', '=', definition_id),
                ('dimension1', 'in', dim1_ids),
                ('dimension2', '=', dim2_id),
                ]
            domain += [
                ('dimension%s' % i, '=', context.get('dimension%s' % i))
                for i in range(3, DIMENSION_MAX + 1)]

            cells = TableCell.search(domain)
            if cells:
                TableCell.write(cells, {
                        'value': value,
                        })
            for dim1_id in (set(dim1_ids) -
                    set(i.dimension1.id for i in cells)):
                to_create_values = {
                    'definition': definition_id,
                    'value': value,
                    'dimension1': dim1_id,
                    'dimension2': dim2_id,
                    }
                for i in range(3, DIMENSION_MAX + 1):
                    to_create_values['dimension%s' % i] = context.get(
                        'dimension%s' % i)
                to_creates.append(to_create_values)
        if to_creates:
            TableCell.create(to_creates)

    @classmethod
    def read(cls, ids, fields_names=None):
        pool = Pool()
        TableDefinition = pool.get('table')
        TableCell = pool.get('table.cell')
        result = super(Table2D, cls).read(ids, fields_names=fields_names)
        definition_id = int(
            Transaction().context.get('table', -1))
        definition = TableDefinition(definition_id)
        for value in result:
            for field in value:
                if field.startswith('col'):
                    value[field] = TableCell._load_value(value[field],
                        definition.type_)
        return result
