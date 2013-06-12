from proteus import Model
import proteus_tools

from trytond.modules.rule_engine.test_case import create_or_update_folder
from trytond.modules.rule_engine.test_case import append_folder_to_context
from trytond.modules.rule_engine.test_case import get_or_create_context


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['LossDesc'] = Model.get('ins_product.loss_desc')
    cfg_dict['EventDesc'] = Model.get('ins_product.event_desc')
    cfg_dict['Document'] = Model.get('ins_product.document_desc')


def create_loss_desc(cfg_dict, data, event_codes=None, document_codes=None):
    res = proteus_tools.get_or_create_this(
        data, cfg_dict, 'LossDesc', sel_val='code')
    proteus_tools.append_from_key(cfg_dict, res, 'event_descs', 'EventDesc',
        'code', event_codes)
    proteus_tools.append_from_key(cfg_dict, res, 'documents', 'Document',
        'code', document_codes)


def create_loss_descs(cfg_dict):
    create_loss_desc(cfg_dict, {
            'code': 'WI',
            'name': proteus_tools.get_translation('Work Incapacity', cfg_dict),
            'item_kind': 'person',
            'with_end_date': True,
        }, ['AC'], ['WI'])
    create_loss_desc(cfg_dict, {
            'code': 'DH',
            'name': proteus_tools.get_translation('Death', cfg_dict),
            'item_kind': 'person',
        }, ['AC', 'DI'], ['DH'])
    create_loss_desc(cfg_dict, {
            'code': 'DY',
            'name': proteus_tools.get_translation('Disability', cfg_dict),
            'item_kind': 'person',
        }, ['AC', 'DI'], ['DY'])


def create_event_desc(cfg_dict):
    events = []
    events.append({
            'code': 'DI',
            'name': proteus_tools.get_translation('Disease', cfg_dict),
        })
    events.append({
            'code': 'AC',
            'name': proteus_tools.get_translation('Accident', cfg_dict),
        })
    for event in events:
        proteus_tools.get_or_create_this(event, cfg_dict, 'EventDesc',
            'code')


def create_document_descs(cfg_dict):
    documents = []
    documents.append({
            'code': 'WI',
            'name': proteus_tools.get_translation('Work Incapacity', cfg_dict),
        })
    documents.append({
            'code': 'DH',
            'name': proteus_tools.get_translation(
                'Death Certificate', cfg_dict),
        })
    documents.append({
            'code': 'AT',
            'name': proteus_tools.get_translation(
                'Amortization Table', cfg_dict),
        })
    documents.append({
            'code': 'DY',
            'name': proteus_tools.get_translation(
                'Disability Justification', cfg_dict),
        })
    for doc in documents:
        proteus_tools.get_or_create_this(doc, cfg_dict, 'Document', 'code')


def launch_test_case(cfg_dict):
    update_cfg_dict_with_models(cfg_dict)
    proteus_tools.set_global_search('ins_claim.claim')
    create_document_descs(cfg_dict)
    create_event_desc(cfg_dict)
    create_loss_descs(cfg_dict)
    default_context = get_or_create_context(cfg_dict, 'Default Context')
    claim_folder = create_or_update_folder(cfg_dict,
        'ins_product.rule_sets.claim')
    append_folder_to_context(default_context, claim_folder)
