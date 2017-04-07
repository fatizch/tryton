# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import company
import res
import ir
import test_case
import party


def register():
    Pool.register(
        company.Company,
        res.User,
        res.Employee,
        ir.Sequence,
        ir.SequenceStrict,
        test_case.TestCaseModel,
        party.PartyConfiguration,
        module='company_cog', type_='model')

    Pool.register_post_init_hooks(set_lang_on_test_create_company,
        module='company_cog')


def set_lang_on_test_create_company(pool, update):
    '''
        Patches company.test.tools::create_company to set a lang on the party
        if it does not exist yet
    '''
    if update:
        return

    from trytond.modules.company.tests import tools

    previous_method = tools.create_company

    def patched_create(*args, **kwargs):
        from proteus import Model
        res_conf = previous_method(*args, **kwargs)
        company = tools.get_company(kwargs.get('config', None))
        if not company.party.lang:
            company.party.lang, = Model.get('ir.lang').find(
                [('code', '=', 'en')])
            company.party.save()
        return res_conf

    tools.create_company = patched_create
