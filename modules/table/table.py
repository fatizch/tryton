import re
import copy
import time
from datetime import datetime
from decimal import Decimal
from functools import partial
try:
    import simplejson as json
except ImportError:
    import json

from lxml import etree
from sql import Column, Literal
from sql.functions import Function, Now

from trytond.config import CONFIG
from trytond import backend
from trytond.pool import Pool
from trytond.pyson import Not, Eval, Bool, Or, PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.protocols.jsonrpc import JSONEncoder
from trytond.tools import memoize

from trytond.modules.cog_utils.model import CoopSQL as ModelSQL
from trytond.modules.cog_utils.model import CoopView as ModelView
from trytond.modules.cog_utils import fields
from trytond.modules.cog_utils import utils, coop_string

__all__ = [
    'TableCell',
    'TableDefinition',
    'TableDefinitionDimension',
    'TableOpen2DAskDimensions',
    'TableOpen2D',
    'Table2D',
    'ManageDimension',
    'DimensionDisplayer',
    'TableCreation',
    ]

TYPE = [
    ('char', 'Char'),
    ('integer', 'Integer'),
    ('numeric', 'Numeric'),
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

DIMENSION_MAX = int(CONFIG.get('table_dimension', 4))


class TableDefinition(ModelSQL, ModelView):
    "Table Definition"

    __name__ = 'table'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, on_change_with=['name', 'code'])
    type_ = fields.Selection(TYPE, 'Type', required=True)
    kind = fields.Function(fields.Char('Kind'), 'get_kind')
    cells = fields.One2Many('table.cell', 'definition', 'Cells')
    number_of_digits = fields.Integer('Number of Digits', states={
            'invisible': Eval('type_', '') != 'numeric'})

    @classmethod
    def __setup__(cls):
        super(TableDefinition, cls).__setup__()
        cls._sql_constraints = [
            ('code_unique', 'UNIQUE(code)',
                'The code of "Table Definition" must be unique'),
        ]
        cls._order.insert(0, ('name', 'ASC'))
        cls._error_messages.update({
                'existing_clone': ('A clone record already exists : %s(%s)')})
        cls._buttons.update({
                'manage_dimension': {
                    'icon': 'tryton-go-jump',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        super(TableDefinition, cls).__register__(module_name)

        if CONFIG['db_type'] != 'postgresql':
            return

        with Transaction().new_cursor() as transaction:
            cursor = transaction.cursor
            try:
                cursor.execute('CREATE EXTENSION IF NOT EXISTS tablefunc', ())
                cursor.commit()
            except:
                import logging
                logger = logging.getLogger('database')
                logger.warning('Unable to activate tablefunc extension, '
                    '2D displaying of tables will not be available')
                cursor.rollback()

    @classmethod
    def copy(cls, records, default=None):
        result = []
        for record in records:
            existings = cls.search(['OR',
                    [('code', '=', '%s_clone' % record.code)],
                    [('name', '=', '%s Clone' % record.name)]])
            for existing in existings:
                cls.raise_user_error('existing_clone',
                    (existing.name, existing.code))
            values = json.dumps(record.export_json()[1], cls=JSONEncoder)
            values = values.replace('["code", "%s"]' % record.code,
                '["code", "%s_clone"]' % record.code)
            values = values.replace('"code": "%s"' % record.code,
                '"code": "%s_clone"' % record.code)
            values = values.replace(u'"name": "%s"' % record.name,
                u'"name": "%s Clone"' % record.name)
            result += record.import_json(values)[cls.__name__].values()
        return result

    def _export_override_cells(self, exported, result, my_key):
        def lock_dim_and_export(locked, results, dimensions):
            my_dim = len(locked) + 1
            try:
                dims = getattr(self, 'dimension%s' % my_dim)
            except AttributeError:
                dims = None
            if not dims:
                matches = TableCell.search([('definition', '=', self.id)] + [
                    ('dimension%s' % (i + 1), '=', locked[i])
                    for i in xrange(my_dim - 1)])
                if not matches:
                    results.append(None)
                else:
                    results.append(matches[0].value)
                return
            else:
                if len(dimensions) == len(locked):
                    dimensions.append(len(dims))
                for elem in dims:
                    locked.append(elem.id)
                    lock_dim_and_export(locked, results, dimensions)
                    locked.pop()
        result = []
        dimensions = []
        lock_dim_and_export([], result, dimensions)
        return [dimensions, result]

    @classmethod
    def _import_override_cells(cls, instance_key, good_instance,
            field_value, values, created, relink):
        Cell = Pool().get('table.cell')
        if (hasattr(good_instance, 'id') and good_instance.id):
            table_id = good_instance.id
            Cell.delete(Cell.search([('definition', '=', table_id)]))
        else:
            table_id = None
        dimensions, cell_values = field_value
        cells_number = len(cell_values)
        cell_values = list(cell_values)

        def lock_dim_and_import(locked, relink_template):
            my_dim = len(locked) + 1
            if my_dim > len(dimensions):
                to_relink = list(relink_template)
                cell = Cell()
                cell.value = cell_values.pop(0)
                cell.definition = table_id
                cell._import_finalize((instance_key,
                        cells_number - len(cell_values)),
                    cell, False, created, relink, to_relink)
            else:
                for elem in xrange(dimensions[my_dim - 1]):
                    relink_template.append(('dimension%s' % my_dim, (
                                'table.dimension.value', (
                                    instance_key, 'dimension%s' % my_dim,
                                    elem + 1))))
                    locked.append(elem + 1)
                    lock_dim_and_import(locked, relink_template)
                    locked.pop()
                    relink_template.pop()
        locks = []
        if table_id:
            template = []
        else:
            template = [('definition', ('table',
                   instance_key))]
        lock_dim_and_import(locks, template)

    @classmethod
    def default_dimension_order(cls):
        return 'alpha'

    @staticmethod
    def default_type_():
        return 'char'

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
    def write(cls, records, values):
        pool = Pool()
        TableDefinitionDimension = pool.get('table.dimension.value')
        super(TableDefinition, cls).write(records, values)
        if any(k for k in values if k.startswith('dimension_order')):
            dimensions = [d for r in records for i in xrange(DIMENSION_MAX)
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

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    @classmethod
    def default_number_of_digits(cls):
        return 2

    @classmethod
    @ModelView.button_action('table.act_manage_dimension')
    def manage_dimension(cls, tables):
        pass

    def get_index_value(self, at_date=None):
        Cell = Pool().get('table.cell')
        if not at_date:
            at_date = utils.today()
        cell = Cell.get_cell(self, (at_date))
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
        TableDefinition.default_dimension_order)

    setattr(TableDefinition, 'dimension%s' % i,
        fields.One2ManyDomain('table.dimension.value', 'definition',
            'Dimension %s' % i, domain=[('type', '=', 'dimension%s' % i)]))


def dimension_state(kind):
    return {
        'invisible': Eval('dimension_kind') != kind,
        }

DIMENSION_DEPENDS = ['dimension_kind']


class TableDefinitionDimension(ModelSQL, ModelView):
    "Table Definition Dimension"

    __name__ = 'table.dimension.value'

    name = fields.Char('Name', select=True)
    sequence = fields.Integer('Sequence',
        states={
            'invisible': Eval('dimension_order') == 'alpha',
            }, depends=['dimension_order'])
    definition = fields.Many2One(
        'table', 'Definition',
        required=True, ondelete='CASCADE')
    type = fields.Selection(
        [('dimension%s' % i, 'Dimension %s' % i)
            for i in range(1, DIMENSION_MAX + 1)],
        'Type', required=True)
    dimension_kind = fields.Function(fields.Selection(KIND, 'Dimension Kind',
            on_change_with=['definition', 'type']),
        'on_change_with_dimension_kind')
    dimension_order = fields.Function(fields.Selection(ORDER,
            'Dimension Order', on_change_with=['definition', 'type']),
        'on_change_with_dimension_order')
    value = fields.Char(
        'Value', states=dimension_state('value'),
        depends=DIMENSION_DEPENDS)
    date = fields.Date(
        'Date', states=dimension_state('date'),
        depends=DIMENSION_DEPENDS)
    start = fields.Float(
        'Start', states=dimension_state('range'),
        depends=DIMENSION_DEPENDS)
    end = fields.Float(
        'End', states=dimension_state('range'),
        depends=DIMENSION_DEPENDS)
    start_date = fields.Date(
        'Start Date',
        states=dimension_state('range-date'), depends=DIMENSION_DEPENDS)
    end_date = fields.Date(
        'End Date',
        states=dimension_state('range-date'), depends=DIMENSION_DEPENDS)

    @classmethod
    def __setup__(cls):
        super(TableDefinitionDimension, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        TableHandler = backend.get('TableHandler')

        super(TableDefinitionDimension, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        table.index_action(['definition', 'type'], 'add')

    def on_change_with_dimension_kind(self, name=None):
        if getattr(self, 'definition', None) and getattr(self, 'type', None):
            idx = int(self.type[len('dimension'):])
            return getattr(self.definition, 'dimension_kind%s' % idx)

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
        records = super(TableDefinitionDimension, cls).create(vlist)
        cls.clean_sequence(records)
        cls.set_name(records)
        return records

    @classmethod
    def write(cls, records, values):
        super(TableDefinitionDimension, cls).write(records, values)
        cls.clean_sequence(records)
        cls.set_name(records)

    @classmethod
    def set_name(cls, dimensions):
        pool = Pool()
        Lang = pool.get('ir.lang')

        lang, = Lang.search([('code', '=', CONFIG['language'])])
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
                    dimension.start, dimension.end)
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
            records = cls.search([('name', 'ilike', value.strip('%'))])
            if len(records) == 1:
                return [('id', '=', records[0].id)]
        return [('name',) + tuple(clause[1:])]


class TableCell(ModelSQL, ModelView):
    "Cell"
    __name__ = 'table.cell'
    definition = fields.Many2One(
        'table', 'Definition',
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
        cursor = Transaction().cursor
        TableHandler = backend.get('TableHandler')

        super(TableCell, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        table.index_action(['definition']
            + ['dimension%s' % i for i in range(1, DIMENSION_MAX + 1)], 'add')

    @classmethod
    def _view_look_dom_arch(cls, tree, type, field_children=None):
        result = tree.xpath("//field[@name='dimensions']")
        if result:
            dimensions, = result
            for i in range(1, DIMENSION_MAX + 1):
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
        if Transaction().context.get('table') and 'value' in result:
            table_definition = \
                TableDefinition(Transaction().context['table'])
            result['value']['type'] = table_definition.type_
            if table_definition.type_ == 'numeric':
                result['value']['digits'] = (12,
                    table_definition.number_of_digits)
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
        start = time.time()
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
        print 'Time:', time.time() - start
        return r

    @classmethod
    def create(cls, values):
        values = [cls._dump_value(v) for v in values]
        return super(TableCell, cls).create(values)

    @classmethod
    def write(cls, records, values):
        values = cls._dump_value(values)
        return super(TableCell, cls).write(records, values)

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
    def get_cell(cls, definition, *values):
        pool = Pool()
        Definition = pool.get('table')
        Dimension = pool.get('table.dimension.value')

        if not isinstance(definition, Definition):
            definition = Definition.get(definition)
        values = (values + (None,) * DIMENSION_MAX)[:DIMENSION_MAX]
        domain = [('definition', '=', definition.id)]
        for i in range(DIMENSION_MAX):
            value = values[i]
            kind = getattr(definition, 'dimension_kind%d' % (i + 1))
            dimension = None
            clause = [
                ('definition', '=', definition.id),
                ('type', '=', 'dimension%d' % (i + 1)),
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
            dimensions = Dimension.search(clause)
            if dimensions:
                dimension, = dimensions
            domain.append(('dimension%d' % (i + 1), '=',
                    dimension.id if dimension else None))
        try:
            cells = cls.search(domain)
        except ValueError:
            return None
        if not cells:
            return None
        if len(cells) == 1:
            return cells[0]
        else:
            raise Exception('Several cells with same dimensions (%s)' % domain)

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
            ondelete='CASCADE',
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
    def default_dimension_required(dimension=0):
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
                TableOpen2DAskDimensions.default_dimension_required,
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

    row = fields.Many2One(
        'table.dimension.value', 'Row',
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
        if not CONFIG['db_type'] == 'postgresql':
            return True
        pool = Pool()
        TableCell = pool.get('table.cell')
        TableDefinition = pool.get('table')
        TableDefinitionDimension = pool.get(
            'table.dimension.value')
        context = Transaction().context
        cursor = Transaction().cursor
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
            Now().as_('create_date'), Literal(None).as_('write_date')]
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


class DimensionDisplayer(ModelView):
    'Dimension Displayer'

    __name__ = 'table.manage_dimension.show.dimension'

    name = fields.Char('Name')
    order = fields.Selection(ORDER, 'Order')
    kind = fields.Selection(KIND, 'Kind')
    input_mode = fields.Selection(
        [('flat_file', 'Flat data'), ('boolean', 'Boolean')], 'Input Mode',
        on_change=['values', 'order', 'input_mode', 'kind', 'date_format',
            'input_mode'], states={'invisible': Eval('kind', '') != 'value'})
    values = fields.One2Many('table.dimension.value', None, 'Dimension Values',
        on_change=['values', 'order', 'kind', 'date_format', 'input_mode'])
    converted_text = fields.Text('Converted Text')
    table = fields.Many2One('table', 'Table', states={
            'invisible': True})
    cur_dimension = fields.Integer('Current Dimension', states={
            'invisible': True})
    input_text = fields.Text('Input Text', on_change=['input_text',
            'date_format', 'kind', 'values', 'input_mode'], states={
            'invisible': Eval('input_mode', '') != 'flat_file'},)
    date_format = fields.Char('Date Format', states={
            'invisible': Not(Or(
                    Eval('kind', '') == 'date',
                    Eval('kind', '') == 'range-date'))},
            # 'invisible': Or(Eval('kind', '') == 'date',
                # Eval('kind', '') == 'range-date')
            # and Eval('input_mode', '') != 'flat_file'},
        on_change=['date_format', 'values', 'input_text', 'kind',
            'input_mode'])

    @classmethod
    def __setup__(cls):
        super(DimensionDisplayer, cls).__setup__()
        cls._error_messages.update({
            'invalid_format': 'Impossible to convert data %s with format %s'})

    @classmethod
    def default_input_mode(cls):
        return 'flat_file'

    @staticmethod
    def default_cur_dimension():
        return 1

    def on_change_input_text(self):
        if self.input_text:
            return {'converted_text': self.convert_values()}
        else:
            return self.on_change_values()

    def on_change_date_format(self):
        if self.kind not in ('date', 'range-date'):
            return {'date_format': ''}
        if self.input_text:
            return self.on_change_input_text()
        return self.on_change_values()

    def on_change_values(self):
        if not self.values:
            return {'converted_text': ''}
        existing = self.get_existing_values(self.kind, self.values)
        return {'converted_text': self.convert_existing_values(existing,
                self.kind, self.date_format)}

    def on_change_input_mode(self):
        if self.input_mode == 'boolean':
            return {
                'input_text': '',
                'converted_text': 'True\nFalse'}
        elif self.input_mode == 'flat_file':
            if (hasattr(self, 'input_text') and self.input_text):
                return self.on_change_input_text()
            else:
                return {'converted_text': ''}
        return {}

    def changing_ok(self):
        if not self.table.cells:
            return True
        if self.kind != getattr(self.table, 'dimension_kind%s' %
                self.cur_dimension):
            return False
        if not self.input_text and self.input_mode == 'flat_file':
            return True
        if self.input_text:
            return False
        if self.get_existing_values(self.kind, self.values) != \
                self.format_text_values(self.convert_values()):
            return False

    def convert_values(self):
        if self.input_mode == 'boolean':
            return 'True\nFalse'
        elif self.input_mode == 'flat_file' and self.input_text:
            result = [x for x in re.split(r'[ ,|;\n\t]+', self.input_text)]
            if self.kind in ('date', 'range-date'):
                try:
                    datetime.strptime(result[0], self.date_format)
                except:
                    self.raise_user_error('invalid_format', (result[0],
                            self.date_format))
            return '\n'.join(result)

    @classmethod
    def get_existing_values(cls, kind, values):
        res = []
        the_func = lambda x: x.value
        if kind == 'range':
            the_func = lambda x: x.start
        elif kind == 'date':
            the_func = lambda x: x.date
        elif kind == 'range-date':
            the_func = lambda x: x.start_date
        for elem in values:
            res.append(the_func(elem))
        return res

    @classmethod
    def convert_existing_values(cls, values, kind, date_format=None):
        res = []
        if kind in ('value', 'range'):
            the_func = lambda x: str(x)
        elif kind in ('date', 'range-date'):
            the_func = lambda x: datetime.strftime(x, date_format)
        for elem in values:
            res.append(the_func(elem))
        return '\n'.join(res)

    def format_text_values(self, text_values):
        if self.kind in ('value', 'range'):
            the_list = text_values
            if self.order == 'alpha':
                the_list = sorted(text_values)
        elif self.kind in ('date', 'range-date'):
            the_list = []
            for elem in text_values:
                if elem == 'None':
                    the_list.append(None)
                    continue
                try:
                    the_list.append(datetime.strptime(elem, self.date_format))
                except ValueError:
                    self.raise_user_error('invalid_format', (elem,
                            self.date_format))
        return the_list


class ManageDimension(Wizard):
    'Manage Dimension'
    __name__ = 'table.manage_dimension'

    start_state = 'dimension_management'
    dimension_management = StateView('table.manage_dimension.show.dimension',
        'table.dimension_displayer_view_form', [
            Button('Exit', 'end', 'tryton-cancel'),
            Button('Apply', 'apply_', 'tryton-ok', True),
            Button('Previous Dimension', 'previous_dim', 'tryton-go-previous',
                states={
                    'invisible': Eval('cur_dimension', 1) <= 1,
                    }),
            Button('Next Dimension', 'next_dim', 'tryton-go-next', states={
                    'invisible': Eval('cur_dimension', 1) >= DIMENSION_MAX,
                    }),
            Button('View Data', 'view_data', 'tryton-find')])
    apply_ = StateTransition()
    next_dim = StateTransition()
    previous_dim = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ManageDimension, cls).__setup__()
        cls._error_messages.update({
            'dangerous_change': 'The requested change might delete data.',
        })
        setattr(cls, 'view_data', StateAction('table.act_table_2d_open'))

    def get_my_dimension(self):
        if not getattr(self.dimension_management, 'cur_dimension', None):
            return 1
        else:
            return self.dimension_management.cur_dimension

    def default_dimension_management(self, data):
        TableDef = Pool().get('table')
        TableDimension = Pool().get('table.dimension.value')
        Displayer = Pool().get('table.manage_dimension.show.dimension')
        selected_table = TableDef(Transaction().context.get('active_id'))
        selected_dimension = self.get_my_dimension()

        values = TableDimension.search([
                ('type', '=', 'dimension%s' % selected_dimension),
                ('definition', '=', selected_table.id)])
        res = {
            'table': selected_table.id,
            'cur_dimension': selected_dimension,
            'name': getattr(selected_table, 'dimension_name%s' %
                selected_dimension),
            'kind': getattr(selected_table, 'dimension_kind%s' %
                selected_dimension),
            'order': getattr(selected_table, 'dimension_order%s' %
                selected_dimension),
            'date_format': '%d%m%y',
            'values': [x.id for x in values]}
        res['converted_text'] = Displayer.convert_existing_values(
            Displayer.get_existing_values(res['kind'], values), res['kind'],
            res['date_format'])
        return res

    def transition_apply_(self):
        if not self.dimension_management.changing_ok():
            self.raise_user_warning('dangerous_change', 'dangerous_change')
        the_table = self.dimension_management.table
        idx = self.dimension_management.cur_dimension
        setattr(the_table, 'dimension_order%s' % idx,
            self.dimension_management.order)
        setattr(the_table, 'dimension_kind%s' % idx,
            self.dimension_management.kind)
        setattr(the_table, 'dimension_name%s' % idx,
            self.dimension_management.name)
        existing_values = self.dimension_management.get_existing_values(
            self.dimension_management.order, self.dimension_management.values)
        new_values = self.dimension_management.convert_values()
        the_table.save()
        if not new_values:
            return 'dimension_management'
        new_values = self.dimension_management.format_text_values(
            new_values.split('\n'))
        if existing_values == new_values:
            return 'dimension_management'
        Dimension = Pool().get('table.dimension.value')
        Dimension.delete(Dimension.search([
                    ('type', '=', 'dimension%s' % idx),
                    ('definition', '=', the_table.id)]))
        dim_type = self.dimension_management.kind
        for i, elem in enumerate(new_values):
            new_dim = Dimension()
            new_dim.type = 'dimension%s' % idx
            new_dim.definition = the_table.id
            new_dim.sequence = i
            if dim_type == 'date':
                new_dim.date = elem
            elif dim_type == 'value':
                new_dim.value = elem
            elif dim_type == 'range':
                new_dim.start = elem
                new_dim.end = new_values[i + 1] if len(new_values) > i + 1 \
                    else None
            elif dim_type == 'range-date':
                new_dim.start_date = elem
                new_dim.end_date = new_values[i + 1] \
                    if len(new_values) > i + 1 else None
            new_dim.save()
        return 'dimension_management'

    def transition_previous_dim(self):
        self.transition_apply_()
        self.dimension_management.cur_dimension -= 1
        return 'dimension_management'

    def transition_next_dim(self):
        self.transition_apply_()
        self.dimension_management.cur_dimension += 1
        return 'dimension_management'

    def do_view_data(self, action):
        self.transition_apply_()
        table_id = Transaction().context.get('active_id')
        data = {
            'model': 'table',
            'id': table_id,
            'ids': [table_id],
            }
        return action, data


class TableCreation(Wizard):
    'Create New Table'

    __name__ = 'table.create'

    start_state = 'new_table'
    new_table = StateView('table', 'table.table_basic_data_view_form', [
            Button('Exit', 'end', 'tryton-cancel'),
            Button('Edit Dimensions', 'edit_dim_1', 'tryton-go-next',
                default=True)])
    edit_dim_1 = StateTransition()
    launch_edition = StateAction('table.act_manage_dimension')

    def transition_edit_dim_1(self):
        self.new_table.save()
        return 'launch_edition'

    def do_launch_edition(self, action):
        data = {
            'model': 'table',
            'id': self.new_table.id,
            'ids': [self.new_table.id],
            }
        return action, data
