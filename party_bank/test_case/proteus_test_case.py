import re
import os
import random
import warnings

from proteus import Model
import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_cfg_dict(cfg_dict):
    cfg_dict['Bank'] = Model.get('party.bank')
    cfg_dict['Address'] = Model.get('party.address')
    cfg_dict['Country'] = Model.get('country.country')
    cfg_dict['Party'] = Model.get('party.party')
    cfg_dict['BankAccount'] = Model.get('party.bank_account')
    cfg_dict['BankAccountNumber'] = Model.get('party.bank_account_number')
    cfg_dict['Society'] = Model.get('party.society')
    return cfg_dict


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict(cfg_dict)

    if is_table_empty(cfg_dict['Bank']):
        create_bank(cfg_dict)
    create_bank_accounts(cfg_dict)


def is_table_empty(model):
    return len(model.find(limit=1)) == 0


def create_bank(cfg_dict):
    f = open(os.path.join(DIR, 'bank.cfg'), 'r')
    countries = {}
    n = 0
    for line in f:
        if n >= int(cfg_dict['nb_bank']):
            break
        try:
            bank = cfg_dict['Bank']()
            society = cfg_dict['Society']()
            society.currency = cfg_dict['currency']
            if bank.society is None:
                bank.society = []
            bank.society.append(society)
            bank.name = line[11:51].strip()
            bank.code = line[51:61].strip()
            add_address(cfg_dict, line, bank, countries)
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


def get_country(cfg_dict, country_code, countries):
    if country_code in countries.keys():
        return countries[country_code]
    Country = cfg_dict['Country']
    country, = Country.find(
        [('code', '=', country_code.upper())],
        limit=1)
    countries[country_code] = country
    return country


def add_address(cfg_dict, line, bank, countries):
    address = bank.addresses[0]
    address.name = line[11:49].strip()
    address.line3 = line[88:120].strip()
    address.street = line[120:152].strip().upper()
    address.streetbis = line[152:184].strip().upper()
    address.zip = line[184:189].strip().upper()
    address.city = line[190:216].strip().upper()
    country_code = check_pattern(line[240:242], r'^[A-Z]{2}')
    proteus_tools.create_zip_code_if_necessary(address)
    if country_code:
        address.country = get_country(cfg_dict, country_code, countries)


def add_bank_info(line, bank):
    bic = check_pattern(line[236:247], r'^[0-9A-Z]{8,11}')
    if bic:
        bank.bic = bic
    bank.bank_code = line[0:5]


def create_bank_accounts(cfg_dict):
    banks = load_bank_code(cfg_dict)
    Party = cfg_dict['Party']
    n = 0
    parties = Party.find([('bank_accounts', '=', None)])
    print 'Creating %s bank accounts' % len(parties)
    for party in parties:
        try:
            add_bank_account(cfg_dict, party, banks)
            party.save()
            n += 1
        except:
            warnings.warn('Impossible to create bank account for %s'
                % party.name, stacklevel=2)
    if n > 0:
        print 'Successfully created %s/%s bank accounts' % (n, len(parties))


def get_random(the_dict):
    return u'%s' % the_dict.get(random.randint(0, len(the_dict) - 1))


def add_bank_account(cfg_dict, party, banks):
    bank_account = cfg_dict['BankAccount']()
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
