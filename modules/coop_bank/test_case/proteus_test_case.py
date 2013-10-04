import re
import os
import random
import warnings
import logging

from proteus import Model
import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_cfg_dict(cfg_dict):
    cfg_dict['Bank'] = Model.get('bank')
    cfg_dict['Address'] = Model.get('party.address')
    cfg_dict['Country'] = Model.get('country.country')
    cfg_dict['Party'] = Model.get('party.party')
    cfg_dict['BankAccount'] = Model.get('bank.account')
    cfg_dict['BankAccountNumber'] = Model.get('bank.account.number')
    return cfg_dict


def create_banks(cfg_dict):
    banks = {}
    with open(os.path.join(DIR, 'bank.cfg'), 'r') as f:
        countries = {}
        banks = dict((x.bic, x) for x in cfg_dict['Bank'].find([]))
        n = 0
        for line in f:
            if n + len(banks) >= int(cfg_dict['nb_bank']):
                break
            try:
                bic = line[236:247].rstrip().replace(' ', '')
                if not bic or bic in banks:
                    continue
                bank = cfg_dict['Bank']()
                bank.bic = bic
                company = cfg_dict['Party']()
                company.is_company = True
                company.currency = cfg_dict['currency']
                company.name = line[11:51].strip()
                company.short_name = line[51:61].strip()
                add_address(cfg_dict, line, company, countries)
                add_bank_info(line, bic, bank)
                banks[bic] = bank
                company.save()
                bank.party = company
                bank.save()
                n += 1
            except:
                raise
                warnings.warn('Impossible to create bank %s' %
                    line[11:51].strip(), stacklevel=2)
    if n > 0:
        logging.getLogger('test_case').info(
            'Successfully imported %s banks' % n)
    return banks


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


def add_bank_info(line, bic, bank):
    bic = check_pattern(line[236:247], r'^[0-9A-Z]{8,11}')
    if bic:
        bank.bic = bic
    bank.bic = bic


def create_bank_accounts(cfg_dict, banks):
    Party = cfg_dict['Party']
    n = 0
    parties = Party.find([('bank_accounts', '=', None)])
    logging.getLogger('test_case').info(
        'Creating %s bank accounts' % len(parties))
    for party in parties:
        try:
            add_bank_account(cfg_dict, party, banks)
            party.save()
            n += 1
        except:
            warnings.warn('Impossible to create bank account for %s'
                % party.name, stacklevel=2)
    if n > 0:
        logging.getLogger('test_case').info(
            'Successfully created %s/%s bank accounts' % (n, len(parties)))


def get_random(the_dict):
    return u'%s' % the_dict.get(random.randint(0, len(the_dict) - 1))


def add_bank_account(cfg_dict, party, banks):
    bank_account = cfg_dict['BankAccount']()
    if party.bank_accounts is None:
        party.bank_accounts = []
    party.bank_accounts.append(bank_account)
    bank_account.currency = cfg_dict['currency']
    bank_account_nb = bank_account.numbers[-1]
    bank_account_nb.type = 'iban'
    bank_code = str(random.randint(0, 99999)).zfill(5)
    bank_account.bank = banks[random.choice(banks.keys())]
    branch_code = str(random.randint(0, 999)).zfill(5)
    account_number = str(random.randint(0, 99999999)).zfill(11)
    key = str(97 - (89 * int(bank_code) + 15 * int(branch_code)
            + 3 * int(account_number)) % 97).zfill(2)
    bank_account_nb.number = 'FR76%s%s%s%s' % (bank_code, branch_code,
        account_number, key)


def migrate_old_bank_account(cfg_dict, banks):
    for old_bank_account in Model.get('party.bank_account').find([]):
        if not old_bank_account.party.bank_accounts:
            bank_account = Model.get('bank.account')()
            bank_account.currency = cfg_dict['currency']
            bank_account.owners.append(old_bank_account.party)
            bank_account.start_date = old_bank_account.start_date
            bank_account.end_date = old_bank_account.end_date
            if old_bank_account.bank:
                bank_account.bank = old_bank_account.bank.bank_role[0]
            else:
                bank_account.bank = banks[random.choice(banks.keys())]
            bank_account.numbers[0].number = \
                old_bank_account.account_numbers[0].number
            bank_account.numbers[0].type = \
                old_bank_account.account_numbers[0].kind.lower()
            bank_account.save()
        old_bank_account.delete()


def migrate_bank():
    for old_bank in Model.get('party.bank').find([]):
        if not old_bank.party.bank_role:
            bank = Model.get('bank')()
            bank.party = old_bank.party
            bank.bic = old_bank.bic
            bank.save()
        old_bank.delete()


def launch_test_case(cfg_dict):
    update_cfg_dict(cfg_dict)
    migrate_bank()
    banks = create_banks(cfg_dict)
    migrate_old_bank_account(cfg_dict, banks)
    create_bank_accounts(cfg_dict, banks)
