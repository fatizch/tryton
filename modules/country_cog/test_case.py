# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

MODULE_NAME = 'country_cog'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    load_all_zipcodes = fields.Boolean('Load all Zip Codes')
    main_zip = fields.Integer('Main Zip')

    @classmethod
    def zip_code_test_case(cls):
        if Transaction().context.get('TESTING', False):
            return
        Country = Pool().get('country.country')
        Zip = Pool().get('country.zip')
        countries = Country.search([
                ('code', '=', cls.get_language().code.upper())])
        if not countries:
            return
        country = countries[0]
        cls.load_resources(MODULE_NAME)
        zip_file = cls.read_csv_file('zipcode.csv', MODULE_NAME, sep='\t')
        existing_zips = Zip.search([('country', '=', country.id)])
        zip_dict = dict([('%s_%s' % (x.zip, x.city), x)
                for x in existing_zips])
        res = []
        for cur_line in zip_file:
            if len(cur_line) < 2:
                continue
            if (cls.get_instance().load_all_zipcodes
                    or cur_line[1][0:2] in cls.get_instance().main_zip):
                zip = cur_line[1].rstrip().lstrip()
                city = cur_line[0].rstrip().lstrip()
                if '%s_%s' % (zip, city) in zip_dict:
                    continue
                res.append({'city': city, 'zip': zip, 'country': country.id})
        if len(res):
            Zip.create(res)
            cls.get_logger().info('Successfully created %s zipcodes' %
                len(res))
        else:
            cls.get_logger().info('No zipcode to update')
