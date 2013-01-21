#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import glob
import random
import csv
import datetime

from proteus import Model
DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['Table'] = Model.get('table.table_def')
    cfg_dict['Dimension'] = Model.get('table.table_dimension')
    cfg_dict['Cell'] = Model.get('table.table_cell')
    return cfg_dict


def convert_date(cfg_dict, value):
    if cfg_dict['language'] == 'fr_FR':
        formating = '%d/%m/%Y'
    else:
        formating = '%m/%d/%Y'
    return datetime.datetime.strptime(value, formating)


def create_dim_value(cfg_dict, dim_number, value, kind='value', end=None):

    res = cfg_dict['Dimension']()
    res.type = 'dimension%s' % dim_number
    if kind == 'value':
        res.value = u'%s' % value
    if kind == 'date':
        res.date = value
    if kind == 'range':
        res.start = float(value)
        res.end = float(end) if end else None
    if kind == 'range-date':
        res.start_date = convert_date(cfg_dict, value)
        res.end_date = convert_date(cfg_dict, end) if end else None
    return res


def get_or_create_table(cfg_dict, name, kind, dim_dict, code=None):

    Table = cfg_dict['Table']
    res = get_object_from_db(Table, 'name', name)
    if res:
        return res
    res = Table()
    res.name = name
    res.type_ = kind
    if code:
        res.code = code
    for i in range(1, 5):
        kind, name, values = dim_dict.get(str(i), (None, None, None))
        if not kind:
            continue
        setattr(res, 'dimension_kind%s' % i, kind)
        setattr(res, 'dimension_name%s' % i, name)
        n = len(values)
        for j in range(n):
            end = None
            if kind.startswith('range'):
                end = values[j + 1] if j < n - 1 else None
            getattr(res, 'dimension%s' % i).append(create_dim_value(cfg_dict,
                    i, values[j], kind, end))
    return res


def create_cell(cfg_dict, table, value, dim1, dim2=None, dim3=None):
    res = cfg_dict['Cell']()
    res.definition = table
    res.dimension1 = dim1
    res.dimension2 = dim2
    res.dimension3 = dim3
    res.value = str(value)
    res.save()
    return res


def get_object_from_db(model, var_name, value):
    instances = model.find([(var_name, '=', value)], limit=1)
    if len(instances) > 0:
        return instances[0]


def create_table_10_100(cfg_dict):
    table = get_or_create_table(cfg_dict, 'Table 10x100', 'numeric', 
        {
            '1': ('value', '100', range(100)),
            '2': ('value', '10', range(10))
        },
        'Table_10_100')
    if table.id > 0:
        return table
    table.save()
    for dim1 in table.dimension1:
        for dim2 in table.dimension2:
            create_cell(cfg_dict, table, random.random() * 100, dim1, dim2)


def create_table_cotisation(cfg_dict):
    table = get_or_create_table(cfg_dict, 'Cotisation Retraite', 'numeric',
        {
            '1': ('value', 'Régime', ['Arrco', 'Agirc', 'AGFF', 'CET']),
            '2': ('value', 'Tranche', ['Tranche 1', 'Tranche 2', 'Tranche A',
                'Tranche B', 'Tranche C']),
            '3': ('value', 'Cadre ?', ['cadre', 'non cadre']),
            '4': ('range-date', 'Date', ['01/01/2012'])
        },
        )
    if table.id > 0:
        return table
    table.save()
    dims = []
    for i in range(1, 4):
        dim_dict = {}
        dims.append(dim_dict)
        for dim in getattr(table, 'dimension%s' % i):
            dim_dict[dim.value] = dim
    dims.append({'dim4': table.dimension4[0]})

    def create_cell(Cell, table, dims, dimensions, value):
        res = Cell()
        res.definition = table
        for i in range(len(dimensions)):
            setattr(res, 'dimension%s' % int(i + 1), dims[i][dimensions[i]])
        res.value = str(float(value) / 100)
        res.save()

    Cell = cfg_dict['Cell']
    create_cell(Cell, table, dims, ['Arrco', 'Tranche 1', 'non cadre', 'dim4'],
        7.5)
    create_cell(Cell, table, dims, ['Arrco', 'Tranche 2', 'non cadre', 'dim4'],
        20)
    create_cell(Cell, table, dims, ['AGFF', 'Tranche 1', 'non cadre', 'dim4'],
        2)
    create_cell(Cell, table, dims, ['AGFF', 'Tranche 2', 'non cadre', 'dim4'],
        2.2)
    create_cell(Cell, table, dims, ['Arrco', 'Tranche 1', 'cadre', 'dim4'],
        7.5)
    create_cell(Cell, table, dims, ['Agirc', 'Tranche B', 'cadre', 'dim4'],
        20.3)
    create_cell(Cell, table, dims, ['Agirc', 'Tranche C', 'cadre', 'dim4'],
        20.3)
    create_cell(Cell, table, dims, ['CET', 'Tranche 1', 'cadre', 'dim4'],
        0.35)
    create_cell(Cell, table, dims, ['CET', 'Tranche B', 'cadre', 'dim4'],
        0.35)
    create_cell(Cell, table, dims, ['CET', 'Tranche C', 'cadre', 'dim4'],
        0.35)
    create_cell(Cell, table, dims, ['AGFF', 'Tranche 1', 'cadre', 'dim4'],
        2)
    create_cell(Cell, table, dims, ['AGFF', 'Tranche B', 'cadre', 'dim4'],
        2.2)


