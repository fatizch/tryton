from proteus import Model


def update_cfg(cfg_dict):
    cfg_dict['Contract'] = Model.get('contract.contract')


def migrate_rate_line(cfg_dict):
    Contract = cfg_dict['Contract']
    Contract.button_calculate_rates(Contract.find(
            [('rates.start_date', '=', None)]), {})


def launch_test_case(cfg_dict):
    update_cfg(cfg_dict)
    migrate_rate_line(cfg_dict)
