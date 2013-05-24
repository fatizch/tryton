import random
from proteus import Model
import proteus_tools


def update_models(cfg_dict):
    cfg_dict['DistributionNetwork'] = Model.get(
        'distribution.dist_network')


def create_dist_network(cfg_dict, name, parent=None,
        children_name=None, children_nb=None):
    res = cfg_dict['DistributionNetwork']()
    res.name = name
    if parent:
        res.parent = parent
    res.save()
    if not children_name or not children_nb:
        return res
    for i in range(1, children_nb + 1):
        create_dist_network(cfg_dict, '%s %s' % (children_name, i),
            res)
    return res


def create_dist_networks(cfg_dict):
    if proteus_tools.get_objects_from_db(cfg_dict, 'DistributionNetwork',
            key='name', value='Root'):
        return
    root = create_dist_network(cfg_dict, 'Root')
    internal_network = create_dist_network(cfg_dict,
        'Internal Network', root, 'Region', random.randint(1, 3))
    for region in internal_network.childs:
        for i in range(1, random.randint(1, 5)):
            name = '%s : Dept %s' % (region.name, i)
            create_dist_network(cfg_dict, name, region,
                '%s Agency' % name, random.randint(1, 10))
    partner = create_dist_network(cfg_dict, 'Commercials Partners',
        root, 'Partner', random.randint(1, 5))
    for sub_partner in partner.childs:
        for i in range(1, random.randint(1, 5)):
            name = '%s : Dept %s' % (sub_partner.name, i)
            create_dist_network(cfg_dict, name, sub_partner,
                '%s broker' % name, random.randint(1, 50))

    create_dist_network(cfg_dict, 'Open World',
        root, 'Broker', 100)


def launch_test_case(cfg_dict):
    update_models(cfg_dict)
    create_dist_networks(cfg_dict)
