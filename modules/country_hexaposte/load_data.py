# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.config import config

from trytond.modules.coog_core import model, fields


__all__ = [
    'HexaPostSet',
    'HexaPostLoader',
    'HexaPostSetWizard',
    ]

mapping_fr_subdivision = {
    'GP': ['970', '971'],  # Guadeloupe
    'MQ': ['972'],  # Martinique
    'GF': ['973'],  # Guyanne
    'RE': ['974', '977', '978', ],  # Réunion
    'PM': ['975'],  # St Pierre et Miquelon
    'YT': ['976'],  # Mayotte
    'TF': ['984'],  # Terres australes française
    'WF': ['986'],  # Wallis et Futuna
    'PF': ['987'],  # Polynésie Française
    'NC': ['988'],  # Nouvelle calédonie
    '2A': ['201', '200', '203', '205', '207', '209'],  # Corse du sud
    '2B': ['202', '206', '204'],  # Haute corse
    }


class HexaPostSet(model.CoogView):
    'HexaPost Loader '

    __name__ = 'country.hexapost.set'

    use_default = fields.Boolean('Use default file')
    resource = fields.Binary('Resource', states={
            'invisible': Bool(Eval('use_default'))
            })
    data_file = fields.Char('Default data file', states={
            'readonly': True,
            'invisible': True,
            })

    @classmethod
    def __setup__(cls):
        super(HexaPostSet, cls).__setup__()
        cls._error_messages.update({
                'cant_find_subdivision': "Can't find subdivision for %s"
                })

    @staticmethod
    def default_data_file():
        filename = 'HEXAPOSTNV2011_2016.tri'
        top_path = os.path.abspath(os.path.dirname(__file__))
        data_path = os.path.join(
            top_path, 'test_case_data',
            Transaction().language, filename)
        return data_path


class HexaPostSetWizard(Wizard):
    'HexaPost Loader Set Wizard'

    __name__ = 'country.hexapost.set.wizard'

    start_state = 'configuration'
    configuration = StateView('country.hexapost.set',
        'country_hexaposte.hexapost_set_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Set', 'set_', 'tryton-ok', default=True),
            ])
    set_ = StateTransition()

    def transition_set_(self):
        Zip = Pool().get('country.zip')
        if self.configuration.use_default:
            with open(self.configuration.data_file, 'r',
                    encoding='latin-1') as _file:
                data = HexaPostLoader.get_hexa_post_data_from_file(_file)
        else:
            data = HexaPostLoader.get_hexa_post_data_from_file(
                self.configuration.resource)
        to_create, to_write = HexaPostLoader.get_hexa_post_updates(data)
        if to_create:
            Zip.create(to_create)
        if to_write:
            with ServerContext().set_context(from_batch=True):
                Zip.write(*to_write)
        return 'end'


