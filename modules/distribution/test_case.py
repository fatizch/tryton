# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import random

from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import coog_string

MODULE_NAME = 'distribution'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def create_distribution_network(cls, **kwargs):
        DistributionNetwork = Pool().get('distribution.network')
        if 'code' not in kwargs:
            kwargs['code'] = coog_string.slugify(
                kwargs['name'])
        if 'company' not in kwargs:
            kwargs['company'] = cls.get_company()
        return DistributionNetwork(**kwargs)

    @classmethod
    def new_distribution_network(cls, name, children_name=None,
            children_number=None):
        res = cls.create_distribution_network(name=name, childs=[])
        childs = []
        if children_name and children_number:
            for i in range(1, children_number + 1):
                child = cls.new_distribution_network('%s %s' %
                    (children_name, i))
                child.code = str(i).zfill(2)
                childs.append(child)
        res.childs = childs
        return res

    @classmethod
    def distribution_network_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        root = cls.new_distribution_network(translater('Root'))

        internal_network = cls.new_distribution_network(translater(
                'Internal Network'), translater('Region'), 2)
        internal_network.code = 'C2'
        for child in internal_network.childs:
            child.code = internal_network.code + child.code
        childs = list(root.childs)
        childs.append(internal_network)
        for region in internal_network.childs:
            for i in range(1, random.randint(1, 3)):
                name = '%s : %s %s' % (region.name, translater('Dept'), i)
                department = cls.new_distribution_network(name, '%s %s' %
                    (name, translater('Agency')), random.randint(1, 5))
                department.code = region.code + str(i).zfill(2)
                for child in department.childs:
                    child.code = department.code + child.code
                region_childs = list(region.childs)
                region_childs.append(department)
                region.childs = region_childs
        partner = cls.new_distribution_network(
            translater('Commercial Partners'), translater('Partner'),
            random.randint(2, 3))
        partner.code = 'C1'
        for child in partner.childs:
            child.code = partner.code + child.code
        childs.append(partner)
        for sub_partner in partner.childs:
            for i in range(1, random.randint(2, 3)):
                if sub_partner == partner.childs[0]:
                    name = '%s : %s %s' % (sub_partner.name,
                        translater('Agency'), i)
                    department = cls.new_distribution_network(name,
                        '%s %s' % (name, translater('Commercial')),
                        random.randint(2, 10))
                else:
                    name = '%s : %s %s' % (sub_partner.name,
                        translater('Dept'), i)
                    department = cls.new_distribution_network(name,
                        '%s %s' % (name, translater('Broker')),
                        random.randint(2, 10))
                department.code = sub_partner.code + str(i).zfill(2)
                for child in department.childs:
                    child.code = department.code + child.code
                sub_partner_childs = list(sub_partner.childs)
                sub_partner_childs.append(department)
                sub_partner.childs = sub_partner_childs
        other = cls.new_distribution_network(translater('Open World'),
            translater('Broker'), 20)
        other.code = 'C3'
        for child in other.childs:
            child.code = other.code + child.code
        childs.append(other)
        root.childs = childs
        root.save()

    @classmethod
    def distribution_network_test_case_test_method(cls):
        translater = cls.get_translater(MODULE_NAME)
        DistributionNetwork = Pool().get('distribution.network')
        return len(DistributionNetwork.search(
                [('name', '=', translater('Root'))])) == 0
