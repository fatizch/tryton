# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
from io import BytesIO
from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.transaction import Transaction
from trytond.modules.coog_core import model, fields


__all__ = [
    'HexaPostSet',
    'HexaPostLoader',
    'HexaPostSetWizard',
    ]


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
            with open(self.configuration.data_file, 'rb') as _file:
                data = HexaPostLoader.get_hexa_post_data_from_file(_file)
        else:
            data = HexaPostLoader.get_hexa_post_data_from_file(
                BytesIO(self.configuration.resource))
        to_create, to_write = HexaPostLoader.get_hexa_post_updates(data)
        if to_create:
            Zip.create(to_create)
        if to_write:
            Zip.write(*to_write)
        return 'end'


class HexaPostLoader(object):
    '''Utility class to update coog's zipcode repository from
     HEXAPOSTE NV 2011 file'''

    @classmethod
    def get_hexa_post_updates(cls, hexa_data):
        Country = Pool().get('country.country')
        Zip = Pool().get('country.zip')

        france = Country.search([('code', '=', 'FR')])[0]

        existing_zips = Zip.search([('country', '=', france.id)])
        zip_dict_hexa_id = {x.hexa_post_id: x for x in existing_zips}
        zip_dict_hexa_id_keys = set(zip_dict_hexa_id.keys())
        zip_dict_name = {'%s_%s_%s' % (x.zip, x.city, x.line5 or ''): x
                for x in existing_zips}
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
        translation = {
            'delivery_wording': 'city',
            'post_code': 'zip',
            'address_id': 'hexa_post_id',
            'line_5_wording': 'line5',
            }
        res = []
        for line in data:
            if not line['post_code'] or not line['delivery_wording']:
                continue
            new_line = {}
            for k, v in translation.iteritems():
                new_line[v] = line[k]
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
            for field, params in p[file_format].items():
                raw = line[params[1]:params[1] + params[0]]
                clean = raw.strip()
                code_line[field] = clean
            res.append(code_line)
        return res
