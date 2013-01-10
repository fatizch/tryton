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


def get_or_create_this(cfg_dict, class_key, data, sel_val='', domain=None,
        to_store=True):
    if sel_val:
        the_object = proteus_tools.get_objects_from_db(
            cfg_dict, class_key, sel_val, data[sel_val])
    elif domain:
        the_object = proteus_tools.get_objects_from_db(
            cfg_dict, class_key, domain=domain)

    if the_object:
        return the_object

    the_object = cfg_dict[class_key]()

    for key, value in data.iteritems():
        setattr(the_object, key, value)

    if to_store:
        the_object.save()

    return the_object


def get_or_create_status(cfg_dict, data):
    status = proteus_tools.get_objects_from_db(
        cfg_dict, 'Status', 'code', data['code'])
    if status:
        return status

    status = cfg_dict['Status']()

    for key, value in data.iteritems():
        setattr(status, key, value)

    status.save()

    return status


def get_or_create_step_desc(cfg_dict, data):
    step = proteus_tools.get_objects_from_db(
        cfg_dict, 'StepDesc', 'technical_name', data['technical_name'])
    if step:
        return step

    step = cfg_dict['StepDesc']()

    for key, value in data.iteritems():
        setattr(step, key, value)

    step.save()

    return step


def get_or_create_transition(cfg_dict, data):
    trans = proteus_tools.get_objects_from_db(
        cfg_dict, 'StepTransition', domain=[
            ('from_step', '=', data['from_step'].id),
            ('to_step', '=', data['to_step'].id)])
    if trans:
        return trans

    trans = cfg_dict['StepTransition']()

    for key, value in data.iteritems():
        setattr(trans, key, value)

    trans.save()

    return trans


def get_or_create_process_desc(cfg_dict, data):
    process = proteus_tools.get_objects_from_db(
        cfg_dict, 'ProcessDesc', 'technical_name', data['technical_name'])
    if process:
        return process

    process = cfg_dict['ProcessDesc']()

    for key, value in data.iteritems():
        setattr(process, key, value)

    process.save()

    return process
    

def get_or_create_process_step_relation(cfg_dict, data):
    relation = proteus_tools.get_objects_from_db(
        cfg_dict, 'ProcessStepRelation', domain=[
            ('process', '=', data['process'].id),
            ('step', '=', data['step'].id)])
    if relation:
        return relation

    relation = cfg_dict['ProcessStepRelation']()

    for key, value in data.iteritems():
        setattr(relation, key, value)

    relation.save()

    return relation


