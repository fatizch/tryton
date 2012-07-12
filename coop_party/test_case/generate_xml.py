from lxml import etree
import ConfigParser
import random
from datetime import date

def generate_xml(path):
    config = ConfigParser.ConfigParser()
    config.read('test_case.cfg')
    tryton = etree.Element('tryton')
    data = etree.SubElement(tryton, 'data')
    dicts = {}
    total_nb = config.getint('test_case', 'total_nb')
    nb_male = config.getint('test_case', 'nb_male')
    nb_female = total_nb - nb_male
    dicts['male'] = get_dictionnary(path + 'male.txt', nb_male)
    dicts['female'] = get_dictionnary(path + 'female.txt', nb_female)
    dicts['last_name'] = get_dictionnary(path + 'last_name.txt', total_nb)
    date_interv = calculate_date_interval(config)

    for i in range(nb_male):
        add_person(data, dicts, date_interv, 'M', i)

    for j in range(nb_female):
        add_person(data, dicts, date_interv, 'F', i + j+ 1)

    f = open('person_tc.xml', 'w')
    f.write('<?xml version="1.0"?>\n')
    f.write(etree.tostring(tryton, pretty_print=True))
    f.close()

def calculate_date_interval(config):
    start_date = date.today()
    start_date = start_date.replace(year=start_date.year
        - config.getint('test_case', 'adult_age_max')).toordinal()
    end_date = date.today()
    end_date = end_date.replace(year=end_date.year
        -config.getint('test_case', 'adult_age_min')).toordinal()
    return [start_date, end_date]

def add_person(data_node, dicts, date_interv, sex='M', i=0):
    party = etree.SubElement(data_node, 'record',
        {'model': "party.party",
         'id': 'party_%s' % i})
    add_field(party, 'name', get_random(dicts['last_name']))
    person = etree.SubElement(data_node, 'record',
        {'model': "party.person",
         'id': 'person_%s' % i})
    field = etree.SubElement(person, 'field',
        {'name': 'party', 'ref': 'party_%s' % i})
    add_field(person, 'gender', sex)
    if sex == 'M':
        the_dict = 'male'
    elif sex == 'F':
        the_dict = 'female'
    add_field(person, 'first_name', get_random(dicts[the_dict]))
    add_field(person, 'birth_date',
        str(date.fromordinal(random.randint(date_interv[0], date_interv[1]))))

def get_dictionnary(file_name, size):
    fd = open(file_name, 'r')
    res = {}
    n = 0
    for line in fd:
        res[n] = line.strip()
        n += 1
        #item are ordered by name popularity, if the sample is small,
        #no need to search for too exotic name
        if n >= 4 * size:
            break
    fd.close()
    return res

def get_random(the_dict):
    return u'%s' % the_dict.get(random.randint(0, len(the_dict)-1))

def add_field(node_parent, field_name, string):
    if string != '':
        field = etree.SubElement(node_parent, 'field', {'name': field_name})
        field.text = string

if __name__ == '__main__':
    config = ConfigParser.ConfigParser()
    config.read(r'../../coop_utils/coop.cfg')
    generate_xml(r'%s/' % config.get('localization', 'country').lower())
