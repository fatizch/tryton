# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
from decimal import Decimal

from trytond.pool import Pool
from trytond.model import ModelSingleton
from trytond.protocols.jsonrpc import JSONEncoder, JSONDecoder

from trytond.modules.coog_core import model, fields

__all__ = [
    'CommutationManager',
    'CommutationManagerLine',
    ]

FREQUENCIES = [
    ('12', 'Monthly'),
    ('4', 'Quarterly'),
    ('2', 'Half yearly'),
    ('1', 'Yearly'),
    ]


class CommutationManager(ModelSingleton, model.CoogSQL, model.CoogView):
    'Commutation Manager'
    __name__ = 'table.commutation_manager'

    lines = fields.One2Many('table.commutation_manager.line', 'manager',
        'Lines', delete_missing=True)

    @classmethod
    def get_life_commutation(cls, table_code, rate, frequency, age):
        Cell = Pool().get('table.cell')
        table = cls.find_table(table_code, rate, frequency)
        return json.loads(Cell.get(table, age), object_hook=JSONDecoder())

    @classmethod
    def find_table(cls, base_code, rate, frequency):
        manager = cls.get_singleton()
        if not manager:
            return None
        for line in manager.lines:
            if line.base_table.code != base_code:
                continue
            if line.rate != rate:
                continue
            if line.frequency != frequency:
                continue
            return line.data_table


class CommutationManagerLine(model.CoogSQL, model.CoogView):
    'Commutation Manager Line'
    __name__ = 'table.commutation_manager.line'

    manager = fields.Many2One('table.commutation_manager', 'Manager',
        required=True, ondelete='CASCADE', select=True)
    base_table = fields.Many2One('table', 'Base table', required=True,
        ondelete='RESTRICT')
    data_table = fields.Many2One('table', 'Target table', ondelete='RESTRICT',
        readonly=True)
    rate = fields.Numeric('Rate', digits=(6, 4), required=True)
    frequency = fields.Selection(FREQUENCIES, 'Frequency', required=True)

    @classmethod
    def __setup__(cls):
        super(CommutationManagerLine, cls).__setup__()
        cls._buttons.update({
                'refresh': {},
                })

    @classmethod
    def create(cls, vlist):
        lines = super(CommutationManagerLine, cls).create(vlist)
        cls.refresh(lines)
        return lines

    @classmethod
    def delete(cls, lines):
        data_tables = [(x, x.data_table) for x in lines if x.data_table]
        if data_tables:
            cls.write([x[0] for x in data_tables], {'data_table': None})
            Pool().get('table').delete([x[1] for x in data_tables])
        super(CommutationManagerLine, cls).delete(lines)

    @classmethod
    @model.CoogView.button
    def refresh(cls, lines):
        tables = []
        for line in lines:
            if line.data_table:
                tables.append(line.data_table)
                line.data_table = None
        if tables:
            cls.save(lines)
            Pool().get('table').delete(tables)
        for line in lines:
            line.create_data_table()
        cls.save(lines)

    def create_data_table(self):
        Table = Pool().get('table')
        sub_table, = Table.search([('code', '=', self.base_table.code)])
        code = 'commutation_%s_%.2f_%s' % (self.base_table.code,
            self.rate * 100, self.frequency)
        name = 'Commutation %s (%.2f%%) %s' % (self.base_table.code,
            self.rate * 100, self.frequency)
        table = Table()
        table.code = code
        table.name = name
        table.type_ = 'char'
        table.dimension_kind1 = 'value'
        table.dimension_name1 = 'Age'
        table.dimension1 = [{
                'type': 'dimension1',
                'value': x.value}
            for x in sub_table.dimension1]
        table.save()
        self.data_table = table
        self._populate_life_commutation_table()
        self.data_table.save()

    def _populate_life_commutation_table(self):
        # Algorithm : cf https://en.wikipedia.org/wiki/Actuarial_notation
        Dimension = Pool().get('table.dimension.value')
        k = (Decimal(self.frequency) - 1) / (2 * Decimal(self.frequency))
        size = len(self.data_table.dimension1)
        vals = {x: [Decimal(0) for y in range(size + 1)]
            for x in ['lx', 'dx', 'qx', 'px', 'vx', 'Dx', 'Cx', 'Mx', 'Nx',
                'Rx', 'Ax', 'a"x', 'ax']}
        for cell in self.base_table.cells:
            vals['lx'][int(cell.dimension1.value)] = cell._load_value(
                cell.value, self.base_table.type_)

        for i in range(size):
            vals['dx'][i] = vals['lx'][i] - vals['lx'][i + 1]
            vals['qx'][i] = vals['dx'][i] / vals['lx'][i] \
                if vals['lx'] != 0 else 0
            vals['px'][i] = 1 - vals['qx'][i]
            vals['vx'][i] = (1 / (1 + self.rate)) ** i
            vals['Dx'][i] = vals['lx'][i] * vals['vx'][i]
            vals['Cx'][i] = vals['vx'][i] * vals['dx'][i] / (
                1 + self.rate) ** Decimal('0.5')

        cur_m, cur_n = 0, 0
        for i in reversed(range(size)):
            cur_m += vals['Cx'][i]
            vals['Mx'][i] = cur_m
            cur_n += vals['Dx'][i]
            vals['Nx'][i] = cur_n
            vals['Ax'][i] = vals['Mx'][i] / vals['Dx'][i] \
                if vals['Dx'][i] else 0
            vals['a"x'][i] = (vals['Nx'][i] / vals['Dx'][i]
                if vals['Dx'][i] else 0) + k
            vals['ax'][i] = (vals['Nx'][i + 1] / vals['Dx'][i]
                if vals['Dx'][i] else 0) + k

        cur_r = 0
        for i in reversed(range(size)):
            cur_r += vals['Mx'][i]
            vals['Rx'][i] = cur_r

        self.data_table.cells = [{
                'dimension1': Dimension.get_dimension_ids(self.data_table, 0,
                    str(i))[0],
                'value': json.dumps({
                        'dx': vals['dx'][i],
                        'qx': vals['qx'][i],
                        'px': vals['px'][i],
                        'vx': vals['vx'][i],
                        'Dx': vals['Dx'][i],
                        'Cx': vals['Cx'][i],
                        'Mx': vals['Mx'][i],
                        'Nx': vals['Nx'][i],
                        'Rx': vals['Rx'][i],
                        'Ax': vals['Ax'][i],
                        'a"x': vals['a"x'][i],
                        'ax': vals['ax'][i],
                        }, cls=JSONEncoder)}
            for i in range(size)]
