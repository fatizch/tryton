#!/usr/bin/env python
# -*- coding: utf-8 -*-

import proteus_tools

from proteus import Model


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['User'] = Model.get('res.user')
    cfg_dict['Priority'] = Model.get('task_manager.priority')
    cfg_dict['Team'] = Model.get('task_manager.team')
    cfg_dict['Status'] = Model.get('process.status')
    cfg_dict['Group'] = Model.get('res.group')
    cfg_dict['ModelAccess'] = Model.get('ir.model.access')
    cfg_dict['FieldAccess'] = Model.get('ir.model.field.access')
    cfg_dict['MenuAccess'] = Model.get('ir.ui.menu-res.group')
    cfg_dict['Model'] = Model.get('ir.model')
    cfg_dict['Field'] = Model.get('ir.model.field')
    cfg_dict['ModelData'] = Model.get('ir.model.data')
    cfg_dict['ProcessDesc'] = Model.get('process.process_desc')
    cfg_dict['StepDesc'] = Model.get('process.step_desc')
    cfg_dict['Menu'] = Model.get('ir.ui.menu')
    cfg_dict['Priority'] = Model.get('task_manager.priority')
    cfg_dict['ProcessStepRelation'] = Model.get(
        'process.process_step_relation')


def create_methods(cfg_dict):
    res = {}
    res['Model'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Model', 'model', only_get=True)
    res['Group'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Group', 'name')
    res['ModelAccess'] = proteus_tools.generate_creation_method(
        cfg_dict, 'ModelAccess', domain=['model', 'group'])
    res['ModelData'] = proteus_tools.generate_creation_method(
        cfg_dict, 'ModelData', domain=['module', 'fs_id'], only_get=True)
    res['MenuAccess'] = proteus_tools.generate_creation_method(
        cfg_dict, 'MenuAccess', domain=['menu', 'group'], only_get=True)
    res['Field'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Field', domain=['name', 'model'], only_get=True)
    res['ProcessDesc'] = proteus_tools.generate_creation_method(
        cfg_dict, 'ProcessDesc', 'technical_name', only_get=True)
    res['User'] = proteus_tools.generate_creation_method(
        cfg_dict, 'User', 'login')
    res['FieldAccess'] = proteus_tools.generate_creation_method(
        cfg_dict, 'FieldAccess', domain=['field', 'group'])
    res['StepDesc'] = proteus_tools.generate_creation_method(
        cfg_dict, 'StepDesc', 'technical_name', only_get=True)
    res['Team'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Team', 'code')
    res['Priority'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Priority', domain=['process_step', 'team'])
    res['ProcessStepRelation'] = proteus_tools.generate_creation_method(
        cfg_dict, 'ProcessStepRelation', domain=['process', 'step'],
        only_get=True)

    return res


def launch_test_case(cfg_dict):
    update_cfg_dict_with_models(cfg_dict)
    meths = create_methods(cfg_dict)
    translater = proteus_tools.translate_this(cfg_dict)

    admin_user = meths['User']({
        'login': 'admin',
    })

    product_mod = meths['Model']({
        'model': 'ins_product.product',
    })

    coverage_mod = meths['Model']({
        'model': 'ins_product.coverage',
    })

    society_mod = meths['Model']({
        'model': 'party.society',
    })

    subs_process = meths['ProcessDesc']({
        'technical_name': 'individual_subscription',
    })

    contract_admin_grp = meths['Group']({
        'name': translater('Contract Administration'),
        'menu_access': [
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_contract',
                'fs_id': 'menu_contract'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_contract',
                'fs_id': 'menu_individual'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_contract',
                'fs_id': 'menu_contract_form'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_product'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_product_form'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_coverage_form'}).db_id),
            subs_process.menu_item,
        ],
        'users': [admin_user],
    })

    meths['ModelAccess']({
        'model': product_mod,
        'group': contract_admin_grp,
        'perm_read': True,
    })

    meths['ModelAccess']({
        'model': coverage_mod,
        'group': contract_admin_grp,
        'perm_read': True,
    })

    meths['ModelAccess']({
        'model': society_mod,
        'group': contract_admin_grp,
        'perm_read': True,
        'perm_write': True,
        'perm_create': True,
        'perm_delete': True,
    })

    coverage_mod = meths['Model']({
        'model': 'ins_product.coverage',
    })

    menu_mod = meths['Model']({
        'model': 'ir.ui.menu',
    })

    act_win_mod = meths['Model']({
        'model': 'ir.action.act_window',
    })

    param_grp = meths['Group']({
        'name': translater('Functional Admin'),
        'menu_access': [
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_product'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_product_form'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_product_configuration'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_product_configuration'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'rule_engine',
                'fs_id': 'menu_rule_engine'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_model_clause'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_model_coop_schema'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_product',
                'fs_id': 'menu_coverage_form'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'party',
                'fs_id': 'menu_configuration'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_collective',
                'fs_id': 'menu_coverage_form'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'insurance_collective',
                'fs_id': 'menu_product_form'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'process',
                'fs_id': 'process_menu_id'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'process',
                'fs_id': 'menu_process_status'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'process',
                'fs_id': 'menu_process_desc'}).db_id),
            cfg_dict['Menu'](meths['ModelData']({
                'module': 'process',
                'fs_id': 'menu_step_desc'}).db_id),
            subs_process.menu_item,
        ],
        'users': [admin_user],
    })

    meths['ModelAccess']({
        'model': product_mod,
        'group': param_grp,
        'perm_read': True,
        'perm_write': True,
        'perm_create': True,
        'perm_delete': True,
    })

    meths['ModelAccess']({
        'model': coverage_mod,
        'group': param_grp,
        'perm_read': True,
        'perm_write': True,
        'perm_create': True,
        'perm_delete': True,
    })

    meths['ModelAccess']({
        'model': menu_mod,
        'group': param_grp,
        'perm_read': True,
        'perm_write': True,
        'perm_create': True,
        'perm_delete': True,
    })

    meths['ModelAccess']({
        'model': act_win_mod,
        'group': param_grp,
        'perm_read': True,
        'perm_write': True,
        'perm_create': True,
        'perm_delete': True,
    })

    menu_item_fld = meths['Field']({
        'model': meths['Model']({
            'model': 'process.process_desc',
        }),
        'name': 'menu_item',
    })

    meths['FieldAccess']({
        'field': menu_item_fld,
        'group': param_grp,
        'perm_read': True,
        'perm_write': True,
        'perm_create': True,
        'perm_delete': True,
    })

    param_user = meths['User']({
        'login': 'param',
        'password': 'param',
        'name': translater('Lab Manager'),
        'groups': [
            param_grp,
        ]})

    ctr_adm_user = meths['User']({
        'login': 'contract',
        'password': 'contract',
        'name': translater('Contract Administrator'),
        'groups': [
            contract_admin_grp,
        ]})

    ctr_valid_grp = meths['Group']({
        'name': translater('Contract Validation'),
        'users': [admin_user],
    })

    ctr_validation_user = meths['User']({
        'login': 'contract_validation',
        'password': 'contract_validation',
        'name': translater('Contract Validation'),
        'groups': [
            contract_admin_grp,
            ctr_valid_grp,
        ]})

    valid_step = meths['StepDesc']({
        'technical_name': 'ctr_validation'
    })

    proteus_tools.proteus_append_extend(
        valid_step, 'authorizations', ctr_valid_grp)

    valid_step.save()

    basic_team = meths['Team']({
        'name': translater('Contract Data Team'),
        'code': 'ctr_data_team',
        'members': [ctr_adm_user],
        'priorities': [
            meths['Priority']({
                'priority': 1,
                'process_step': meths['ProcessStepRelation']({
                    'process': subs_process,
                    'step': meths['StepDesc']({
                        'technical_name': 'pricing'}),
                }),
            }),
            meths['Priority']({
                'priority': 2,
                'process_step': meths['ProcessStepRelation']({
                    'process': subs_process,
                    'step': meths['StepDesc']({
                        'technical_name': 'covered_person_selection'}),
                }),
            }),
            meths['Priority']({
                'priority': 3,
                'process_step': meths['ProcessStepRelation']({
                    'process': subs_process,
                    'step': meths['StepDesc']({
                        'technical_name': 'option_selection'}),
                }),
            }),
            meths['Priority']({
                'priority': 4,
                'process_step': meths['ProcessStepRelation']({
                    'process': subs_process,
                    'step': meths['StepDesc']({
                        'technical_name': 'subscriber_selection'}),
                }),
            }),
        ],
    })

    valid_team = meths['Team']({
        'name': translater('Validation Team'),
        'code': 'ctr_valid_team',
        'members': [ctr_validation_user],
        'priorities': [
            meths['Priority']({
                'priority': 1,
                'process_step': meths['ProcessStepRelation']({
                    'process': subs_process,
                    'step': meths['StepDesc']({
                        'technical_name': 'ctr_validation'}),
                }),
            }),
        ],
    })
