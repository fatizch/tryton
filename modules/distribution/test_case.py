import random

from trytond.pool import PoolMeta, Pool
from trytond.modules.coop_utils import set_test_case

MODULE_NAME = 'distribution'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    @classmethod
    def create_distribution_network(cls, name, children_name=None,
            children_number=None):
        DistributionNetwork = Pool().get('distribution.dist_network')
        res = DistributionNetwork()
        res.name = name
        res.childs = []
        if not children_name or not children_number:
            return res
        for i in range(1, children_number + 1):
            child = cls.create_distribution_network('%s %s' %
                (children_name, i))
            res.childs.append(child)
        return res

    @classmethod
    @set_test_case('Distribution Network Test Case', 'main_company_test_case')
    def distribution_network_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        DistributionNetwork = Pool().get('distribution.dist_network')
        if DistributionNetwork.search([('name', '=', translater('Root'))]):
            return
        root = cls.create_distribution_network(translater('Root'))
        internal_network = cls.create_distribution_network(translater(
                'Internal Network'), translater('Region'), 2)
        root.childs.append(internal_network)
        for region in internal_network.childs:
            for i in range(1, random.randint(1, 3)):
                name = '%s : %s %s' % (region.name, translater('Dept'), i)
                department = cls.create_distribution_network(name, '%s %s' %
                    (name, translater('Agency')), random.randint(1, 5))
                region.childs.append(department)
        partner = cls.create_distribution_network(
            translater('Commercial Partners'), translater('Partner'),
            random.randint(1, 3))
        root.childs.append(partner)
        for sub_partner in partner.childs:
            for i in range(1, random.randint(1, 3)):
                name = '%s : %s %s' % (sub_partner.name, translater('Dept'), i)
                department = cls.create_distribution_network(name,
                    '%s %s' % (name, translater('broker')),
                    random.randint(1, 20))
                sub_partner.childs.append(department)

        other = cls.create_distribution_network(translater('Open World'),
            translater('Broker'), 30)
        root.childs.append(other)
        return [root]
