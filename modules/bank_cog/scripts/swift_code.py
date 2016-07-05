# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import requests
from bs4 import BeautifulSoup
from collections import defaultdict

# this script requires to install request and BeautifulSoup python packages
# pip install requests BeautifulSoup
#
# after around 3000 call the web site http://www.swiftcodes.info/ is no more
# accessible: the ip is blacklisted

bic_file_name = '/home/user/temp/bic.csv'

# list of country
countries = ['french-guiana', 'french-polynesia']

with open(bic_file_name, 'w') as bic_file:
    bic_file.write('bank_name;branch_name;bic;address_street;address_zip;'
        'address_city;address_country\n')

    bics = defaultdict(list)
    for country in countries:
        site = 'http://www.swiftcodes.info/%s/' % country
        i = 1
        r = requests.get(site)
        while r.status_code == 200:
            soup = BeautifulSoup(r.text)
            table = soup.find('table', 'swift')
            table_data = [[cell.text for cell in row("td")]
                 for row in table("tr")]
            for data in table_data:
                if len(data) == 5:
                    bics[country].append({
                            'bank_name': data[1],
                            'city': data[2],
                            'branch_name': data[3],
                            'swift_code': data[4],
                            })
            i += 1
            site = 'http://www.swiftcodes.info/%s/page/%s/' % (country, i)
            r = requests.get(site)

    for key, values in bics.iteritems():
        for bic in values:
            site = 'http://www.swiftcodes.info/%s/swift-code-%s' % (key,
                bic['swift_code'])
            r = requests.get(site)
            soup = BeautifulSoup(r.text)
            table = soup.find_all("table")
            table_data = [[cell.text for cell in row("td")]
                 for row in table[0]("tr")]
            table_data.remove([])
            table_dic = dict(table_data)
            bic_file.write('%s;%s;%s;%s;%s;%s;%s\n' %
                (bic['bank_name'],
                bic['branch_name'],
                bic['swift_code'],
                table_dic['Address'],
                table_dic['Postcode'],
                table_dic['City'],
                table_dic['Country'],
                ))
            print '%s exported' % bic
