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

    status_declaration = meths['Status']({
        'code': 'claim_declaration',
        'name': translater('Claim Declaration'),
    })
    status_documents = meths['Status']({
        'code': 'waiting_for_documents',
        'name': translater('Waiting for documents'),
    })
    status_calculation = meths['Status']({
        'code': 'claim_calculation',
        'name': translater('Being calculated'),
    })
    status_validation = meths['Status']({
        'code': 'claim_validation',
        'name': translater('Validation'),
    })
    status_closing = meths['Status']({
        'code': 'claim_closing',
        'name': translater('Closing'),
    })

    claim_model = Model.get('ir.model').find(
        [('model', '=', 'ins_claim.claim')])[0]

    step_claimant = meths['StepDesc']({
        'technical_name': 'claimant',
        'fancy_name': translater('Claimant Selection'),
        'main_model': claim_model,
        'step_xml': '''
<label name="declaration_date"/>
<field name="declaration_date"/>
<newline/>
<label name="claimant"/>
<field name="claimant" colspan="3"/>
<newline/>
<field name="contracts" colspan="2"/>
<field name="contact_history" colspan="2"/>''',
        'code_after': 'set_claim_number',
    })
    step_loss = meths['StepDesc']({
        'technical_name': 'loss',
        'fancy_name': translater('Loss Selection'),
        'main_model': claim_model,
        'step_xml': '''
<label name="name"/>
<field name="name"/>
<label name="status"/>
<field name="status"/>
<label name="claimant"/>
<field name="claimant"/>
<label name="declaration_date"/>
<field name="declaration_date"/>
<field name="losses" colspan="4" mode="form,tree" \
view_ids="insurance_claim_process.loss_view_form,\
insurance_claim.loss_view_tree"/>''',
        'code_before': 'init_loss',
    })
    step_documents = meths['StepDesc']({
        'technical_name': 'required_documents',
        'fancy_name': translater('Documents'),
        'main_model': claim_model,
        'step_xml': '''
<label name="name"/>
<field name="name"/>
<label name="status"/>
<field name="status"/>
<label name="claimant"/>
<field name="claimant"/>
<label name="declaration_date"/>
<field name="declaration_date"/>
<field name="documents" colspan="4" mode="form"/>''',
        'code_before': 'init_declaration_document_request',
    })
    step_delivered_service = meths['StepDesc']({
        'technical_name': 'delivered_services',
        'fancy_name': translater('Delivered Services'),
        'main_model': claim_model,
        'step_xml': '''
<label name="name"/>
<field name="name"/>
<label name="status"/>
<field name="status"/>
<label name="claimant"/>
<field name="claimant"/>
<label name="declaration_date"/>
<field name="declaration_date"/>
<field name="losses" colspan="4" mode="form,tree" expand_toolbar="0" \
view_ids="insurance_claim_process.loss_delivered_services_view_form,\
insurance_claim.loss_view_tree"/>
<field name="doc_received" invisible="1"/>''',
        'code_before': 'init_delivered_services',
    })
    step_indemnification = meths['StepDesc']({
        'technical_name': 'indemnification_calculation',
        'fancy_name': translater('Indemnification Validation'),
        'main_model': claim_model,
        'step_xml': '''
<label name="name"/>
<field name="name"/>
<label name="status"/>
<field name="status"/>
<label name="claimant"/>
<field name="claimant"/>
<label name="declaration_date"/>
<field name="declaration_date"/>
<field name="indemnifications" colspan="4" mode="form,tree" \
expand_toolbar="0" />
''',
        'code_before': 'calculate_indemnification',
        'code_after': 'validate_indemnifications',
    })
    step_disbursment = meths['StepDesc']({
        'technical_name': 'disbursment',
        'fancy_name': translater('Disbursment'),
        'main_model': claim_model,
        'step_xml': '''
<label name="name"/>
<field name="name"/>
<label name="status"/>
<field name="status"/>
<label name="claimant"/>
<field name="claimant"/>
<label name="declaration_date"/>
<field name="declaration_date"/>
<field name="indemnifications" colspan="4" mode="form,tree" \
expand_toolbar="0" />''',
        'code_after': 'validate_indemnifications',
    })
    step_closing = meths['StepDesc']({
        'technical_name': 'closing',
        'fancy_name': translater('Closing'),
        'main_model': claim_model,
        'step_xml': '''
<label name="name"/>
<field name="name"/>
<label name="status"/>
<field name="status"/>
<label name="claimant"/>
<field name="claimant"/>
<label name="declaration_date"/>
<field name="declaration_date"/>
<field name="indemnifications" colspan="4" mode="form,tree" \
expand_toolbar="0" />''',
    })

    prev_product = Model.get('ins_product.product').find(
        [('code', '=', 'PREV')])[0]

    process_claim = meths['ProcessDesc']({
        'technical_name': 'claim_declaration',
        'fancy_name': translater('Claim Declaration'),
        'on_model': claim_model,
        'start_date': cfg_dict['Date'].today({}),
        'kind': 'claim_declaration',
        'for_products': [prev_product],
        'xml_tree': '''
<field name="current_state"/>
<field name="name"/>
<field name="claimant"/>
<field name="status"/>
''',
        'step_button_group_position': 'right',
    })

    meths['ProcessStepRelation'](
        {
            'process': process_claim,
            'step': step_claimant,
            'status': status_declaration,
            'order': 1,
        },
        {'process_model': claim_model.id})
    meths['ProcessStepRelation'](
        {
            'process': process_claim,
            'step': step_loss,
            'status': status_declaration,
            'order': 2,
        },
        {'process_model': claim_model.id})
    meths['ProcessStepRelation'](
        {
            'process': process_claim,
            'step': step_documents,
            'status': status_documents,
            'order': 3,
        },
        {'process_model': claim_model.id})
    meths['ProcessStepRelation'](
        {
            'process': process_claim,
            'step': step_delivered_service,
            'status': status_calculation,
            'order': 4,
        },
        {'process_model': claim_model.id})
    meths['ProcessStepRelation'](
        {
            'process': process_claim,
            'step': step_indemnification,
            'status': status_calculation,
            'order': 5,
        },
        {'process_model': claim_model.id})
    meths['ProcessStepRelation'](
        {
            'process': process_claim,
            'step': step_disbursment,
            'status': status_validation,
            'order': 6,
        },
        {'process_model': claim_model.id})
    meths['ProcessStepRelation'](
        {
            'process': process_claim,
            'step': step_closing,
            'status': status_closing,
            'order': 7,
        },
        {'process_model': claim_model.id})

    meths['StepTransition'](
        {
            'from_step': step_claimant,
            'to_step': step_loss,
            'on_process': process_claim,
            'pyson': "~Eval('contracts')",
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_loss,
            'to_step': step_claimant,
            'on_process': process_claim,
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_loss,
            'to_step': step_documents,
            'on_process': process_claim,
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_documents,
            'to_step': step_loss,
            'on_process': process_claim,
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_documents,
            'to_step': step_claimant,
            'on_process': process_claim,
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_documents,
            'to_step': step_delivered_service,
            'on_process': process_claim,
            'pyson': "~Eval('doc_received')",
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_loss,
            'to_step': step_documents,
            'on_process': process_claim,
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_delivered_service,
            'to_step': step_indemnification,
            'on_process': process_claim,
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_indemnification,
            'to_step': step_delivered_service,
            'on_process': process_claim,
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_indemnification,
            'to_step': step_disbursment,
            'on_process': process_claim,
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_disbursment,
            'to_step': step_closing,
            'on_process': process_claim,
        },
        {'process_model': claim_model.id})
    meths['StepTransition'](
        {
            'from_step': step_closing,
            'on_process': process_claim,
            'kind': 'complete',
        },
        {'process_model': claim_model.id})

    cfg_dict['ProcessDesc'].update_view([process_claim.id], {})
