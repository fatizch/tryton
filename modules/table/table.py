import re
import copy
from datetime import datetime
from decimal import Decimal
try:
    import simplejson as json
except ImportError:
    import json

from sql import Column, Literal
from sql.functions import Function, Now

from trytond.config import CONFIG
from trytond import backend
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.pyson import Not, Eval, If, Bool, Or, PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.protocols.jsonrpc import JSONEncoder

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
    'DimensionDisplayer',
    'ManageDimension1',
    'ManageDimension2',
    'ManageDimension3',
    'ManageDimension4',
    'TableCreation',
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

DIMENSION_MAX = 4

DIMENSION_DEPENDS = ['type']


def dimension_state(kind):
    return {
        'invisible': (If(
            Eval('type') == 'dimension1',
            Eval('_parent_definition', {}).get('dimension_kind1', kind),
            If(
                Eval('type') == 'dimension2',
                Eval('_parent_definition', {}).get('dimension_kind2', kind),
                If(
                    Eval('type') == 'dimension3',
                    Eval('_parent_definition', {}).get(
                        'dimension_kind3', kind),
                    Eval('_parent_definition', {}).get(
                        'dimension_kind4', kind)))) != kind)}


class TableDefinition(ModelSQL, ModelView):
    "Table Definition"

    __name__ = 'table'

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True, on_change_with=['name', 'code'])
    type_ = fields.Selection(
        [
            ('char', 'Char'),
            ('integer', 'Integer'),
            ('numeric', 'Numeric'),
            ('boolean', 'Boolean'),
            ('date', 'Date'),
        ], 'Type', required=True)
    dimension_order1 = fields.Selection(
        ORDER, 'Dimension Order 1',
        states={
            'invisible': ~Eval('dimension_kind1'),
            'required': Bool(Eval('dimension_kind1'))},
        depends=['dimension_kind1'])
    dimension_order2 = fields.Selection(
        ORDER, 'Dimension Order 2',
        states={
            'invisible': ~Eval('dimension_kind2'),
            'required': Bool(Eval('dimension_kind2')),
        },
        depends=['dimension_kind2'])
    dimension_order3 = fields.Selection(
        ORDER, 'Dimension Order 3',
        states={
            'invisible': ~Eval('dimension_kind3'),
            'required': Bool(Eval('dimension_kind3')),
        },
        depends=['dimension_kind3'])
    dimension_order4 = fields.Selection(
        ORDER, 'Dimension Order 4',
        states={
            'invisible': ~Eval('dimension_kind3'),
            'required': Bool(Eval('dimension_kind3')),
        },
        depends=['dimension_kind3'])
    dimension_kind1 = fields.Selection(
        KIND, 'Dimension Kind 1',
        states={
            'readonly': Bool(Eval('dimension1')),
        })
    dimension_kind2 = fields.Selection(
        KIND, 'Dimension Kind 2',
        states={
            'readonly': Bool(Eval('dimension2')),
        })
    dimension_kind3 = fields.Selection(
        KIND, 'Dimension Kind 3',
        states={
            'readonly': Bool(Eval('dimension3')),
        })
    dimension_kind4 = fields.Selection(
        KIND, 'Dimension Kind 4',
        states={'readonly': Bool(Eval('dimension4'))})
    dimension1 = fields.One2ManyDomain(
        'table.dimension.value', 'definition', 'Dimension 1',
        domain=[('type', '=', 'dimension1')],
        states={'invisible': ~Eval('dimension_kind1')},
        depends=['dimension_kind1'])
    dimension2 = fields.One2ManyDomain(
        'table.dimension.value', 'definition', 'Dimension 2',
        domain=[('type', '=', 'dimension2')],
        states={'invisible': ~Eval('dimension_kind2')},
        depends=['dimension_kind2'])
    dimension3 = fields.One2ManyDomain(
        'table.dimension.value', 'definition', 'Dimension 3',
        domain=[('type', '=', 'dimension3')],
        states={'invisible': ~Eval('dimension_kind3')},
        depends=['dimension_kind4'])
    dimension4 = fields.One2ManyDomain(
        'table.dimension.value', 'definition', 'Dimension 4',
        domain=[('type', '=', 'dimension4')],
        states={'invisible': ~Eval('dimension_kind4')},
        depends=['dimension_kind4'])
    dimension_name1 = fields.Char(
        'Name',
        states={
            'invisible': ~Eval('dimension_kind1'),
        })
    dimension_name2 = fields.Char(
        'Name',
        states={
            'invisible': ~Eval('dimension_kind2'),
        })
    dimension_name3 = fields.Char(
        'Name',
        states={
            'invisible': ~Eval('dimension_kind3'),
        })
    dimension_name4 = fields.Char(
        'Name',
        states={
            'invisible': ~Eval('dimension_kind4'),
        })
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
        cls.__rpc__.update({
                'manage_dimension_1': RPC(instantiate=0),
                'manage_dimension_2': RPC(instantiate=0),
                'manage_dimension_3': RPC(instantiate=0),
                'manage_dimension_4': RPC(instantiate=0),
                })
        cls._order.insert(0, ('name', 'ASC'))

        cls._error_messages.update({
                'existing_clone': ('A clone record already exists : %s(%s)')})

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

    @staticmethod
    def default_dimension_order1():
        return 'alpha'
    default_dimension_order2 = default_dimension_order1
    default_dimension_order3 = default_dimension_order1
    default_dimension_order4 = default_dimension_order1

    @staticmethod
    def default_type_():
        return 'char'

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
    @ModelView.button_action('table.act_manage_dimension_1')
    def manage_dimension_1(cls, tables):
        pass

    @classmethod
    @ModelView.button_action('table.act_manage_dimension_2')
    def manage_dimension_2(cls, tables):
        pass

    @classmethod
    @ModelView.button_action('table.act_manage_dimension_3')
    def manage_dimension_3(cls, tables):
        pass

    @classmethod
    @ModelView.button_action('table.act_manage_dimension_4')
    def manage_dimension_4(cls, tables):
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


