import copy
from datetime import datetime
from decimal import Decimal

from trytond.config import CONFIG
from trytond.backend import TableHandler
from trytond.pool import Pool
from trytond.pyson import Eval, If, Bool, PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.modules.coop_utils.model import CoopSQL as ModelSQL
from trytond.modules.coop_utils.model import CoopView as ModelView
from trytond.modules.coop_utils import fields
from trytond.modules.coop_utils import coop_string

__all__ = [
    'TableCell', 'TableDefinition',
    'TableDefinitionDimension', 'TableOpen2DAskDimensions',
    'TableOpen2D', 'Table2D']

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


class TableDefinition(ModelSQL, ModelView):
    "Table Definition"

    __name__ = 'table.table_def'

    name = fields.Char('Name', required=True)
    code = fields.Char(
        'Code', required=True,
        on_change_with=['name', 'code'])
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
        'table.table_dimension', 'definition', 'Dimension 1',
        domain=[('type', '=', 'dimension1')],
        states={'invisible': ~Eval('dimension_kind1')},
        depends=['dimension_kind1'])
    dimension2 = fields.One2ManyDomain(
        'table.table_dimension', 'definition', 'Dimension 2',
        domain=[('type', '=', 'dimension2')],
        states={'invisible': ~Eval('dimension_kind2')},
        depends=['dimension_kind2'])
    dimension3 = fields.One2ManyDomain(
        'table.table_dimension', 'definition', 'Dimension 3',
        domain=[('type', '=', 'dimension3')],
        states={'invisible': ~Eval('dimension_kind3')},
        depends=['dimension_kind4'])
    dimension4 = fields.One2ManyDomain(
        'table.table_dimension', 'definition', 'Dimension 4',
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
    cells = fields.One2Many('table.table_cell', 'definition', 'Cells')

    @classmethod
    def __setup__(cls):
        super(TableDefinition, cls).__setup__()
        cls._sql_constraints = [
            ('name_unique', 'UNIQUE(name)',
                'The name of "Table Definition" must be unique'),
        ]
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(TableDefinition, cls).__register__(module_name)

        if not CONFIG['db_type'] == 'postgresql':
            return

        cursor = Transaction().cursor
        cursor.execute('CREATE EXTENSION IF NOT EXISTS tablefunc', ())

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
        TableDefinitionDimension = pool.get('table.table_dimension')
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
        for i in range(1, DIMENSION_MAX + 1):
            if getattr(self, 'dimension_kind%s' % i):
                nb_dim += 1
        if nb_dim == 1:
            return 'Index'
        elif nb_dim == 2:
            return 'Table'
        else:
            return 'Table %sD' % nb_dim

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


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

DIMENSION_DEPENDS = ['type']


class TableDefinitionDimension(ModelSQL, ModelView):
    "Table Definition Dimension"

    __name__ = 'table.table_dimension'
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
        'table.table_def', 'Definition',
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
        cls.rec_name.order_field = (
            "%(table)s.sequence IS NULL %(order)s, "
            "%(table)s.sequence %(order)s, "
            "%(table)s.value %(order)s, "
            "%(table)s.date %(order)s, "
            "%(table)s.start %(order)s, %(table)s.end %(order)s, "
            "%(table)s.start_date %(order)s, %(table)s.end_date %(order)s")
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

        super(TableDefinitionDimension, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        table.index_action(['definition', 'type'], 'add')

    @classmethod
    def _export_keys(cls):
        return set([
            'definition.code', 'type', 'date', 'start',
            'end', 'start_date', 'end_date', 'value'])

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


class TableCell(ModelSQL, ModelView):
    "Cell"
    __name__ = 'table.table_cell'
    definition = fields.Many2One(
        'table.table_def', 'Definition',
        required=True)
    dimension1 = fields.Many2One(
        'table.table_dimension',
        'Dimension 1', ondelete='CASCADE',
        domain=[
            ('definition', '=', Eval('definition')),
            ('type', '=', 'dimension1'),
        ],
        depends=['definition'])
    dimension2 = fields.Many2One(
        'table.table_dimension',
        'Dimension 2', ondelete='CASCADE',
        domain=[
            ('definition', '=', Eval('definition')),
            ('type', '=', 'dimension2'),
        ],
        depends=['definition'])
    dimension3 = fields.Many2One(
        'table.table_dimension',
        'Dimension 3', ondelete='CASCADE',
        domain=[
            ('definition', '=', Eval('definition')),
            ('type', '=', 'dimension3'),
        ],
        depends=['definition'])
    dimension4 = fields.Many2One(
        'table.table_dimension',
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

        super(TableCell, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        table.index_action(
            [
                'definition', 'dimension1', 'dimension2',
                'dimension3', 'dimension4'], 'add')

    @classmethod
    def _export_light(cls):
        return set([
            'definition', 'dimension1', 'dimension2', 'dimension3',
            'dimension4'])

    @classmethod
    def fields_get(cls, fields_names=None):
        pool = Pool()
        TableDefinition = pool.get('table.table_def')
        result = super(TableCell, cls).fields_get(fields_names=fields_names)
        if Transaction().context.get('table.table_def') and 'value' in result:
            table_definition = \
                TableDefinition(Transaction().context['table.table_def'])
            result['value']['type'] = table_definition.type_
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
        TableDefinition = pool.get('table.table_def')
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
        Definition = pool.get('table.table_def')
        Dimension = pool.get('table.table_dimension')

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
        'table.table_def', 'Definition',
        readonly=True)
    dimension3 = fields.Many2One(
        'table.table_dimension',
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
        'table.table_dimension',
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
        TableDefinition = Pool().get('table.table_def')
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


class TableOpen2D(Wizard):
    "Table Open 2D"
    __name__ = 'table.2d.open'
    start = StateTransition()
    ask_dimensions = StateView('table.2d.open.ask_dimensions',
        'table.table_2d_open_ask_dimensions_form_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', True),
            ])
    open_ = StateAction('table.act_table_2d_relate_form')

    def transition_start(self):
        TableDefinition = Pool().get('table.table_def')
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
            'table.table_def': Transaction().context['active_id'],
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
        TableCell = pool.get('table.table_cell')
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
            'table.table_dimension')
        definition_id = int(
            Transaction().context.get('table.table_def', -1))
        dimensions2 = TableDefinitionDimension.search([
                ('type', '=', 'dimension2'),
                ('definition', '=', definition_id),
                ])
        result = super(Table2DDict, self).keys()
        result += ['col%d' % d.id for d in dimensions2]
        return result


class Table2D(ModelSQL, ModelView):
    "Table 2D"
    __name__ = 'table.2d'

    row = fields.Many2One(
        'table.table_dimension', 'Row',
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
        pool = Pool()
        TableCell = pool.get('table.table_cell')
        TableDefinition = pool.get('table.table_def')
        TableDefinitionDimension = pool.get(
            'table.table_dimension')
        definition_id = int(
            Transaction().context.get('table.table_def', -1))
        if definition_id != -1:
            definition = TableDefinition(definition_id)
            if (not definition.dimension_kind1
                    or not definition.dimension_kind2
                    or (definition.dimension_kind3
                        and not Transaction().context.get('dimension3'))
                    or (definition.dimension_kind4
                        and not Transaction().context.get('dimension4'))):
                cls.raise_user_error('not_2d')
        dimensions2 = TableDefinitionDimension.search([
                ('type', '=', 'dimension2'),
                ('definition', '=', definition_id),
            ])
        cols = ', '.join('col%d VARCHAR' % d.id for d in dimensions2)
        if cols:
            cols = ', ' + cols
        dimensions_clause = ''
        dimensions_args = []
        for dimension in ('dimension3', 'dimension4'):
            if Transaction().context.get(dimension) is not None:
                dimensions_clause += 'AND i.%s= %%s ' % dimension
                dimensions_args.append(Transaction().context[dimension])
            else:
                dimensions_clause += 'AND i.%s IS NULL ' % dimension
        return ("SELECT *, id AS row, 0 AS create_uid, NULL AS write_uid, "
                " NOW() AS create_date, NULL AS write_date "
            "FROM CROSSTAB("
            "'SELECT d.id, i.dimension2, i.value "
            'FROM "' + TableDefinitionDimension._table + '" AS d '
            'LEFT JOIN "' + TableCell._table + '" AS i '
                "ON (d.id = i.dimension1 " + dimensions_clause + ") "
            + ("WHERE d.definition = %s " % definition_id)
                + "AND type = ''dimension1'' "
            "ORDER BY 1', "
            "'SELECT id "
            'FROM "' + TableDefinitionDimension._table + '" '
            "WHERE type = ''dimension2'' "
                + ("AND definition = %s " % definition_id)
            + " ORDER BY sequence IS NULL, sequence ASC, value ASC, "
                "date ASC, start ASC, \"end\" ASC, "
                "start_date ASC, end_date ASC') "
            "AS ct(id INTEGER" + cols + ")", dimensions_args)

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        pool = Pool()
        TableCell = pool.get('table.table_cell')
        TableDefinition = pool.get('table.table_def')
        TableDefinitionDimension = pool.get(
            'table.table_dimension')

        definition_id = int(
            Transaction().context.get('table.table_def', -1))
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
            'field_childs': False,
            'view_id': 0,
        }

    @classmethod
    def write(cls, rows, values):
        pool = Pool()
        TableCell = pool.get('table.table_cell')
        super(Table2D, cls).write(rows, values)
        dim1_ids = [r.id for r in rows]
        definition_id = int(
            Transaction().context.get('table.table_def', -1))
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
            for dim1_id in (set(dim1_ids) - set(i.id for i in cells)):
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
        TableDefinition = pool.get('table.table_def')
        TableCell = pool.get('table.table_cell')
        result = super(Table2D, cls).read(ids, fields_names=fields_names)
        definition_id = int(
            Transaction().context.get('table.table_def', -1))
        definition = TableDefinition(definition_id)
        for value in result:
            for field in value:
                if field.startswith('col'):
                    value[field] = TableCell._load_value(value[field],
                        definition.type_)
        return result
