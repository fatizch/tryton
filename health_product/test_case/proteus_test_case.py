import os
import csv

from proteus import Model
try:
    import proteus_tools
except:
    pass


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['ExpenseKind'] = Model.get('ins_product.expense_kind')


def get_or_create_objects(cfg_dict, cur_line, header):
    data = {}
    n = 0
    for key in header:
        if not key:
            continue
        data[key] = cur_line[n].decode('latin-1')
        n += 1
    proteus_tools.get_or_create_this(
        data, {}, cfg_dict, 'ExpenseKind', 'code')


def create_objects(cfg_dict, name):
    path = os.path.join(cfg_dict['dir_loc'], name + '.csv')
    reader = csv.reader(open(path, 'rb'), delimiter=';')
    n = 0
    for cur_line in reader:
        if n == 0:
            header = cur_line
        else:
            get_or_create_objects(cfg_dict, cur_line, header)
        n += 1

    print 'Successfully created %s %s' % (n, name)


def launch_test_case(cfg_dict):
    update_cfg_dict_with_models(cfg_dict)
    create_objects(cfg_dict, 'expense_kind')
