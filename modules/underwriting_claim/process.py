# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


__all__ = [
    'UnderwritingStart',
    'UnderwritingStartFindProcess',
    ]


class UnderwritingStart:
    __metaclass__ = PoolMeta
    __name__ = 'underwriting.start'

    @classmethod
    def __setup__(cls):
        super(UnderwritingStart, cls).__setup__()
        cls._error_messages.update({
                'closed_claim': 'Cannot start a new underwriting process '
                'on a closed claim',
                })

    def default_process_parameters(self, name):
        defaults = super(UnderwritingStart, self).default_process_parameters(
            name)
        if Transaction().context.get('active_model') != 'claim':
            return defaults
        claim = Pool().get('claim')(Transaction().context.get('active_id'))
        if claim.status == 'closed':
            self.raise_user_error('closed_claim')
        defaults['parent'] = str(claim)
        defaults['party'] = claim.claimant.id
        return defaults


class UnderwritingStartFindProcess:
    __metaclass__ = PoolMeta
    __name__ = 'underwriting.start.find_process'

    @fields.depends('parent', 'results')
    def on_change_parent(self):
        super(UnderwritingStartFindProcess, self).on_change_parent()
        if (not self.parent or not self.parent.__name__ == 'claim' or
                not self.parent.id >= 0):
            return
        for result in self.results:
            if result.target.startswith('claim.service,'):
                result.selected = True
