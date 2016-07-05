# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from .hexa_post import HexaPostLoader

MODULE_NAME = 'country_hexaposte'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def hexa_post_test_case(cls):
        Zip = Pool().get('country.zip')
        if Transaction().context.get('TESTING', False):
            return
        hexa_data = cls.load_hexa_post_data_from_file(
            MODULE_NAME, 'HEXAPOSTNV2011_2016.tri')
        to_create, to_write = HexaPostLoader.get_hexa_post_updates(hexa_data)
        if to_create:
            Zip.create(to_create)
            cls.get_logger().info('Successfully created new %s zipcodes' %
                len(to_create))
        if to_write:
            Zip.write(*to_write)
            cls.get_logger().info('Successfully updated %s zipcodes' %
                str(len(to_write) / 2))
        else:
            cls.get_logger().info('No zipcode to update')

    @classmethod
    def load_hexa_post_data_from_file(cls, module, filename):
        cls.load_resources(module)
        if isinstance(cls._loaded_resources[module]['files'][filename], list):
            return cls._loaded_resources[module]['files'][filename]
        with open(cls._loaded_resources[module]['files'][filename], 'r') as f:
            res = HexaPostLoader.get_hexa_post_data_from_file(f)
        cls._loaded_resources[module]['files'][filename] = res
        return res
