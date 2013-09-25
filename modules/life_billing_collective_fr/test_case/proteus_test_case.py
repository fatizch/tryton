from proteus import Model
import proteus_tools


def update_cfg(cfg_dict):
    cfg_dict['Contract'] = Model.get('contract.contract')
    cfg_dict['Account'] = Model.get('account.account')
    cfg_dict['AccountType'] = Model.get('account.account.type')
    cfg_dict['AccountConfiguration'] = Model.get('account.configuration')
    cfg_dict['Company'] = Model.get('company.company')


def create_methods(cfg_dict):
    res = {}
    res['Account'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Account', sel_keys=['name', 'company'])
    res['AccountType'] = proteus_tools.generate_creation_method(
        cfg_dict, 'AccountType', sel_keys=['name', 'company'])
    return res


def migrate_rate_line(cfg_dict):
    Contract = cfg_dict['Contract']
    Contract.button_calculate_rates([x.id for x in Contract.find(
                [('rates.start_date', '=', None)])], {})


def launch_test_case(cfg_dict):
    meths = create_methods(cfg_dict)
    update_cfg(cfg_dict)
    migrate_rate_line(cfg_dict)
    company, = cfg_dict['Company'].find([('party.name', '=', 'Coop')])
    account_config = cfg_dict['AccountConfiguration'].find([])[0]
    if not account_config.default_suspense_account:
        default_suspense_kind = meths['AccountType'](
            {'name': 'Suspense', 'company': company},
        )
        default_account = meths['Account'](
            {
                'name': 'Default Suspense Account',
                'kind': 'other',
                'type': default_suspense_kind,
            },
            {'company': company.id})
        account_config.default_suspense_account = default_account
        account_config.save()