class TableDefinitionDimension(ModelSQL, ModelView):
    "Table Definition Dimension"

    __name__ = 'table.dimension.value'
    _order_name = 'rec_name'

    sequence = fields.Integer(
        'Sequence',
        states={
            'invisible': (If(
                Eval('type') == 'dimension1',
                Eval('_parent_definition', {}).get('dimension_order1'),
                If(
                    Eval('type') == 'dimension2',
                    Eval('_parent_definition', {}).get('dimension_order2'),
                    If(
                        Eval('type') == 'dimension3',
                        Eval('_parent_definition', {}).get('dimension_order3'),
                        Eval('_parent_definition', {}).get(
                            'dimension_order4')))) == 'alpha')},
        depends=['type'])
    definition = fields.Many2One(
        'table', 'Definition',
        required=True, ondelete='CASCADE')
    type = fields.Selection(
        [
            ('dimension1', 'Dimension 1'),
            ('dimension2', 'Dimension 2'),
            ('dimension3', 'Dimension 3'),
            ('dimension4', 'Dimension 4'),
        ], 'Type', required=True)
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

        cls._order.insert(0, ('rec_name', 'ASC'))
        if not cls.rec_name.on_change_with:
            cls.rec_name.on_change_with = []
        for field in ('type', 'value', 'date', 'start', 'end', 'start_date',
                'end_date', '_parent_definition.dimension_kind1',
                '_parent_definition.dimension_kind2',
                '_parent_definition.dimension_kind3',
                '_parent_definition.dimension_kind4'):
            if field not in cls.rec_name.on_change_with:
                cls.rec_name.on_change_with.append(field)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        TableHandler = backend.get('TableHandler')

        super(TableDefinitionDimension, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        table.index_action(['definition', 'type'], 'add')

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
        return records

    @classmethod
    def write(cls, records, values):
        super(TableDefinitionDimension, cls).write(records, values)
        cls.clean_sequence(records)

    def on_change_with_rec_name(self):
        return self.get_rec_name([self], 'rec_name')[self.id]

    @classmethod
    def get_rec_name(cls, dimensions, name):
        pool = Pool()
        Lang = pool.get('ir.lang')

        lang, = Lang.search([('code', '=', Transaction().language)])
        names = {}
        for dimension in dimensions:
            kind = 'dimension_kind%s' % dimension.type[-1]
            names[dimension.id] = ''
            if getattr(dimension.definition, kind) == 'value':
                names[dimension.id] = dimension.value
            elif getattr(dimension.definition, kind) == 'date':
                if dimension.date:
                    names[dimension.id] = Lang.strftime(
                        dimension.date, lang.code, lang.date)
                else:
                    names[dimension.id] = str(dimension.id)
            elif getattr(dimension.definition, kind) == 'range':
                names[dimension.id] = '%s - %s' % (
                    dimension.start, dimension.end)
            elif getattr(dimension.definition, kind) == 'range-date':
                if dimension.start_date:
                    names[dimension.id] = '%s -' % (
                        Lang.strftime(
                            dimension.start_date, lang.code, lang.date))
                    if dimension.end_date:
                        names[dimension.id] += ' %s' % (
                            Lang.strftime(
                                dimension.end_date, lang.code, lang.date))
                elif dimension.end_date:
                    names[dimension.id] = '- %s' % (
                        Lang.strftime(
                            dimension.end_date, lang.code, lang.date))
            if (getattr(dimension.definition, kind)
                    and getattr(
                        dimension.definition, kind).startswith('range')):
                names[dimension.id] = '[%s[' % names[dimension.id]
        return names

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('value',) + tuple(clause[1:])]

    @staticmethod
    def order_rec_name(tables):
        table, _ = tables[None]
        return [
            table.sequence == None,
            table.sequence,
            table.value,
            table.date,
            table.start, table.end,
            table.start_date, table.end_date,
            ]


