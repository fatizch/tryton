import re
import os
import random
import warnings

from proteus import Model

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def get_models():
    res = {}
    res['Bank'] = Model.get('party.bank')
    res['Address'] = Model.get('party.address')
    res['Country'] = Model.get('country.country')
    res['Party'] = Model.get('party.party')
    res['BankAccount'] = Model.get('party.bank_account')
    res['BankAccountNumber'] = Model.get('party.bank_account_number')
    res['Company'] = Model.get('company.company')
    return res


def launch_test_case(cfg_dict):
    models = get_models()

    if is_table_empty(models['Bank']):
        create_bank(cfg_dict, models)
    create_bank_accounts(cfg_dict, models)


def is_table_empty(model):
    return len(model.find(limit=1)) == 0


def create_bank(cfg_dict, models):
    f = open(os.path.join(DIR, 'bank.cfg'), 'r')
    countries = {}
    n = 0
    for line in f:
        try:
            bank = models['Bank']()
            company = models['Company']()
            if bank.company is None:
                bank.company = []
            bank.company.append(company)
            bank.name = line[11:51].strip()
            bank.code = line[51:61].strip()
            add_address(models, line, bank, countries)
            add_bank_info(line, bank)
            bank.save()
            n += 1
        except:
            warnings.warn('Impossible to create bank %s' % line[11:51].strip(),
                stacklevel=2)
    f.close()
    if n > 0:
        print 'Successfully imported %s banks' % n


def check_pattern(s, pattern):
    if s is not None:
        s = s.strip()
        matchObj = re.match(pattern, s)
        if matchObj:
            return matchObj.group()
        return False


def get_country(models, country_code, countries):
    if country_code in countries.keys():
        return countries[country_code]
    Country = models['Country']
    country, = Country.find(
        [('code', '=', country_code.upper())],
        limit=1)
    countries[country_code] = country
    return country


def add_address(models, line, bank, countries):
    address = bank.addresses[0]
    address.line1 = line[11:49].strip()
    address.line3 = line[88:120].strip()
    address.street = line[120:152].strip().upper()
    address.streetbis = line[152:184].strip().upper()
    address.zip = line[184:189].strip().upper()
    address.city = line[190:216].strip().upper()
    country_code = check_pattern(line[240:242], r'^[A-Z]{2}')
    if country_code:
        address.country = get_country(models, country_code, countries)


def add_bank_info(line, bank):
    bic = check_pattern(line[236:247], r'^[0-9A-Z]{8,11}')
    if bic:
        bank.bic = bic
    bank.bank_code = line[0:5]


def create_bank_accounts(cfg_dict, models):
    banks = load_bank_code(cfg_dict)
    Party = models['Party']
    n = 0
    for party in Party.find([('bank_accounts', '=', None)]):
        try:
            add_bank_account(models, party, banks)
            party.save()
            n += 1
        except:
            warnings.warn('Impossible to create bank account for %s'
                % party.name, stacklevel=2)
    if n > 0:
        print 'Successfully created %s bank accounts' % n


def get_random(the_dict):
    return u'%s' % the_dict.get(random.randint(0, len(the_dict) - 1))


def add_bank_account(models, party, banks):
    bank_account = models['BankAccount']()
    if party.bank_accounts is None:
        party.bank_accounts = []
    party.bank_accounts.append(bank_account)
    bank_account_nb = bank_account.account_numbers[0]
    bank_account_nb.kind = 'RIB'
    bank_account_nb.bank_code = get_random(banks)
    bank_account_nb.branch_code = str(random.randint(0, 999)).zfill(5)
    bank_account_nb.account_number = str(random.randint(0, 99999999)).zfill(11)
    bank_account_nb.key = str(97 - (89 * int(bank_account_nb.bank_code)
            + 15 * int(bank_account_nb.branch_code)
            + 3 * int(bank_account_nb.account_number)) % 97).zfill(2)


def load_bank_code(cfg_dict):
    f = open(os.path.join(
            DIR, cfg_dict['language'][0:2].lower(), 'bank.txt'),
        'r')
    res = {}
    n = 0
    for line in f:
        res[n] = line[0:5]
        n += 1
    f.close()
    return res
