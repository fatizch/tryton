from trytond.pool import Pool


__all__ = [
    'HexaPostLoader',
    ]


class HexaPostLoader(object):
    '''Utility class to update coog's zipcode repository from
     HEXAPOSTE NV 2011 file'''

    @classmethod
    def get_hexa_post_updates(cls, hexa_data):
        Country = Pool().get('country.country')
        Zip = Pool().get('country.zipcode')

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
