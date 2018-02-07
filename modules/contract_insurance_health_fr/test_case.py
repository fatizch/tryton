# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta, Pool


MODULE_NAME = 'contract_insurance_health_fr'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def create_hc_system(cls, **kwargs):
        HealthCareSystem = Pool().get('health.care_system')
        return HealthCareSystem(**kwargs)

    @classmethod
    def health_care_system_test_case(cls):
        HealthCareSystem = Pool().get('health.care_system')
        cls.load_resources(MODULE_NAME)
        hc_system_file = cls.read_csv_file('hc_system.csv', MODULE_NAME,
            reader='dict')
        hc_systems = []
        for hc_system_data in hc_system_file:
            hc_systems.append(cls.create_hc_system(
                    code=hc_system_data['code'],
                    name=hc_system_data['name'],
                    short_name=hc_system_data['short_name'],
                    ))
        HealthCareSystem.create([x._save_values for x in hc_systems])

    @classmethod
    def create_fund(cls, **kwargs):
        Fund = Pool().get('health.insurance_fund')
        return Fund(**kwargs)

    @classmethod
    def new_fund(cls, data, addresses):
        HealthCareSystem = Pool().get('health.care_system')
        hc_system = HealthCareSystem.search([
                ('code', '=', data['hc_system_code'].zfill(2))])[0]
        department = ''
        if data['ID_ADR'] in addresses:
            zip_code = addresses[data['ID_ADR']]['Code Postal']
            if zip_code[0:2] in ['97', '98']:
                department = zip_code[0:3]
            else:
                department = zip_code[0:2]
        return cls.create_fund(
            code=data['code'], name=data['name'], hc_system=hc_system,
            department=department)

    @classmethod
    def fund_test_case(cls):
        pool = Pool()
        Fund = pool.get('health.insurance_fund')
        HealthCareSystem = pool.get('health.care_system')
        cls.load_resources(MODULE_NAME)
        systems = {}
        health_care_systems = HealthCareSystem.search([])
        for health_care_system in health_care_systems:
            systems[health_care_system.code] = health_care_system.id

        first_line = True
        funds = []
        with open(cls._loaded_resources[MODULE_NAME]['files']['orgdest.csv'],
                'r') as f:
            for line in f:
                if first_line:
                    first_line = False
                    continue
                decode_line = line.decode('latin-1')
                decode_line = decode_line.replace('"', '')
                fund_data = decode_line.split(';')
                funds.append(Fund(
                    code=fund_data[0] + fund_data[1] + fund_data[2],
                    name=fund_data[3],
                    hc_system=systems[fund_data[0]],
                    department=fund_data[10][0:2]))
                print 'code ', fund_data[0] + fund_data[1] + fund_data[2],\
                    ' name ', fund_data[3],\
                    ' hc_system', systems[fund_data[0]],\
                    'department', fund_data[10][0:2]
            Fund.create([x._save_values for x in funds])
