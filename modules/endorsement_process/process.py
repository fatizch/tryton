from trytond.pool import PoolMeta
from trytond.modules.cog_utils import model

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
                'button_start_endorsement_process': {},
                })

    @classmethod
    @model.CoopView.button_action(
        'endorsement_process.endorsement_process_launcher')
    def button_start_endorsement_process(cls, contracts):
        pass
