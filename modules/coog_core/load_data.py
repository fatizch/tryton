# This file is part of Coog.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.modules.coog_core import model
from trytond.wizard import Wizard, StateTransition, Button, StateView


__all__ = [
    'GlobalSearchSet',
    'GlobalSearchSetWizard',
    'LanguageTranslatableSet',
    'LanguageTranslatableWizard',
    ]


class GlobalSearchSet(model.CoogView):
    'Global Search Set'

    __name__ = 'global_search.set'

    @classmethod
    def global_search_list(cls):
        return set([])


class GlobalSearchSetWizard(Wizard):
    'Global Search Set Wizard'

    __name__ = 'global_search.set.wizard'

    start_state = 'start'

    start = StateView('global_search.set',
        'coog_core.global_search_set_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Set', 'set_', 'tryton-ok', default=True),
            ])
    set_ = StateTransition()

    def transition_set_(self):
        pool = Pool()
        Model = pool.get('ir.model')
        GlobalSearch = pool.get('global_search.set')
        targets = Model.search([
                ('model', 'in', GlobalSearch.global_search_list())])
        Model.write(targets, {'global_search_p': True})
        return 'end'


class LanguageTranslatableSet(model.CoogView):
    'Language Translatable Set'

    __name__ = 'language_translatable.set'


class LanguageTranslatableWizard(Wizard):
    'Set Translatable Wizard'

    __name__ = 'language_translatable.set.wizard'

    start = StateView('language_translatable.set',
        'coog_core.language_translatable_set_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Set', 'set_', 'tryton-ok', default=True),
            ])
    set_ = StateTransition()

    def transition_set_(self):
        Lang = Pool().get('ir.lang')
        langs = Lang.search([
                ('translatable', '=', False),
                ('code', 'in', ['fr', 'en'])])
        # We force the write on existing records, do not use the auto-save on
        # test_case return values
        Lang.write(langs, {'translatable': True})
        return 'end'
