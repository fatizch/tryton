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
    cfg_dict['Code'] = Model.get('process.code')


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
    res['Code'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Code', domain=[
            'parent_step', 'parent_transition', 'method_name',
            'technical_kind'])

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

    contract_model = Model.get('ir.model').find(
        [('model', '=', 'contract.contract')])[0]

    subscriber_sel_step = meths['StepDesc']({
        'technical_name': 'subscriber_selection',
        'fancy_name': translater('Subscriber Selection'),
        'main_model': contract_model,
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
  <field name="subscriber_as_company"/>
</group>
<newline/>
<field name="product_desc" widget="richtext" colspan="2"/>
<field name="subscriber_desc" widget="richtext" colspan="2"/>
''',
    })
    option_sel_step = meths['StepDesc']({
        'technical_name': 'option_selection',
        'fancy_name': translater('Options Selection'),
        'main_model': contract_model,
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
        'main_model': contract_model,
        'step_xml': '''
<field name="covered_elements" group="covered_elements" mode="tree"
 view_ids="insurance_contract.covered_elements_clean_tree"
 xexpand="0" xfill="0"/>
<field name="covered_elements" group="covered_elements" mode="form"
 relation="ins_contract.covered_element" relation_field="contract"
 view_ids="insurance_contract.covered_element_view_form"/>
<field name="covered_elements" group="covered_elements" mode="form"
 relation="ins_contract.covered_data" relation_field="covered_element"
 view_ids="insurance_contract.covered_data_view_form"/>
  ''',
    })
    document_step = meths['StepDesc']({
        'technical_name': 'contract_document_request',
        'fancy_name': translater('Document Request'),
        'main_model': contract_model,
        'step_xml': '''
<field name="documents" xfill="1" xexpand="1" yfill="1" \
yexpand="1" mode="form"/>
<field name="doc_received" invisible="1"/>
''',
    })
    pricing_step = meths['StepDesc']({
        'technical_name': 'pricing',
        'fancy_name': translater('Pricing'),
        'main_model': contract_model,
        'step_xml': '''
<field name="billing_manager" mode="form" />
''',
    })
    validation_step = meths['StepDesc']({
        'technical_name': 'ctr_validation',
        'fancy_name': translater('Contract Validation'),
        'main_model': contract_model,
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

    subs_process_desc = meths['ProcessDesc']({
        'technical_name': 'individual_subscription',
        'fancy_name': translater('Individual Subscription Process'),
        'on_model': contract_model,
        'start_date': cfg_dict['Date'].today({}),
        'kind': 'subscription',
        'custom_transitions': True,
        'steps_implicitly_available': False,
        'xml_tree': '''
<field name="current_state"/>
<field name="contract_number"/>
<field name="subscriber"/>
<field name="status"/>
<field name="start_date"/>
<field name="offered"/>
''',
        'step_button_group_position': 'right',
    })

    meths['ProcessStepRelation'](
        {
            'process': subs_process_desc,
            'step': subscriber_sel_step,
            'status': status_basic_data,
            'order': 1,
        },
        {'process_model': contract_model.id})

    meths['ProcessStepRelation'](
        {
            'process': subs_process_desc,
            'step': option_sel_step,
            'status': status_ongoing,
            'order': 2,
        },
        {'process_model': contract_model.id})

    meths['ProcessStepRelation'](
        {
            'process': subs_process_desc,
            'step': covered_pers_sel_step,
            'status': status_ongoing,
            'order': 3,
        },
        {'process_model': contract_model.id})

    meths['ProcessStepRelation'](
        {
            'process': subs_process_desc,
            'step': document_step,
            'status': status_ongoing,
            'order': 4,
        },
        {'process_model': contract_model.id})

    meths['ProcessStepRelation'](
        {
            'process': subs_process_desc,
            'step': pricing_step,
            'status': status_ongoing,
            'order': 5,
        },
        {'process_model': contract_model.id})

    meths['ProcessStepRelation'](
        {
            'process': subs_process_desc,
            'step': validation_step,
            'status': status_validation,
            'order': 6,
        },
        {'process_model': contract_model.id})

    trans1 = meths['StepTransition'](
        {
            'from_step': subscriber_sel_step,
            'to_step': option_sel_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_product_not_null',
        'parent_transition': trans1,
        'sequence': 1,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_subscriber_not_null',
        'parent_transition': trans1,
        'sequence': 2,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_start_date_valid',
        'parent_transition': trans1,
        'sequence': 3,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_product_eligibility',
        'parent_transition': trans1,
        'sequence': 4,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'init_options',
        'parent_transition': trans1,
        'sequence': 5,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'init_complementary_data',
        'parent_transition': trans1,
        'sequence': 6,
    })
    trans2 = meths['StepTransition'](
        {
            'from_step': subscriber_sel_step,
            'to_step': covered_pers_sel_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_product_not_null',
        'parent_transition': trans2,
        'sequence': 1,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_subscriber_not_null',
        'parent_transition': trans2,
        'sequence': 2,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_start_date_valid',
        'parent_transition': trans2,
        'sequence': 3,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_product_eligibility',
        'parent_transition': trans2,
        'sequence': 4,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'init_options',
        'parent_transition': trans2,
        'sequence': 5,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'init_complementary_data',
        'parent_transition': trans2,
        'sequence': 6,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_options_eligibility',
        'parent_transition': trans2,
        'sequence': 8,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_option_selected',
        'parent_transition': trans2,
        'sequence': 9,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_option_dates',
        'parent_transition': trans2,
        'sequence': 10,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'init_covered_elements',
        'parent_transition': trans2,
        'sequence': 11,
    })
    meths['StepTransition'](
        {
            'from_step': option_sel_step,
            'to_step': subscriber_sel_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    trans3 = meths['StepTransition'](
        {
            'from_step': option_sel_step,
            'to_step': covered_pers_sel_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_options_eligibility',
        'parent_transition': trans3,
        'sequence': 1,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_option_selected',
        'parent_transition': trans3,
        'sequence': 2,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_option_dates',
        'parent_transition': trans3,
        'sequence': 3,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'init_covered_elements',
        'parent_transition': trans3,
        'sequence': 4,
    })
    meths['StepTransition'](
        {
            'from_step': covered_pers_sel_step,
            'to_step': subscriber_sel_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    meths['StepTransition'](
        {
            'from_step': covered_pers_sel_step,
            'to_step': option_sel_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    trans4 = meths['StepTransition'](
        {
            'from_step': covered_pers_sel_step,
            'to_step': document_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_at_least_one_covered',
        'parent_transition': trans4,
        'sequence': 1,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_sub_elem_eligibility',
        'parent_transition': trans4,
        'sequence': 2,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'check_covered_amounts',
        'parent_transition': trans4,
        'sequence': 3,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'init_subscription_document_request',
        'parent_transition': trans4,
        'sequence': 4,
    })
    meths['StepTransition'](
        {
            'from_step': document_step,
            'to_step': covered_pers_sel_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    trans5 = meths['StepTransition'](
        {
            'from_step': document_step,
            'to_step': pricing_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'init_billing_manager',
        'parent_transition': trans5,
        'sequence': 1,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'calculate_prices',
        'parent_transition': trans5,
        'sequence': 2,
    })
    meths['StepTransition'](
        {
            'from_step': pricing_step,
            'to_step': document_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    meths['StepTransition'](
        {
            'from_step': pricing_step,
            'to_step': validation_step,
            'on_process': subs_process_desc,
        },
        {'process_model': contract_model.id})
    trans6 = meths['StepTransition'](
        {
            'from_step': validation_step,
            'on_process': subs_process_desc,
            'kind': 'complete',
        },
        {'process_model': contract_model.id})
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'activate_contract',
        'parent_transition': trans6,
        'sequence': 1,
    })
    meths['Code']({
        'technical_kind': 'transition',
        'on_model': contract_model,
        'method_name': 'finalize_contract',
        'parent_transition': trans6,
        'sequence': 2,
    })

    cfg_dict['ProcessDesc'].update_view([subs_process_desc.id], {})
