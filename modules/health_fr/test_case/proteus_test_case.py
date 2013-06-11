import os
import csv

from proteus import Model
try:
    import proteus_tools
except:
    pass


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['ExpenseKind'] = Model.get('ins_product.expense_kind')
    cfg_dict['Regime'] = Model.get('health.regime')
    cfg_dict['InsuranceFund'] = Model.get('health.insurance_fund')


def load_insurance_fund_addresses(cfg_dict, file_name):
    path = os.path.join(cfg_dict['dir_loc'], file_name)
    reader = csv.DictReader(open(path, 'rb'), delimiter=';')
    addresses = {}
    for data in reader:
        addresses[data['ID_ADR']] = data
    return addresses


def update_insurance_funds(cfg_dict, funds):
    addresses = load_insurance_fund_addresses(cfg_dict,
        'caisse_affiliation_adresse.csv')
    for fund_dict, fund_obj in funds:

        regime = proteus_tools.get_objects_from_db(cfg_dict, 'Regime', 'code',
            fund_dict['regime_code'].zfill(2))
        fund_obj.regime = regime
        if fund_dict['ID_ADR'] in addresses:
            address_dict = addresses[fund_dict['ID_ADR']]
            cp = address_dict['Code Postal']
            if cp[0:2] in ['97', '98']:
                fund_obj.department = cp[0:3]
            else:
                fund_obj.department = cp[0:2]
        fund_obj.save()


def launch_test_case(cfg_dict):
    update_cfg_dict_with_models(cfg_dict)
    proteus_tools.import_file(cfg_dict, 'expense_kind.csv', 'ExpenseKind',
        'code')
    proteus_tools.import_file(cfg_dict, 'regime.csv', 'Regime', 'code')
    update_insurance_funds(cfg_dict, proteus_tools.import_file(cfg_dict,
            'caisse_affiliation.csv', 'InsuranceFund', 'code'))
