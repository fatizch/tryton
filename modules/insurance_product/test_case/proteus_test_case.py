#!/usr/bin/env python
# -*- coding: utf-8 -*-


from proteus import Model
import proteus_tools


def update_models(cfg_dict):
    cfg_dict['EligibilityRule'] = Model.get('ins_product.eligibility_rule')


def migrate_eligibility_rules(cfg_dict):
    for rule in cfg_dict['EligibilityRule'].find(
        [
            'OR',
            [('subscriber_classes', '=', 'party.person')],
            [('subscriber_classes', '=', 'party.party')],
            [('subscriber_classes', '=', 'party.company')],
        ]):
        if rule.subscriber_classes == 'party.person':
            rule.subscriber_classes = 'person'
        elif rule.subscriber_classes == 'party.society':
            rule.subscriber_classes = 'company'
        elif rule.subscriber_classes == 'society':
            rule.subscriber_classes = 'company'
        elif rule.subscriber_classes == 'party.party':
            rule.subscriber_classes = 'all'
        rule.save()


def launch_test_case(cfg_dict):
    update_models(cfg_dict)
    proteus_tools.set_global_search('ins_product.product')
    migrate_eligibility_rules(cfg_dict)
