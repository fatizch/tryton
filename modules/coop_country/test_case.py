from trytond.pool import PoolMeta, Pool
from trytond.modules.coop_utils import set_test_case, fields

MODULE_NAME = 'coop_country'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    load_all_zipcodes = fields.Boolean('Load all Zip Codes')
    main_zip = fields.Integer('Main Zip')

    @classmethod
    @set_test_case('Zip Code Test Case')
    def zip_code_test_case(cls):
        Country = Pool().get('country.country')
        Zip = Pool().get('country.zipcode')
        country = Country.search([
                ('code', '=', cls.get_language().code[-2:])])[0]
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
