#!/usr/bin/env python
# -*- coding: utf-8 -*-

import proteus_tools

from proteus import Model


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['Status'] = Model.get('process.status')
    cfg_dict['ProcessStepRelation'] = Model.get(
        'process.process_step_relation')
    cfg_dict['ProcessDesc'] = Model.get('process.process_desc')
    cfg_dict['TransitionAuthorization'] = Model.get(
        'process.transition_authorization')
    cfg_dict['StepTransition'] = Model.get('process.step_transition')
    cfg_dict['StepDesc'] = Model.get('process.step_desc')
    cfg_dict['StepDescAuthorization'] = Model.get(
        'process.step_desc_authorization')


def create_methods(cfg_dict):
    res = {}

    res['Status'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Status', 'code')
    res['StepDesc'] = proteus_tools.generate_creation_method(
        cfg_dict, 'StepDesc', 'technical_name')
    res['StepTransition'] = proteus_tools.generate_creation_method(
        cfg_dict, 'StepTransition', domain=['from_step', 'to_step', 'kind'])
    res['ProcessDesc'] = proteus_tools.generate_creation_method(
        cfg_dict, 'ProcessDesc', 'technical_name')
    res['ProcessStepRelation'] = proteus_tools.generate_creation_method(
        cfg_dict, 'ProcessStepRelation', domain=['process', 'step'])

    return res


def launch_test_case(cfg_dict):
    update_cfg_dict_with_models(cfg_dict)
    meths = create_methods(cfg_dict)
    translater = proteus_tools.translate_this(cfg_dict)

    status_ongoing = meths['Status']({
        'code': 'ctr_ongoing',
        'name': translater('On going'),
    })
    status_validation = meths['Status']({
        'code': 'ctr_validation',
        'name': translater('Validation'),
    })
    status_basic_data = meths['Status']({
        'code': 'ctr_basic_data_input',
        'name': translater('Administrative Data'),
    })
    subscriber_sel_step = meths['StepDesc']({
        'technical_name': 'subscriber_selection',
        'fancy_name': translater('Subscriber Selection'),
        'step_xml': '''
<label name="start_date"/>
<field name="start_date" xfill="1"/>
<newline/>
<label name="offered"/>
<field name="offered" xfill="1" colspan="3"/>
<newline/>
<label name="subscriber_kind"/>
<field name="subscriber_kind" colspan="3"/>
<newline/>
<label name="subscriber"/>
<group id="subscriber" colspan="3" col="1">
  <field name="subscriber_as_person"/>
  <field name="subscriber_as_society"/>
</group>
<newline/>
<field name="product_desc" widget="richtext" colspan="2"/>
<field name="subscriber_desc" widget="richtext" colspan="2"/>
''',
    })
    option_sel_step = meths['StepDesc']({
        'technical_name': 'option_selection',
        'fancy_name': translater('Options Selection'),
        'step_xml': '''
<field name="options" mode="tree"
 view_ids="insurance_contract_subscription.subscription_editable_option_tree"/>
<newline/>
<field name="complementary_data"/>
''',
    })
    covered_pers_sel_step = meths['StepDesc']({
        'technical_name': 'covered_person_selection',
        'fancy_name': translater('Covered Person Selection'),
        'step_xml': '''
<field name="covered_elements"
 mode="form,tree"
 view_ids="life_contract_subscription.subscription_covered_person_form,
life_contract.covered_person_view_tree"/>
  ''',
    })
    document_step = meths['StepDesc']({
        'technical_name': 'contract_document_request',
        'fancy_name': translater('Document Request'),
        'step_xml': '''
<field name="documents" xfill="1" xexpand="1" yfill="1" \
yexpand="1" mode="form"/>
<field name="doc_received" invisible="1"/>
''',
    })
    pricing_step = meths['StepDesc']({
        'technical_name': 'pricing',
        'fancy_name': translater('Pricing'),
        'step_xml': '''
<field name="billing_manager" mode="form" />
''',
    })
    validation_step = meths['StepDesc']({
        'technical_name': 'ctr_validation',
        'fancy_name': translater('Contract Validation'),
        'step_xml': '''
<group id="Administrative data">
  <label name="contract_number"/>
  <field name="contract_number"/>
  <label name="status"/>
  <field name="status"/>
  <label name="start_date"/>
  <field name="start_date"/>
  <newline/>
  <label name="subscriber"/>
  <field name="subscriber"/>
  <label name="offered"/>
  <field name="offered"/>
</group>
<notebook colspan="4">
  <page string="Options" id="options">
    <field name="options"/>
  </page>
  <page string="Billing" id="billing">
    <field name="billing_manager" mode="form"/>
  </page>
  <page string="Complementary Data" id="complementary_data">
    <field name="complementary_data"/>
  </page>
</notebook>
''',
    })

    contract_model = Model.get('ir.model').find(
        [('model', '=', 'ins_contract.contract')])[0]

    top_menu_tmp = Model.get('ir.model.data').find(
        [
            ('module', '=', 'insurance_contract'),
            ('fs_id', '=', 'menu_individual'),
        ])[0]

    top_menu = Model.get('ir.ui.menu')(top_menu_tmp.db_id)

    subs_process_desc = meths['ProcessDesc']({
        'technical_name': 'individual_subscription',
        'fancy_name': translater('Individual Subscription Process'),
        'on_model': contract_model,
        'xml_tree': '''
<field name="current_state"/>
<field name="contract_number"/>
<field name="subscriber"/>
<field name="status"/>
<field name="start_date"/>
<field name="offered"/>
''',
        'menu_top': top_menu,
        'first_step': subscriber_sel_step,
    })

    meths['ProcessStepRelation']({
        'process': subs_process_desc,
        'step': subscriber_sel_step,
        'status': status_basic_data,
        'order': 1,
    })

    meths['ProcessStepRelation']({
        'process': subs_process_desc,
        'step': option_sel_step,
        'status': status_ongoing,
        'order': 2,
    })

    meths['ProcessStepRelation']({
        'process': subs_process_desc,
        'step': covered_pers_sel_step,
        'status': status_ongoing,
        'order': 3,
    })

    meths['ProcessStepRelation']({
        'process': subs_process_desc,
        'step': document_step,
        'status': status_ongoing,
        'order': 4,
    })

    meths['ProcessStepRelation']({
        'process': subs_process_desc,
        'step': pricing_step,
        'status': status_ongoing,
        'order': 5,
    })

    meths['ProcessStepRelation']({
        'process': subs_process_desc,
        'step': validation_step,
        'status': status_validation,
        'order': 6,
    })

    meths['StepTransition']({
        'from_step': subscriber_sel_step,
        'to_step': option_sel_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
        'methods': '''
check_product_not_null
check_subscriber_not_null
check_start_date_valid
check_product_eligibility
init_options
init_complementary_data
''',
    })
    meths['StepTransition']({
        'from_step': subscriber_sel_step,
        'to_step': covered_pers_sel_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
        'methods': '''
check_product_not_null
check_subscriber_not_null
check_start_date_valid
check_product_eligibility
init_options
init_complementary_data
check_options_eligibility
check_option_selected
check_option_dates
init_covered_elements
''',
    })
    meths['StepTransition']({
        'from_step': option_sel_step,
        'to_step': subscriber_sel_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
    })
    meths['StepTransition']({
        'from_step': option_sel_step,
        'to_step': covered_pers_sel_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
        'methods': '''
check_options_eligibility
check_option_selected
check_option_dates
init_covered_elements
''',
    })
    meths['StepTransition']({
        'from_step': covered_pers_sel_step,
        'to_step': subscriber_sel_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
    })
    meths['StepTransition']({
        'from_step': covered_pers_sel_step,
        'to_step': option_sel_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
    })
    meths['StepTransition']({
        'from_step': covered_pers_sel_step,
        'to_step': document_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
        'methods': '''
check_at_least_one_covered
check_sub_elem_eligibility
check_covered_amounts
init_subscription_document_request
''',
    })
    meths['StepTransition']({
        'from_step': document_step,
        'to_step': covered_pers_sel_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
    })
    meths['StepTransition']({
        'from_step': document_step,
        'to_step': pricing_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
        'methods': '''
init_billing_manager
calculate_prices
''',
    })
    meths['StepTransition']({
        'from_step': pricing_step,
        'to_step': document_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
    })
    meths['StepTransition']({
        'from_step': pricing_step,
        'to_step': validation_step,
        'on_process': subs_process_desc,
        'kind': 'standard',
    })
    meths['StepTransition']({
        'from_step': validation_step,
        'on_process': subs_process_desc,
        'kind': 'complete',
        'methods': '''
activate_contract
finalize_contract
''',
    })

    cfg_dict['ProcessDesc'].update_view([subs_process_desc.id], {})
