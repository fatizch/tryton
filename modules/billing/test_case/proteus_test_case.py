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


def create_methods(cfg_dict):
    res = {}
    res['Account'] = proteus_tools.generate_creation_method(
        cfg_dict, 'Account', 'name')
    res['AccountType'] = proteus_tools.generate_creation_method(
        cfg_dict, 'AccountType', 'name')
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
    company = proteus_tools.get_or_create_company(cfg_dict, 'Mother House')

    tax_account_kind = meths['AccountType'](
        {'name': 'Tax Account', 'company': company},
    )
    fee_account_kind = meths['AccountType'](
        {'name': 'Fee Account', 'company': company},
    )
    kinds = {'tax': tax_account_kind, 'fee': fee_account_kind}

    for type_, data in chain(
            izip(repeat('tax'), cfg_dict['Tax'].find([])),
            izip(repeat('fee'), cfg_dict['Fee'].find([]))):
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

    for i in range(10):
        post_move_seq = meths['Sequence'](
            {
                'name': 'Post Move (%i)' % (2010 + i),
                'code': 'account.move',
            },
            {'company': company.id},
        )
        invoice_seq = meths['SequenceStrict'](
            {
                'name': 'Invoice (%i)' % (2010 + i),
                'code': 'account.invoice',
            },
            {'company': company.id},
        )
        fisc_year = meths['FiscalYear']({
            'name': 'Fiscal Year %s' % str(2010 + i),
            'start_date': datetime.date(2010 + i, 1, 1),
            'end_date': datetime.date(2010 + i, 12, 31),
            'code': 'FY%i' % i,
            'post_move_sequence': post_move_seq,
            'in_invoice_sequence': invoice_seq,
            'out_invoice_sequence': invoice_seq,
            'in_credit_note_sequence': invoice_seq,
            'out_credit_note_sequence': invoice_seq})
        cfg_dict['FiscalYear'].create_period([fisc_year.id],
            {'company': company.id})
