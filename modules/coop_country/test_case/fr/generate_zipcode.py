#!/usr/bin/python
# -*- coding: utf-8 -*-
import urllib
import sys
import csv
from HTMLParser import HTMLParser
import logging


def get_cp(txtCommune=None, cdep=None, txtCP=None, with_debug=False):
    #logging.info("looking for %s" % txtCommune)
    params = {'selCritere': 'CP'}
    if txtCommune:
        params['txtCommune'] = txtCommune
    if txtCP:
        params['txtCP'] = txtCP
        if not cdep:
            cdep = txtCP[0:2]
    params = urllib.urlencode(params)
    f = urllib.urlopen(
        'http://www.laposte.fr/sna/rubrique.php3?id_rubrique=59&recalcul=oui',
        params)
    reponse = f.read().decode('iso-8859-1')
    f.close()
    if reponse.find(u'Aucune réponse.') >= 0:
        return None
    i = 0
    while i > -1:
        i = reponse.find('onclick=window.open')
        if i > -1:
            #logging.warn("malformed html found for %s" % txtCommune)
            j = reponse.find('false;', i)
            reponse = reponse[:i] + reponse[j + len('false;'):]
    p = MyParser(cdep)
    p.feed(reponse)
    p.close()
    # if with_debug:
    #     print p.cp_found
    return p.cp_found


class MyParser(HTMLParser):
    read_tag = False
    tag = None
    cdep = None
    cp_found = []

    def __init__(self, cdep):
        HTMLParser.__init__(self)
        if cdep in ['2A', '2B']:
            cdep = '20'
        self.cdep = cdep
        self.tag = None
        self.read_tag = False
        self.result_found = False
        self.cp_found = []

    def handle_starttag(self, tag, attrs):
        for a, v in attrs:
            if a == 'class' and v == 'resultat' or self.result_found:
                self.read_tag = True
                self.tag = tag

    def handle_endtag(self, tag):
        if self.read_tag:
            if tag == self.tag:
                self.read_tag = False

    def handle_data(self, data):
        data = data.rstrip().lstrip()
        if data == '':
            return
        if self.read_tag and data != '-1-':
            if data.replace(' ', '').isnumeric():
                # working on CP
                if not self.cdep or data.startswith(self.cdep):
                    self.result_found = True
                    self.cp_found.append([data, ''])
            else:
                # working on commune
                for cp in reversed(self.cp_found):
                    if cp[1] == '':
                        self.cp_found[self.cp_found.index(cp)][1] = data
                    else:
                        break
                self.result_found = False


def write_cp_by_zipcode(to_file):
    with open(to_file, 'w') as insee_cp:
        for dep in range(1, 100):
            for commune in range(1000):
                txtCP = '%s%s' % (str(dep).zfill(2), str(commune).zfill(3))
                cps = get_cp(txtCP=txtCP)
                if cps is not None and len(cps) == 0:
                    print 'Pb retrieving CP %s' % txtCP
                elif cps:
                    for cur_list in cps:
                        cedex = 'CEDEX' in cur_list[1].upper()
                        line = "%s\t%s\t%s" % (cur_list[1], cur_list[0], cedex)
                        insee_cp.write(line)
                        insee_cp.write("\n")


def normalize_commune(art, ncc):
    #logging.info("normalizing %s %s" % (art, ncc))
    resu = None
    if art:
        resu = art.strip('(').strip(')').strip("'")
    if resu:
        resu = "%s %s" % (resu, ncc)
    else:
        resu = ncc
    resu = resu.replace('-', ' ').replace("'", " ")
    if resu.startswith('SAINT '):
        resu = 'ST ' + resu[6:]
    if resu.startswith('SAINTE '):
        resu = 'STE ' + resu[7:]
    return resu


def write_cp(from_file, to_file):
    logging.basicConfig(level=logging.INFO)
    with open(to_file, 'w') as insee_cp:
        with open(from_file) as insee:
            first = True
            for line in insee:
                if first:
                    first = False
                    continue
                splitted = line.split('\t')
                dep = splitted[3]
                com = splitted[4]
                artmaj = splitted[8]
                ncc = splitted[9]
                txtCommune = normalize_commune(artmaj, ncc)
                try:
                    cp = get_cp(txtCommune, dep)
                    #cp = get_cp('MARSEILLE', '13')
                except:
                    logging.info("Exception when searching CP for %s" %
                        txtCommune)
                    continue
                cd_insee = dep + com
#                if len(cp) > 1:
#                    logging.warn("Plusieurs    CP")
#                    logging.warn(cp)
                if len(cp) == 0:
                    logging.info("Impossible to find CP for %s in %s"
                            % (txtCommune, dep))
                for cur_list in cp:
                    if cur_list[1] != txtCommune:
                        logging.info("Searching: %s Found: %s CP: %s INSEE: %s"
                            % (txtCommune, cur_list[1], cur_list[0], cd_insee))
                    insee_cp.write("%s\t%s\t%s" % (cur_list[1], cur_list[0],
                        cd_insee))
                    insee_cp.write("\n")


def test_CP():
    print get_cp(txtCommune='BOURG EN BRESSE', cdep='01', with_debug=True)


def merge_zip_codes():
    cur_dict = {}

    reader2 = csv.reader(open('zipcode.csv', 'rb'), delimiter='\t')
    for cur_line in reader2:
        if not cur_line[1] in cur_dict:
            cur_dict[cur_line[1]] = []
        cur_dict[cur_line[1]].append(cur_line)

    reader = csv.reader(open('communes.txt', 'rb'), delimiter='\t')
    for cur_line in reader:
        cur_line[1] = cur_line[1].strip(' ')
        found = False
        if not cur_line[1] in cur_dict:
            cur_dict[cur_line[1]] = []
        else:
            for line in cur_dict[cur_line[1]]:
                if line[0] == cur_line[0]:
                    found = True
                    break
        if not found:
            cur_dict[cur_line[1]].append(cur_line)

    destination = open("zip_merged.csv", "w")
    k = 0
    for i in range(1000, 98900):
        lines = cur_dict.get(str(i).zfill(5))
        if i == 6000:
            print i, lines
        if lines:
            for line in lines:
                k += 1
                destination.write('%s\t%s\t%s\n' % (line[0], line[1], 'CEDEX' in line[0]))
                if i == 6000:
                    print '%s\t%s\t%s\n' % (line[0], line[1], 'CEDEX' in line[0])
    destination.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        #from_file = sys.argv[1]
        to_file = sys.argv[2]
    else:
        #from_file = 'comsimp2012.txt'
        to_file = 'zipcode_temp.csv'
    #write_cp(from_file, to_file)
    write_cp_by_zipcode(to_file)
