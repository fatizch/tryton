#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
from optparse import OptionParser
import sys

from proteus import Model, Wizard
from proteus import config as pconfig

TODAY = datetime.date.today()


def set_config(database, password, config_file):
    return pconfig.set_trytond(
        database, password=password,
        database_type='sqlite', config_file=config_file)


def install_modules(config, modules):
    Module = Model.get('ir.module.module')
    modules = Module.find([
        ('name', 'in', modules),
        ('state', '!=', 'installed'),
    ])
    Module.install([x.id for x in modules], config.context)
    modules = [x.name for x in Module.find([('state', '=', 'to install')])]
    Wizard('ir.module.module.install_upgrade').execute('upgrade')

    ConfigWizardItem = Model.get('ir.module.module.config_wizard.item')
    for item in ConfigWizardItem.find([('state', '!=', 'done')]):
        item.state = 'done'
        item.save()

    return modules


def setup_insurance_contract(config):
    Party = Model.get('party.party')
    Product = Model.get('ins_product.product')
    on_party, = Party.find(limit=1)
    on_product, = Product.find([('code', '=', 'AAA')])
    wizard = Wizard('ins_contract.subs_process')
    wizard._config._context['from_session'] = wizard.session_id
    wizard._config.context['from_session'] = wizard.session_id
    wizard.form.start_date += datetime.timedelta(days=2)
    wizard.form.subscriber = on_party
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


def main(database, modules, password, demo_password, config_file):
    config = set_config(database, password, config_file)
    modules = install_modules(config, modules)

    if 'insurance_contract' in modules:
        setup_insurance_contract(config)

    # setup_languages(config, modules, demo_password)

if __name__ == '__main__':
    parser = OptionParser(usage="Usage: %prog [options] <database name>")
    parser.add_option('-p', '--password', dest='password',
        default='admin', help='admin password [default: %default]')
    parser.add_option('-m', '--module', dest='modules', action='append',
        help='module to install', default=[])
    parser.add_option('--demo_password', dest='demo_password',
        default='demo', help='demo password [default: %default]')
    parser.add_option('--config_file', dest='config_file',
        default='', help='tryton server config file [default: %default]')
    options, args = parser.parse_args()
    if len(args) > 1:
        parser.error('Too much args!')
    elif not args:
        parser.error('Not enough args!')
    sys.argv = []  # clean argv for trytond
    database, = args
    main(database, options.modules, options.password, options.demo_password,
        options.config_file)
