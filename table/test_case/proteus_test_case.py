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


def get_or_create_table(cfg_dict, name, dim1_kind, dim1,
        dim2_kind=None, dim2=None,
        dim3_kind=None, dim3=None,
        dim4_kind=None, dim4=None):

    Table = cfg_dict['Table']
    res = get_object_from_db(Table, 'name', name)
    if res:
        return res
    res = Table()
    res.name = name
    res.dimension_kind1 = dim1_kind
    for i in dim1:
        res.dimension1.append(create_dim_value(cfg_dict, 1, i))
    if dim2_kind:
        res.dimension_kind2 = dim2_kind
        for i in dim2:
            res.dimension2.append(create_dim_value(cfg_dict, 2, i))
    if dim3_kind:
        res.dimension_kind3 = dim3_kind
        for i in dim3:
            res.dimension2.append(create_dim_value(cfg_dict, 3, i))
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
    table = get_or_create_table(cfg_dict, 'Table 10x100', 'value', range(100),
    'value', range(10))
    if table.id > 0:
        return table
    table.save()
    for dim1 in table.dimension1:
        for dim2 in table.dimension2:
            create_cell(cfg_dict, table, random.random() * 100, dim1, dim2)


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


def load_table_from_csv(cfg_dict):
    for cur_file in glob.glob(
            os.path.join(DIR, cfg_dict['language'][0:2].lower(), '*.csv')):
        name = os.path.splitext(os.path.basename(cur_file))[0]
        Table = cfg_dict['Table']
        Cell = cfg_dict['Cell']
        if get_object_from_db(Table, 'name', name):
            continue
        reader = csv.reader(open(cur_file, 'rb'), delimiter=';')
        line = 0
        table = Table()
        table.name = name
        table.save()
        for cur_line in reader:
            if len(cur_line) == 0:
                continue
            line += 1
            if line == 1:
                nb_dim = 2 if len(cur_line) > 2 else 1
                if nb_dim == 2:
                    dim2_values = cur_line[1:]
                    table.dimension_kind2 = get_dimension_kind(dim2_values[0])
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
                    cell.value = cur_line[j]
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


def create_objects(cfg_dict):
    create_table_10_100(cfg_dict)
    load_table_from_csv(cfg_dict)


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict_with_models(cfg_dict)
    create_objects(cfg_dict)
