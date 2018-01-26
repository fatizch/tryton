# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.pool import PoolMeta, Pool

MODULE_NAME = 'table'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def create_table_from_filename(cls, filename):
        # Remove leading table_
        filename = filename[6:]
        # Remove file extension
        filename = filename.split('.')[0]
        Table = Pool().get('table')
        Dimension = Pool().get('table.dimension.value')
        Cell = Pool().get('table.cell')
        if ';' in filename:
            code, name, kind = filename.split(';')
        else:
            name, code, kind = filename, '', 'char'
        code = code.strip()
        name = name.strip()
        existing = Table.search([('code', '=', code)])
        if existing:
            # Delete existing data before update
            Cell.delete(Cell.search([('definition', '=', existing[0].id)]))
            Dimension.delete(Dimension.search([
                        ('definition', '=', existing[0].id)]))
            return existing[0]
        table = Table()
        table.code = code
        table.name = name
        table.type_ = kind
        return table

    @classmethod
    def set_dimensions_from_first_cell(cls, first_cell, table):
        dims = first_cell.split('|')
        for idx in range(len(dims)):
            name, kind = dims[idx].split('[')
            kind = kind[:-1]
            setattr(table, 'dimension_name%s' % str(idx + 1), name)
            setattr(table, 'dimension_kind%s' % str(idx + 1), kind)
            setattr(table, 'dimension_order%s' % str(idx + 1), 'sequence')

    @classmethod
    def create_nth_dimension(cls, table, values, n):
        Configuration = cls.get_instance()
        Dimension = Pool().get('table.dimension.value')
        dimensions = []
        for idx, elem in enumerate(values):
            res = Dimension()
            res.type = 'dimension%s' % n
            if getattr(table, 'dimension_kind%s' % n) == 'value':
                res.value = u'%s' % elem
            if getattr(table, 'dimension_kind%s' % n) == 'date':
                res.date = elem
            if getattr(table, 'dimension_kind%s' % n) == 'range':
                res.start = Decimal(elem)
                res.end = (Decimal(values[idx + 1]) if idx < len(values) - 1
                    else None)
            if getattr(table, 'dimension_kind%s' % n) == 'range-date':
                res.start_date = datetime.datetime.strptime(elem,
                    Configuration.language.date).date()
                res.end_date = (datetime.datetime.strptime(values[idx + 1],
                    Configuration.language.date).date()
                    if idx < len(values) - 1 else None)
            res.sequence = idx
            res.definition = table
            res.save()
            dimensions.append(res)
        setattr(table, 'dimension%s' % n, dimensions)

    @classmethod
    def load_table_from_file(cls, filename):
        Cell = Pool().get('table.cell')
        the_file = cls._loaded_resources[MODULE_NAME]['files'][filename]
        table = cls.create_table_from_filename(filename)
        cls.set_dimensions_from_first_cell(the_file[0][0], table)
        # Table must be saved as transactional mixing of table / dims / cells
        # does not work properly
        table.save()
        cls.create_nth_dimension(table, [x[0] for x in the_file[1:]], 1)
        if len(the_file[0]) > 2:
            cls.create_nth_dimension(table, the_file[0][1:], 2)
        for idx, line in enumerate(the_file[1:], start=0):
            for jdx, value in enumerate(line[1:], start=0):
                cell = Cell()
                cell.dimension1 = table.dimension1[idx]
                if len(the_file[0]) > 2:
                    cell.dimension2 = table.dimension2[jdx]
                if table.type_ == 'numeric':
                    cell.value = '.'.join(value.split(','))
                else:
                    cell.value = value
                cell.definition = table
                cell.save()

    @classmethod
    def table_test_case(cls):
        cls.load_resources(MODULE_NAME)
        for file_name in cls._loaded_resources[MODULE_NAME]['files']:
            if file_name.startswith('table_'):
                cls.read_csv_file(file_name, MODULE_NAME)
                cls.load_table_from_file(file_name)

    @classmethod
    def table_test_case_test_method(cls):
        return True