class TableCell(ModelSQL, ModelView):
    "Cell"
    __name__ = 'table.cell'
    definition = fields.Many2One(
        'table', 'Definition',
        required=True)
    dimension1 = fields.Many2One(
        'table.dimension.value',
        'Dimension 1', ondelete='CASCADE',
        domain=[
            ('definition', '=', Eval('definition')),
            ('type', '=', 'dimension1'),
        ],
        depends=['definition'])
    dimension2 = fields.Many2One(
        'table.dimension.value',
        'Dimension 2', ondelete='CASCADE',
        domain=[
            ('definition', '=', Eval('definition')),
            ('type', '=', 'dimension2'),
        ],
        depends=['definition'])
    dimension3 = fields.Many2One(
        'table.dimension.value',
        'Dimension 3', ondelete='CASCADE',
        domain=[
            ('definition', '=', Eval('definition')),
            ('type', '=', 'dimension3'),
        ],
        depends=['definition'])
    dimension4 = fields.Many2One(
        'table.dimension.value',
        'Dimension 4', ondelete='CASCADE',
        domain=[
            ('definition', '=', Eval('definition')),
            ('type', '=', 'dimension4'),
        ],
        depends=['definition'])
    value = fields.Char('Value')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        TableHandler = backend.get('TableHandler')

        super(TableCell, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        table.index_action(
            [
                'definition', 'dimension1', 'dimension2',
                'dimension3', 'dimension4'], 'add')

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


class TableOpen2DAskDimensions(ModelView):
    "Table Open 2D Ask Dimensions"
    __name__ = 'table.2d.open.ask_dimensions'
    definition = fields.Many2One(
        'table', 'Definition',
        readonly=True)
    dimension3 = fields.Many2One(
        'table.dimension.value',
        'Dimension 3',
        domain=[
            ('definition', '=', Eval('definition')),
            ('type', '=', 'dimension3'),
        ],
        states={
            'required': Eval('dimension3_required', False),
            'invisible': ~Eval('dimension3_required'),
        },
        depends=['definition', 'dimension3_required'])
    dimension3_required = fields.Boolean('Dimension 3 Required', readonly=True)
    dimension4 = fields.Many2One(
        'table.dimension.value',
        'Dimension 4',
        domain=[
            ('definition', '=', Eval('definition')),
            ('type', '=', 'dimension4'),
        ],
        states={
            'required': Eval('dimension4_required', False),
            'invisible': ~Eval('dimension4_required'),
        },
        depends=['definition', 'dimension4_required'])
    dimension4_required = fields.Boolean('Dimension 4 Required', readonly=True)

    @staticmethod
    def default_definition():
        return Transaction().context.get('active_id')

    @staticmethod
    def default_dimension_required(dimension):
        TableDefinition = Pool().get('table')
        definition_id = Transaction().context.get('active_id')
        if definition_id:
            definition = TableDefinition(definition_id)
            return bool(getattr(definition, 'dimension_kind%s' % dimension))
        return False

    @classmethod
    def default_dimension3_required(cls):
        return cls.default_dimension_required(3)

    @classmethod
    def default_dimension4_required(cls):
        return cls.default_dimension_required(4)

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
            view_fields['dimension3']['string'] = definition.dimension_name3
            view_fields['dimension4']['string'] = definition.dimension_name4
        return result


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
        if getattr(self.ask_dimensions, 'dimension3', None):
            context['dimension3'] = self.ask_dimensions.dimension3.id
        if getattr(self.ask_dimensions, 'dimension4', None):
            context['dimension4'] = self.ask_dimensions.dimension4.id
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
        definition_id = int(
            Transaction().context.get('table', -1))
        if definition_id != -1:
            definition = TableDefinition(definition_id)
            if (not definition.dimension_kind1
                    or not definition.dimension_kind2
                    or (definition.dimension_kind3
                        and not Transaction().context.get('dimension3'))
                    or (definition.dimension_kind4
                        and not Transaction().context.get('dimension4'))):
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
        for dimension_name in ('dimension3', 'dimension4'):
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
        for dimension in ('dimension3', 'dimension4'):
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
        super(Table2D, cls).write(rows, values)
        dim1_ids = [r.id for r in rows]
        definition_id = int(
            Transaction().context.get('table', -1))
        to_creates = []
        for col, value in values.iteritems():
            dim2_id = int(col[3:])
            cells = TableCell.search([
                    ('dimension1', 'in', dim1_ids),
                    ('dimension2', '=', dim2_id),
                    ('dimension3', '=',
                        Transaction().context.get('dimension3')),
                    ('dimension4', '=',
                        Transaction().context.get('dimension4')),
                    ('definition', '=', definition_id),
                ])
            if cells:
                TableCell.write(cells, {
                        'value': value,
                    })
            for dim1_id in (set(dim1_ids) -
                    set(i.dimension1.id for i in cells)):
                to_creates.append({
                        'definition': definition_id,
                        'dimension1': dim1_id,
                        'dimension2': dim2_id,
                        'dimension3': Transaction().context.get('dimension3'),
                        'dimension4': Transaction().context.get('dimension4'),
                        'value': value,
                    })
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


class ManageDimensionGeneric(Wizard):
    'Manage Dimension'

    start_state = 'dimension_management'
    dimension_management = StateView('table.manage_dimension.show.dimension',
        'table.dimension_displayer_view_form', [
            Button('Exit', 'end', 'tryton-cancel'),
            Button('Apply', 'apply_', 'tryton-ok', True),
            Button('View Data', 'view_data', 'tryton-find')])
    apply_ = StateTransition()
    next_dim = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ManageDimensionGeneric, cls).__setup__()
        cls._error_messages.update({
            'dangerous_change': 'The requested change might delete data.',
        })
        setattr(cls, 'view_data', StateAction('table.act_table_2d_open'))
        if int(cls.__name__[-1]) >= DIMENSION_MAX:
            return
        next_dim = int(cls.__name__[-1]) + 1
        setattr(cls, 'next_dim_action', StateAction(
                'table.act_manage_dimension_%s' % next_dim))
        # TODO : Find why this is needed (sometimes, the insert occurs twice)
        if 'Dimension %s' % next_dim in [x.string for x in
                cls.dimension_management.buttons]:
            return
        cls.dimension_management = copy.copy(cls.dimension_management)
        cls.dimension_management.buttons.insert(2, Button('Dimension %s' %
                    next_dim, 'next_dim', 'tryton-go-next'))

    def get_my_dimension(self):
        raise NotImplementedError

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

    def transition_next_dim(self):
        self.transition_apply_()
        return 'next_dim_action'

    def do_view_data(self, action):
        self.transition_apply_()
        table_id = Transaction().context.get('active_id')
        data = {
            'model': 'table',
            'id': table_id,
            'ids': [table_id],
            }
        return action, data

    def do_next_dim_action(self, action):
        table_id = Transaction().context.get('active_id')
        data = {
            'model': 'table',
            'id': table_id,
            'ids': [table_id],
            }
        return action, data


class ManageDimension1(ManageDimensionGeneric):
    'Manage Dimension 1'

    __name__ = 'table.manage_dimension.show_dimension_1'

    def get_my_dimension(self):
        return 1


class ManageDimension2(ManageDimensionGeneric):
    'Manage Dimension 2'

    __name__ = 'table.manage_dimension.show_dimension_2'

    def get_my_dimension(self):
        return 2


class ManageDimension3(ManageDimensionGeneric):
    'Manage Dimension 3'

    __name__ = 'table.manage_dimension.show_dimension_3'

    def get_my_dimension(self):
        return 3


class ManageDimension4(ManageDimensionGeneric):
    'Manage Dimension 4'

    __name__ = 'table.manage_dimension.show_dimension_4'

    def get_my_dimension(self):
        return 4


class TableCreation(Wizard):
    'Create New Table'

    __name__ = 'table.create'

    start_state = 'new_table'
    new_table = StateView('table', 'table.table_basic_data_view_form', [
            Button('Exit', 'end', 'tryton-cancel'),
            Button('Edit Dimension 1', 'edit_dim_1', 'tryton-go-next')])
    edit_dim_1 = StateTransition()
    launch_edition = StateAction('table.act_manage_dimension_1')

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
