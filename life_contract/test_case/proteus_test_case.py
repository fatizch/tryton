#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime

from proteus import Model, Wizard
from proteus_tools import multiprocess_this


def create_contract(on_party, on_product, date_delta):
    print '%s, %s, %s' % (on_party.party.name, on_product.name,
        date_delta)
    wizard = Wizard('ins_contract.subs_process')
    wizard._config._context['from_session'] = wizard.session_id
    wizard._config.context['from_session'] = wizard.session_id
    wizard.form.start_date += datetime.timedelta(days=date_delta)
    wizard.form.subscriber = on_party.party
    wizard.form.product = on_product
    wizard.execute('steps_next')
    wizard.execute('steps_next')
    wizard.execute('steps_next')
    wizard.execute('steps_complete')


def launch_test_case(cfg_dict):
    the_date = datetime.date.today()
    Party = Model.get('party.person')
    Product = Model.get('ins_product.product')
    on_product, = Product.find([('code', '=', 'AAA')], limit=1)
    on_parties = Party.find()
    the_args = []
    for party in on_parties:
        the_args.append([
            party,
            on_product,
            len(the_args)])

    multiprocess_this(create_contract, the_args, cfg_dict,
        datetime.datetime.now() + datetime.timedelta(days=20))
