#!/usr/bin/python
import urllib
import sys
from HTMLParser import HTMLParser
import logging


def get_cp(txtCommune, cdep=None):
    #logging.info("looking for %s" % txtCommune)
    params = urllib.urlencode({'txtCommune': txtCommune, 'selCritere': 'CP'})
    f = urllib.urlopen(
        'http://www.laposte.fr/sna/rubrique.php3?id_rubrique=59&recalcul=oui',
        params)
    reponse = f.read().decode('iso-8859-1')
    #print reponse
    f.close()
    #-- remove malformatted HTML
    i = 0
    while i > -1:
        i = reponse.find('onclick=window.open')
        if i > -1:
            logging.warn("malformed html found")
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
                for cur_list in cp:
                    if cur_list[1] != txtCommune:
                        logging.info("Searching: %s Found: %s CP: %s INSEE: %s"
                            % (txtCommune, cur_list[1], cur_list[0], cd_insee))
                    insee_cp.write("%s\t%s\t%s" % (txtCommune, cur_list[0],
                        cd_insee))
                    insee_cp.write("\n")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        from_file = sys.argv[1]
        to_file = sys.argv[2]
    else:
        from_file = 'comsimp2012.txt'
        to_file = 'zipcode.csv'
    write_cp(from_file, to_file)
