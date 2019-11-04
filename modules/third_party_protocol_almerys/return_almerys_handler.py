# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from lxml import etree
import xml.etree.ElementTree as ET

from . import almerys

__all__ = [
    'AlmerysV3ReturnHandler',
    ]


class AlmerysV3ReturnHandler(object):

    def handle_file(self, file):
        known_codes = {x[0]: x[0] for x in almerys.ERROR_CODE}
        result = []
        tree = etree.parse(file)
        root = tree.getroot()
        encoding = tree.docinfo.encoding
        ET.tostring(root, encoding=encoding)
        link = root.tag.split('}')[0] + '}'
        for file_nbre in root.findall('./' + link + 'ENTETE/' + link +
                'NUM_FICHIER'):
            f_nbre = file_nbre.text
        rejets = root.findall('./' + link + 'OFFREUR_SERVICE/' + link +
            'REJETS/' + link + 'REJET_PRE_INTEGRATION/')
        for rejet in rejets:
            if rejet.tag == link + 'CONTRAT':
                contract = rejet[0].text
            elif rejet.tag == link + 'ERREUR':
                code_error = known_codes.get(rejet[0].text, 'UNKNOWN_CODE')
                label_error = rejet[1].text
                result.append((f_nbre, contract, code_error, label_error,))
        return result
