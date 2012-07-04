import re
from lxml import etree
from ibanlib import iban


def read_file():
    f = open('bank.cfg', 'r')
    tryton = etree.Element('tryton')
    data = etree.SubElement(tryton, 'data')
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
            {'model': "party.legal_entity",
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

if __name__ == '__main__':
    read_file()
