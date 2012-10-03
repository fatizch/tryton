#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime

from proteus import Model, Wizard


def launch_test_case(cfg_dict):
    Party = Model.get('party.person')
    Product = Model.get('ins_product.product')
    on_party, = Party.find(limit=1)
    on_product, = Product.find([('code', '=', 'AAA')], limit=1)
    wizard = Wizard('ins_contract.subs_process')
    wizard._config._context['from_session'] = wizard.session_id
    wizard._config.context['from_session'] = wizard.session_id
    wizard.form.start_date += datetime.timedelta(days=2)
    wizard.form.subscriber = on_party.party
    wizard.form.product = on_product
    wizard.execute('steps_next')
    wizard.form.options[0].start_date += \
        datetime.timedelta(days=-4)
    wizard.form.options[0].start_date += \
        datetime.timedelta(days=5)
    wizard.form.options[1].start_date += \
        datetime.timedelta(days=-1)
    wizard.form.options[1].start_date += \
        datetime.timedelta(days=1)
    wizard.execute('steps_next')
    wizard.execute('steps_next')
    wizard.execute('steps_complete')