def launch_test_case(cfg_dict):
    update_cfg_dict_with_models(cfg_dict)
    status_ongoing = get_or_create_status(
        cfg_dict, {
            'code': 'ctr_ongoing',
            'name': 'On going',
        })
    status_validated = get_or_create_status(
        cfg_dict, {
            'code': 'ctr_validated', 
            'name': 'Validated',
        })
    subscriber_sel_step = get_or_create_step_desc(
        cfg_dict, {
            'technical_name': 'subscriber_selection',
            'fancy_name': 'Subscriber Selection',
            'step_xml': '''
<label name="start_date"/>
<field name="start_date" xfill="1"/>
<newline/>
<label name="product"/>
<field name="product" xfill="1" colspan="3"/>
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
<field name="subscriber_desc" widget="richtext" colspan="2"/>
<field name="product_desc" widget="richtext" colspan="2"/>
''',
        })
    option_sel_step = get_or_create_step_desc(
        cfg_dict, {
            'technical_name': 'option_selection',
            'fancy_name': 'Options Selection',
            'step_xml': '''
<field name="options" mode="tree" 
 view_ids="insurance_contract_subscription.subscription_editable_option_tree"/>
<newline/>
<field name="dynamic_data"/>
''',
        })
    covered_pers_sel_step = get_or_create_step_desc(
        cfg_dict, {
            'technical_name': 'covered_person_selection',
            'fancy_name': 'Covered Person Selection',
            'step_xml': '''
<field name="extension_life"  expand_toolbar="0" mode="form" 
  view_ids="life_contract_subscription.subscription_extension_life_form"/>
  ''',
        })
    pricing_step = get_or_create_step_desc(
        cfg_dict, {
            'technical_name': 'pricing',
            'fancy_name': 'Pricing',
            'step_xml': '''
<field name="billing_manager" mode="form" />
''',
        })
    validation_step = get_or_create_step_desc(
        cfg_dict, {
            'technical_name': 'ctr_validation',
            'fancy_name': 'Contract Validation',
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
  <label name="product"/>
  <field name="product"/>
</group>
<notebook colspan="4">
  <page string="Options" id="options">
    <field name="options"/>
  </page>
  <page string="Billing" id="billing">
    <field name="billing_manager" mode="form"/>
  </page>
  <page string="Complementary Data" id="dynamic_data">
    <field name="dynamic_data"/>
  </page>
</notebook>
''',
        })
    get_or_create_transition(cfg_dict, {
        'from_step': subscriber_sel_step,
        'to_step': option_sel_step,
        'kind': 'next',
        'methods': '''
check_product_not_null
check_subscriber_not_null
check_start_date_valid
check_product_eligibility
init_dynamic_data
init_options
''',
        })
    get_or_create_transition(cfg_dict, {
        'from_step': subscriber_sel_step,
        'to_step': covered_pers_sel_step,
        'kind': 'next',
        'methods': '''
check_product_not_null
check_subscriber_not_null
check_start_date_valid
check_product_eligibility
init_dynamic_data
init_options
check_options_eligibility
check_option_selected
check_option_dates
init_extensions
''',
        })
    get_or_create_transition(cfg_dict, {
        'from_step': option_sel_step,
        'to_step': subscriber_sel_step,
        'kind': 'previous',
        })
    get_or_create_transition(cfg_dict, {
        'from_step': option_sel_step,
        'to_step': covered_pers_sel_step,
        'kind': 'next',
        'methods': '''
check_options_eligibility
check_option_selected
check_option_dates
init_extensions
''',
        })
    get_or_create_transition(cfg_dict, {
        'from_step': covered_pers_sel_step,
        'to_step': subscriber_sel_step,
        'kind': 'previous',
        })
    get_or_create_transition(cfg_dict, {
        'from_step': covered_pers_sel_step,
        'to_step': option_sel_step,
        'kind': 'previous',
        })
    get_or_create_transition(cfg_dict, {
        'from_step': covered_pers_sel_step,
        'to_step': pricing_step,
        'kind': 'next',
        'methods': '''
check_at_least_one_covered
check_sub_elem_eligibility
check_covered_amounts
init_billing_manager
calculate_prices
''',
        })
    get_or_create_transition(cfg_dict, {
        'from_step': pricing_step,
        'to_step': covered_pers_sel_step,
        'kind': 'previous',
        })
    get_or_create_transition(cfg_dict, {
        'from_step': pricing_step,
        'to_step': validation_step,
        'kind': 'next',
        'methods': '''
activate_contract
finalize_contract
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

    subs_process_desc = get_or_create_process_desc(cfg_dict, {
        'technical_name': 'individual_subscription',
        'fancy_name': 'Individual Subscription Process',
        'on_model': contract_model,
        'xml_tree': '''
<field name="current_state"/>    
<field name="contract_number"/>
<field name="subscriber"/>
<field name="status"/>
<field name="start_date"/>
<field name="product"/>
''',
        'menu_top': top_menu,
        'first_step': subscriber_sel_step,
        })

    get_or_create_process_step_relation(cfg_dict, {
        'process': subs_process_desc,
        'step': subscriber_sel_step,
        'status': status_ongoing,
        })

    get_or_create_process_step_relation(cfg_dict, {
        'process': subs_process_desc,
        'step': option_sel_step,
        'status': status_ongoing,
        })

    get_or_create_process_step_relation(cfg_dict, {
        'process': subs_process_desc,
        'step': covered_pers_sel_step,
        'status': status_ongoing,
        })

    get_or_create_process_step_relation(cfg_dict, {
        'process': subs_process_desc,
        'step': pricing_step,
        'status': status_ongoing,
        })

    get_or_create_process_step_relation(cfg_dict, {
        'process': subs_process_desc,
        'step': validation_step,
        'status': status_validated,
        })

    cfg_dict['ProcessDesc'].update_view([subs_process_desc.id], {})