class HexaPostLoader(object):
    '''Utility class to update coog's zipcode repository from
     HEXAPOSTE NV 2011 file'''

    @classmethod
    def get_hexa_post_updates(cls, hexa_data):
        pool = Pool()
        Country = pool.get('country.country')
        Zip = pool.get('country.zip')

        france = Country.search([('code', '=', 'FR')])[0]

        existing_zips = Zip.search([('country', '=', france.id)])
        zip_dict_hexa_id = {x.hexa_post_id: x for x in existing_zips}
        zip_dict_hexa_id_keys = set(zip_dict_hexa_id.keys())
        zip_dict_name = {'%s_%s_%s' % (x.zip, x.city,
                x.line5 or ''): x for x in existing_zips}
        zip_dict_name_keys = set(zip_dict_name.keys())

        hexa_data_coog = cls.convert_hexa_data_to_coog_data(hexa_data)

        to_create = []
        to_write = []
        created = set([])
        for line in hexa_data_coog:
            zip = line['zip']
            city = line['city']
            hexa_id = line['hexa_post_id']
            line5 = line['line5']
            name_key = '%s_%s_%s' % (zip, city, line5)

            if hexa_id in zip_dict_hexa_id_keys:
                to_write.extend(([zip_dict_hexa_id[hexa_id]], line))
            else:
                line['country'] = france.id
                if name_key not in zip_dict_name_keys:
                    to_create.append(line)
                    created.add(name_key)
                elif name_key not in created:
                    to_write.extend(([zip_dict_name[name_key]], line))
                zip_dict_name_keys.add(name_key)

        return to_create, to_write

    @classmethod
    def convert_hexa_data_to_coog_data(cls, data):
        pool = Pool()
        SubDivision = pool.get('country.subdivision')
        Country = pool.get('country.country')
        UpdateCreationView = pool.get('country.hexapost.set')

        france = Country.search([('code', '=', 'FR')])[0]

        subdivisions = SubDivision.search([('country', '=', france.id)])
        subdivisions_cache = {}
        for division in subdivisions:
            # First 3 characters are FR_
            if division.code[3:] in mapping_fr_subdivision:
                for code in mapping_fr_subdivision[division.code[3:]]:
                    subdivisions_cache[code] = division
            else:
                subdivisions_cache[division.code[3:]] = division
        translation = {
            'delivery_wording': 'city',
            'post_code': 'zip',
            'address_id': 'hexa_post_id',
            'line_5_wording': 'line5',
            'insee_code': 'insee_code',
            }
        res = []
        is_testing = config.getboolean('env', 'testing')
        for line in data:
            if not line['post_code'] or not line['delivery_wording']:
                continue
            new_line = {}
            for k, v in translation.items():
                new_line[v] = line[k]
            if line['post_code'][:2] in subdivisions_cache:
                new_line['subdivision'] = subdivisions_cache[
                    line['post_code'][:2]]
            elif line['post_code'][:3] in subdivisions_cache:
                new_line['subdivision'] = subdivisions_cache[
                    line['post_code'][:3]]
            elif line['post_code'][:2] not in ('00', '98'):
                if not is_testing:
                    UpdateCreationView.raise_user_error('cant_find_subdivision',
                        line['post_code'])
            res.append(new_line)
        return res

    @classmethod
    def get_hexa_post_data_from_file(cls, f):
        lines = []
        for line in f:
            lines.append(line)
        prefix = cls.load_prefix(lines[0])
        return cls.load_hexa_lines(lines[1:], prefix)

    @classmethod
    def load_prefix(cls, prefix_line):
        prefix = {}
        prefix['creation_date'] = prefix_line[0:10]
        prefix['file_wording'] = prefix_line[10:32]
        prefix['file_kind'], prefix['format'] = prefix_line[32:].split()
        return prefix

    @classmethod
    def load_hexa_lines(cls, lines, prefix):
        p = {
            '32': {           # len, index
                'address_id': [6, 0],
                'insee_code': [5, 6],
                'commune_wording': [32, 11],
                'multi_delivery': [1, 43],
                'post_code_type': [1, 44],
                'line_5_wording': [32, 45],
                'post_code': [5, 108],
                'delivery_wording': [26, 82],
                'former_insee_code': [5, 108],
                'update_code': [1, 113],
                'cea': [10, 114]
                },
            '38': {
                'address_id': [6, 0],
                'insee_code': [5, 6],
                'commune_wording': [38, 11],
                'multi_delivery': [1, 49],
                'post_code_type': [1, 50],
                'line_5_wording': [38, 51],
                'post_code': [5, 89],
                'delivery_wording': [32, 94],
                'former_insee_code': [5, 126],
                'update_code': [1, 131],
                'cea': [10, 132]
                }
            }
        res = []
        file_format = prefix['format']
        for line in lines:
            code_line = {}
            for field, params in list(p[file_format].items()):
                raw = line[params[1]:params[1] + params[0]]
                clean = raw.strip()
                code_line[field] = clean
            res.append(code_line)
        return res
