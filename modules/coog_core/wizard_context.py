# This file is part of Coog.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json

from trytond.wizard import Wizard, StateView, StateTransition

from trytond.modules.coog_core import model, fields, jsonrpc


__all__ = [
    'PersistentDataView',
    'PersistentContextWizard',
    ]


class PersistentDataView(model.CoogView):
    'Persistent Data View'

    __name__ = 'wizard.persistent_data.view'

    json_context = fields.Char('JSON Context')


class PersistentContextWizard(Wizard):
    'Persistent Context Wizard'

    context_data = StateView('wizard.persistent_data.view', '', [])
    start = StateTransition()

    def transition_start(self):
        return 'end'

    @property
    def wizard_context(self):
        if hasattr(self, 'loaded_context_'):
            return self.loaded_context_
        if not hasattr(self, 'context_data'):
            self.context_data = getattr(self, 'context_data')
        if not hasattr(self.context_data, 'json_context'):
            self.context_data.json_context = '{}'
        self.loaded_context_ = json.loads(self.context_data.json_context,
            object_hook=jsonrpc.PoolObjectDecoder())
        return self.loaded_context_

    def _save(self):
        self.context_data.json_context = json.dumps(self.wizard_context,
            cls=jsonrpc.PoolObjectEncoder)
        super(PersistentContextWizard, self)._save()
