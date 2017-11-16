#!/usr/bin/env python
import sys

from proteus import config, Model, Wizard

assert len(sys.argv) == 2, 'Missing mandatory parameters "module"'

module = sys.argv[1]


def log_step(info):
    print ' '
    print '#' * 100
    print '#%s#' % info.center(98, ' ')
    print '#' * 100
    print ' '

log_step('Starting trytond instance')

conf = config.set_trytond()

Lang = Model.get('ir.lang')
fr, = Lang.find([('code', '=', 'fr')])
fr.translatable = True
fr.save()

Module = Model.get('ir.module')
to_install = Module.find([('name', '=', module),
        ('state', '=', 'not activated')])

if to_install:
    to_install[0].click('activate')

if to_install:
    log_step('Updating Database')
    wizard = Wizard('ir.module.activate_upgrade')
    wizard.execute('upgrade')

ConfigItem = Model.get('ir.module.config_wizard.item')
for elem in ConfigItem.find([]):
    elem.state = 'done'
    elem.save()

wizard = Wizard('ir.translation.update')
wizard.form.language = Model.get('ir.lang').find([('code', '=', 'fr')])[0]
wizard.execute('update')

log_step('Ready')
