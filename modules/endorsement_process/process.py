# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval, Bool, In
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import model
from trytond.modules.endorsement.endorsement import \
    STATUS_INCOMPATIBLE_WITH_ENDORSEMENTS

__metaclass__ = PoolMeta
__all__ = [
    'Process',
    'Contract',
    ]


class Process:
    __name__ = 'process'

    @classmethod
    def __setup__(cls):
        super(Process, cls).__setup__()
        cls.kind.selection.append(('endorsement', 'Contract Endorsement'))


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_start_endorsement_process': {
                    'invisible': Bool(In(Eval('status'),
                            STATUS_INCOMPATIBLE_WITH_ENDORSEMENTS)),
                    },
                })

    @classmethod
    @model.CoopView.button_action(
        'endorsement_process.endorsement_process_launcher')
    def button_start_endorsement_process(cls, contracts):
        pass
