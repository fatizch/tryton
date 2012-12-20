#!/usr/bin/python
# -*- coding: utf-8 -*-
import urllib
import sys
from HTMLParser import HTMLParser


def get_cp(txtCommune=None, cdep=None, txtCP=None):
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


def test_CP():
    print get_cp(txtCP='27630')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        #from_file = sys.argv[1]
        to_file = sys.argv[2]
    else:
        #from_file = 'comsimp2012.txt'
        to_file = 'zipcode_temp.csv'
    #write_cp(from_file, to_file)
    write_cp_by_zipcode(to_file)
