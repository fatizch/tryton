import re
from lxml import etree
from ibanlib import iban
import ConfigParser
import random


def generate_bank():
    f = open('bank.cfg', 'r')
    tryton = etree.Element('tryton')
    data = etree.SubElement(tryton, 'data', {'skiptest': "1"})
    for line in f:
        party = etree.SubElement(data, 'record',
            {'model': "party.party",
             'id': 'party_%s' % line[0:5]})
        add_field(party, 'name', line[11:51].strip())
        add_field(party, 'code', line[51:61].strip())
#        field = etree.SubElement(party, 'field',
#            {'name': 'addresses', 'eval': "[('delete_all',)]"})

        add_address(line, data)

        le = etree.SubElement(data, 'record',
            {'model': "company.company",
             'id': 'le_%s' % line[0:5]})
        field = etree.SubElement(le, 'field',
        {'name': 'party', 'ref': 'party_%s' % line[0:5]})

        add_bank(line, data)

    f.close()

    f = open('bank_tc.xml', 'w')
    f.write('<?xml version="1.0"?>\n')
    f.write(etree.tostring(tryton, pretty_print=True))
    f.close()


def check_pattern(s, pattern):
    if s is not None:
        s = s.strip()
        matchObj = re.match(pattern, s)
        if matchObj:
            return matchObj.group()
        return False


def add_field(node_parent, field_name, string):
    if string != '':
        field = etree.SubElement(node_parent, 'field', {'name': field_name})
        field.text = string


def add_address(line, node):
    address = etree.SubElement(node, 'record',
        {'model': "party.address",
         'id': 'address_%s' % line[0:5]})
    field = etree.SubElement(address, 'field',
        {'name': 'party', 'ref': 'party_%s' % line[0:5]})
    add_field(address, 'line1', line[11:49].strip())
    add_field(address, 'line3', line[88:120].strip())
    add_field(address, 'street', line[120:152].strip().upper())
    add_field(address, 'streetbis', line[152:184].strip().upper())
    add_field(address, 'zip', line[184:189].strip().upper())
    add_field(address, 'city', line[190:216].strip().upper())
    country = check_pattern(line[240:242], r'^[A-Z]{2}')
    if country:
        field = etree.SubElement(address, 'field',
            {'name': 'country', 'ref': 'country.' + country.lower()})


def add_bank(line, node):
    bank = etree.SubElement(node, 'record',
        {'model': "party.bank",
         'id': 'bank_%s' % line[0:5]})
    field = etree.SubElement(bank, 'field',
    {'name': 'party', 'ref': 'party_%s' % line[0:5]})
    bic = check_pattern(line[236:247], r'^[0-9A-Z]{8,11}')
    if bic and iban.valid_BIC(bic):
        add_field(bank, 'bic', bic)

    add_field(bank, 'bank_code', line[0:5])

def generate_bank_account(path):
    config = ConfigParser.ConfigParser()
    config.read(r'../../coop_party/test_case/test_case.cfg')
    tryton = etree.Element('tryton')
    data = etree.SubElement(tryton, 'data')
    dicts = {}
    total_nb = config.getint('test_case', 'total_nb')

    banks = load_bank_code(path)

    for i in range(total_nb):
        add_bank_account(data, i, banks)

    f = open('bank_account_tc.xml', 'w')
    f.write('<?xml version="1.0"?>\n')
    f.write(etree.tostring(tryton, pretty_print=True))
    f.close()

def get_random(the_dict):
    return u'%s' % the_dict.get(random.randint(0, len(the_dict)-1))

def add_bank_account(node, i, banks):
    bank_account = etree.SubElement(node, 'record',
        {'model': "party.bank_account",
         'id': 'bank_account_%s' % i})
    field = etree.SubElement(bank_account, 'field',
        {'name': 'party', 'ref': 'coop_party.party_%s' % i})
    bank_account_nb = etree.SubElement(node, 'record',
        {'model': "party.bank_account_number",
         'id': 'bank_account_nb_%s' % i})
#    field = etree.SubElement(bank_account_nb, 'field',
#            {'name': 'kind', 'eval': "[('delete_all',)]"})
    field = etree.SubElement(bank_account_nb, 'field',
        {'name': 'bank_account', 'ref': 'bank_account_%s' % i})
    add_field(bank_account_nb, 'kind', 'RIB')

    code_bank = get_random(banks)
    code_branch = str(random.randint(0, 999)).rjust(5, '0')
    account_number = str(random.randint(0, 99999999)).rjust(11, '0')
    key = 97 - (89 * int(code_bank) + 15 * int(code_branch)
                + 3 * int(account_number)) % 97
    add_field(bank_account_nb, 'number',
        code_bank+code_branch+account_number+str(key).rjust(2, '0'))

def load_bank_code(path):
    f = open(path+'bank.txt', 'r')
    res = {}
    n = 0
    for line in f:
        res[n] = line[0:5]
        n += 1
    f.close()
    return res
    

if __name__ == '__main__':
    generate_bank()
    config = ConfigParser.ConfigParser()
    config.read(r'../../coop_utils/coop.cfg')
    generate_bank_account(r'%s/' % config.get('localization', 'country').lower())
