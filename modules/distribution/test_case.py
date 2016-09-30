# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import random

from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import coop_string

MODULE_NAME = 'distribution'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def create_distribution_network(cls, **kwargs):
        DistributionNetwork = Pool().get('distribution.network')
        if 'code' not in kwargs:
            kwargs['code'] = coop_string.slugify(
                kwargs['name'])
        return DistributionNetwork(**kwargs)

    @classmethod
    def new_distribution_network(cls, name, children_name=None,
            children_number=None):
        res = cls.create_distribution_network(name=name, childs=[])
        if children_name and children_number:
            for i in range(1, children_number + 1):
                child = cls.new_distribution_network('%s %s' %
                    (children_name, i))
                res.childs.append(child)
        return res

    @classmethod
    def distribution_network_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        root = cls.new_distribution_network(translater('Root'))

        internal_network = cls.new_distribution_network(translater(
                'Internal Network'), translater('Region'), 2)
        root.childs.append(internal_network)
        for region in internal_network.childs:
            for i in range(1, random.randint(1, 3)):
                name = '%s : %s %s' % (region.name, translater('Dept'), i)
                department = cls.new_distribution_network(name, '%s %s' %
                    (name, translater('Agency')), random.randint(1, 5), True)
                region.childs.append(department)
        partner = cls.new_distribution_network(
            translater('Commercial Partners'), translater('Partner'),
            random.randint(1, 3), True)
        root.childs.append(partner)
        for sub_partner in partner.childs:
            for i in range(1, random.randint(1, 3)):
                name = '%s : %s %s' % (sub_partner.name, translater('Dept'), i)
                department = cls.new_distribution_network(name,
                    '%s %s' % (name, translater('broker')),
                    random.randint(1, 20), True)
                sub_partner.childs.append(department)
        other = cls.new_distribution_network(translater('Open World'),
            translater('Broker'), 30, True)
        root.childs.append(other)
        root.save()

    @classmethod
    def distribution_network_test_case_test_method(cls):
        translater = cls.get_translater(MODULE_NAME)
        DistributionNetwork = Pool().get('distribution.network')
        return len(DistributionNetwork.search(
                [('name', '=', translater('Root'))])) == 0