def get_dimension_kind(value):
    res = 'value'
    try:
        i = float(value)
    except ValueError, TypeError:
        pass
    else:
        return 'range'
    if '/' in value:
        return 'range-date'
    return res


def create_dims(table, first_cell):
    dims = first_cell.split('|')
    for idx in range(len(dims)):
        name, kind = dims[idx].split('[')
        kind = kind[:-1]
        setattr(table, 'dimension_name%s' % str(idx + 1), name)
        setattr(table, 'dimension_kind%s' % str(idx + 1), kind)

    table.save()


def load_table_from_csv(cfg_dict, path, file_name):
    Table = cfg_dict['Table']
    if ';' in file_name:
        (code, name, kind) = file_name.split(';')
    else:
        name = file_name
        code = ''
        kind = 'char'
    code = code.strip()
    name = name.strip()
    if get_object_from_db(Table, 'name', name):
        return
    reader = csv.reader(open(path, 'rb'), delimiter=';')
    line = 0
    table = Table()
    table.code = code
    table.name = name
    table.type_ = kind
    table.save()
    Cell = cfg_dict['Cell']
    for cur_line in reader:
        if len(cur_line) == 0:
            continue
        line += 1
        if line == 1:
            nb_dim = 2 if len(cur_line) > 2 else 1
            create_dims(table, cur_line[0])
            if nb_dim == 2:
                dim2_values = cur_line[1:]
                for val in dim2_values:
                    dim2 = create_dim_value(
                            cfg_dict, 2, val, table.dimension_kind2)
                    table.dimension2.append(dim2)
                    table.save()
            continue
        if line == 2:
            table.dimension_kind1 = get_dimension_kind(cur_line[0])
        table.dimension1.append(create_dim_value(
                cfg_dict, 1, cur_line[0], table.dimension_kind1))
        table.save()
        dim1 = table.dimension1[-1]

        cell = Cell()
        cell.definition = table
        cell.dimension1 = dim1
        if kind == 'numeric':
            cell.value = '.'.join(cur_line[1].split(','))
        else:
            cell.value = cur_line[1]
        if nb_dim == 2:
            j = 0
            for dim2 in table.dimension2:
                j += 1
                if j == 1:
                    cell.dimension2 = dim2
                    cell.save()
                    continue
                cell = Cell()
                cell.definition = table
                cell.dimension1 = dim1
                cell.dimension2 = dim2
                if kind == 'numeric':
                    cell.value = '.'.join(cur_line[j].split(','))
                else:
                    cell.value = cur_line[j]
                cell.save()
        else:
            cell.save()

    #Setting end value for range kind
    for dim_nb in range(1, 5):
        dimensions = getattr(table, 'dimension%s' % dim_nb)
        n = len(dimensions)
        dim_kind = getattr(table, 'dimension_kind%s' % dim_nb)
        if not dim_kind or not dim_kind.startswith('range'):
            continue
        for i in range(n - 1):
            ext = ''
            if dim_kind == 'range-date':
                ext = '_date'
            end = getattr(dimensions[i + 1], 'start' + ext)
            setattr(dimensions[i], 'end' + ext, end)
    table.save()


def load_tables_from_csv(cfg_dict):
    for cur_file in glob.glob(
            os.path.join(DIR, cfg_dict['language'][0:2].lower(), '*.csv')):
        name = os.path.splitext(os.path.basename(cur_file))[0]
        try:
            load_table_from_csv(cfg_dict, cur_file, name)
        except:
            print 'Impossible to load file %s' % cur_file
            raise


def create_objects(cfg_dict):
    create_table_10_100(cfg_dict)
    load_tables_from_csv(cfg_dict)
    create_table_cotisation(cfg_dict)


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict_with_models(cfg_dict)
    create_objects(cfg_dict)
