#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import datetime
from itertools import repeat, izip, chain

from proteus import Model
import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['Account'] = Model.get('account.account')
    cfg_dict['AccountType'] = Model.get('account.account.type')
    cfg_dict['Tax'] = Model.get('coop_account.tax_desc')
    cfg_dict['Fee'] = Model.get('coop_account.fee_desc')
    cfg_dict['FiscalYear'] = Model.get('account.fiscalyear')
    cfg_dict['Sequence'] = Model.get('ir.sequence')
    cfg_dict['SequenceStrict'] = Model.get('ir.sequence.strict')
    cfg_dict['AccountConfiguration'] = Model.get('account.configuration')
    cfg_dict['Contract'] = Model.get('contract.contract')
    cfg_dict['Company'] = Model.get('company.company')
    cfg_dict['Product'] = Model.get('offered.product')
    cfg_dict['Coverage'] = Model.get('offered.coverage')
    cfg_dict['Journal'] = Model.get('account.journal')


def create_methods(cfg_dict):
    res = {}
    res['Account'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Account', sel_keys=['name', 'company'])
    res['AccountType'] = proteus_tools.generate_creation_method(
        cfg_dict, 'AccountType', sel_keys=['name', 'company'])
    res['FiscalYear'] = proteus_tools.generate_creation_method(
        cfg_dict, 'FiscalYear', 'name')
    res['Sequence'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Sequence', 'name')
    res['SequenceStrict'] = proteus_tools.generate_creation_method(
        cfg_dict, 'SequenceStrict', 'name')
    return res


def launch_test_case(cfg_dict):
    update_cfg_dict_with_models(cfg_dict)
    meths = create_methods(cfg_dict)
    company, = cfg_dict['Company'].find([('party.name', '=', 'Coop')])
    collection_account_kind = meths['AccountType'](
        {'name': 'Collection Account', 'company': company},
    )
    cash_account = meths['Account'](
        {
            'name': 'Cash Account',
            'kind': 'revenue',
            'type': collection_account_kind,
        },
        {'company': company.id},
    )
    check_account = meths['Account'](
        {
            'name': 'Check Account',
            'kind': 'revenue',
            'type': collection_account_kind,
        },
        {'company': company.id},
    )
    company.collection_journal = cfg_dict['Journal'].find(
        [('type', '=', 'cash')])[0]
    company.cash_account = cash_account
    company.check_account = check_account
    company.save()

    cfg_dict['_config'].set_context({'company': company.id})

    bad_contracts = cfg_dict['Contract'].find([('company', '=', None)])
    cfg_dict['Contract'].write([x.id for x in bad_contracts],
        {'company': company.id}, {})

    tax_account_kind = meths['AccountType'](
        {'name': 'Tax Account', 'company': company},
    )
    fee_account_kind = meths['AccountType'](
        {'name': 'Fee Account', 'company': company},
    )
    kinds = {'tax': tax_account_kind, 'fee': fee_account_kind}
    for type_, data in chain(
            izip(repeat('tax'), cfg_dict['Tax'].find(
                [('account_for_billing', '=', None)])),
            izip(repeat('fee'), cfg_dict['Fee'].find(
                [('account_for_billing', '=', None)]))):
        tmp_account = meths['Account'](
            {
                'name': 'Account for %s' % data.code,
                'kind': 'other',
                'type': kinds[type_],
            },
            {'company': company.id},
        )
        data.account_for_billing = tmp_account
        data.save()

    product_account_kind = meths['AccountType']({
        'name': 'Product Account', 'company': company},
    )
    coverage_account_kind = meths['AccountType'](
        {'name': 'Coverage Account', 'company': company},
    )
    kinds = {
        'product': product_account_kind, 'coverage': coverage_account_kind}
    for type_, data in chain(
            izip(repeat('product'), cfg_dict['Product'].find(
                [('account_for_billing', '=', None)])),
            izip(repeat('coverage'), cfg_dict['Coverage'].find(
                [('account_for_billing', '=', None)]))):
        tmp_account = meths['Account'](
            {
                'name': 'Account for %s %s' % (type_, data.name),
                'kind': 'revenue',
                'type': kinds[type_],
            },
            {'company': company.id},
        )
        data.account_for_billing = tmp_account
        data.save()
    existing_fiscal_years = cfg_dict['FiscalYear'].find([])
    if len(existing_fiscal_years) == 0:
        for i in range(10):
            post_move_seq = meths['Sequence'](
                {
                    'name': 'Post Move (%i)' % (2010 + i),
                    'code': 'account.move',
                },
                {'company': company.id},
            )
            fisc_year = meths['FiscalYear'](
                {
                    'name': 'Fiscal Year %s' % str(2010 + i),
                    'start_date': datetime.date(2010 + i, 1, 1),
                    'end_date': datetime.date(2010 + i, 12, 31),
                    'code': 'FY%i' % i,
                    'post_move_sequence': post_move_seq,
                },
                {'company': company.id},
            )
            if len(fisc_year.periods) < 1:
                cfg_dict['FiscalYear'].create_period([fisc_year.id],
                    {'company': company.id})

    account_config = cfg_dict['AccountConfiguration'].find([])[0]
    if not account_config.default_account_receivable:
        default_receivable_kind = meths['AccountType'](
            {'name': 'Client Receivable', 'company': company},
        )
        default_account = meths['Account'](
            {
                'name': 'Default Receivable Account',
                'kind': 'receivable',
                'type': default_receivable_kind,
            },
            {'company': company.id})
        account_config.default_account_receivable = default_account
    if not account_config.default_account_payable:
        default_payable_kind = meths['AccountType'](
            {'name': 'Client Payable', 'company': company},
        )
        default_account = meths['Account'](
            {
                'name': 'Default Payable Account',
                'kind': 'payable',
                'type': default_payable_kind,
            },
            {'company': company.id})
        account_config.default_account_payable = default_account
    account_config.save()
