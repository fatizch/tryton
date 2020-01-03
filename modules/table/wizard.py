# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from lxml import etree
from decimal import Decimal

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.modules.coog_core import model, fields
from .table import DIMENSION_MAX

__all__ = [
    'Import2DTable',
    'Import2DTableParam',
    ]


class Import2DTable(Wizard):
    'Import'

    __name__ = 'table.2d.import'

    start_state = 'param'
    param = StateView('table.2d.import.param',
        'table.table_2d_import_param_wiev_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Import', 'import_', 'tryton-go-next', default=True)])
    import_ = StateTransition()

    def default_param(self, name):
        assert Transaction().context.get('active_model') == 'table'
        return {
            'table': Transaction().context.get('active_id'),
            }

    def get_field_name(self, type_index, start=True):
        kind = getattr(self.param.table, 'dimension_kind%s' % type_index)
        if kind == 'range':
            return 'start' if start else 'end'
        elif kind == 'range-date':
            return 'start_date' if start else 'end_date'
        elif start:
            return kind

    def update_dimension_value(self, dim_value, value, type_index, start=True):
        field_name = self.get_field_name(type_index, start)
        if not field_name:
            return
        prev_value = getattr(dim_value, field_name, None)
        setattr(dim_value, field_name, value)
        new_value = getattr(dim_value, field_name)
        if prev_value != new_value:
            dim_value.save()

    def get_dimension_value(self, indexed_cache, valued_cache, index, value,
            type_index):
        if index not in indexed_cache:
            field_name = self.get_field_name(type_index)
            for key, dim_value in valued_cache.items():
                if key == value or (field_name == 'start'
                        and Decimal(key) == Decimal(value)):
                    break
            else:
                dim_value = Pool().get('table.dimension.value')(
                    definition=self.param.table,
                    type='dimension%s' % type_index)
                self.update_dimension_value(dim_value, value, type_index, True)
            indexed_cache[index] = dim_value
        return indexed_cache, indexed_cache[index]

    def load_dimension_values(self, type_index):
        valued_cache = {}
        for dimension_value in Pool().get('table.dimension.value').search([
                    ('definition', '=', self.param.table),
                    ('type', '=', 'dimension%s' % type_index)]):
            field_name = self.get_field_name(type_index)
            valued_cache[getattr(dimension_value, field_name)] = dimension_value
        return valued_cache

    def transition_import_(self):
        Cell = Pool().get('table.cell')
        i, j = 0, 0
        x, y, previous_x, previous_y = None, None, None, None
        idx_col_values, idx_lines_values = {}, {}
        val_col_values = self.load_dimension_values(self.param.col_dimension)
        val_lines_values = self.load_dimension_values(self.param.line_dimension)
        to_create = []
        for line in self.param.data.split('\n'):
            for cell_value in line.split('\t'):
                cell_value = cell_value.strip().replace('\r', '')
                if (i == 0 and j == 0) or not cell_value:
                    # First line and first colunm should not contain any info
                    pass
                elif j == 0 and self.param.col_dimension:
                    # First line should contains dimension 1 values
                    if x is not None:
                        previous_x = x
                    idx_col_values, x = self.get_dimension_value(idx_col_values,
                        val_col_values, i, cell_value, self.param.col_dimension)
                    if previous_x:
                        self.update_dimension_value(previous_x, cell_value,
                            self.param.col_dimension, False)
                elif i == 0 and self.param.line_dimension:
                    # First column should contains dimension 2 values
                    if y is not None:
                        previous_y = y
                    idx_lines_values, y = self.get_dimension_value(
                        idx_lines_values, val_lines_values, j, cell_value,
                        self.param.line_dimension)
                    if previous_y:
                        self.update_dimension_value(previous_y, cell_value,
                            self.param.line_dimension, False)
                elif i > 0 and j > 0:
                    cell = {
                        'definition': self.param.table,
                        'value': cell_value.replace(',', '.'),
                        }
                    if self.param.col_dimension:
                        cell['dimension%s' % self.param.col_dimension] = \
                            idx_col_values[i]
                    if self.param.line_dimension:
                        cell['dimension%s' % self.param.line_dimension] = \
                            idx_lines_values[j]
                    for k in range(1, DIMENSION_MAX + 1):
                        if k in(self.param.col_dimension,
                                self.param.line_dimension):
                            continue
                        dimension_value = getattr(self.param,
                            'fixed_dimension%s' % k)
                        if dimension_value:
                            cell[dimension_value.type] = dimension_value
                    to_create.append(cell)
                i += 1
            i = 0
            j += 1
        if to_create:
            Cell.create(to_create)
        return 'end'


class Import2DTableParam(model.CoogView):
    'Parameters'

    __name__ = 'table.2d.import.param'

    table = fields.Many2One('table', 'Table', required=True)
    col_dimension = fields.Selection('get_possible_dimension', 'Column',
        sort=False)
    line_dimension = fields.Selection('get_possible_dimension', 'Line',
        sort=False)
    data = fields.Text('Data', required=True, help="Copy/Paste from Excel")

    @fields.depends('table')
    def get_possible_dimension(self):
        if not self.table:
            return [('', '')]
        selection = []
        for i in range(1, DIMENSION_MAX + 1):
            if getattr(self.table, 'dimension_kind%s' % i):
                selection.append(('%s' % i,
                        getattr(self.table, 'dimension_name%s' % i)))
        return selection

    @classmethod
    def _view_look_dom_arch(cls, tree, type, field_children=None):
        if tree.tag == 'form':
            result = tree.xpath("//field[@name='fixed_dimensions']")
            if result:
                dimensions, = result
                for i in range(1, DIMENSION_MAX + 1):
                    group = etree.Element('group')
                    group.set('id', 'fixed_dim%s' % i)
                    group.set('colspan', '2')
                    group.set('col', '2')
                    group.set('yfill', '1')
                    group.set('yexpand', '1')
                    label_kind = etree.Element('label')
                    label_kind.set('name', 'fixed_dimension%s' % i)
                    group.append(label_kind)
                    field_kind = etree.Element('field')
                    field_kind.set('name', 'fixed_dimension%s' % i)
                    group.append(field_kind)
                    dimensions.addprevious(group)
                dimensions.getparent().remove(dimensions)
        return super(Import2DTableParam, cls)._view_look_dom_arch(tree,
            type, field_children=field_children)


for i in range(1, DIMENSION_MAX + 1):
    setattr(Import2DTableParam, 'fixed_dimension%s' % i,
        fields.Many2One('table.dimension.value', 'Fixed Dimension %s' % i,
            domain=[('definition', '=', Eval('table')),
                ('type', '=', 'dimension%s' % i)], depends=['table']))
