from trytond.pool import PoolMeta
from trytond.pyson import Eval, Less

from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta

__all__ = [
    'Party',
    'PartyInteraction',
    ]


class Party:
    __name__ = 'party.party'

    claims = fields.One2Many('claim', 'claimant', 'Claims', readonly=True)
    number_of_claims = fields.Function(
        fields.Integer('Number Of Claims', states={'invisible': True}),
        'on_change_with_number_of_claims')
    last_claim = fields.Function(
        fields.Many2One('claim', 'Last Claim'),
        'get_last_claim_id')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._buttons.update({
                'open_claims': {
                    'invisible': Less(Eval('number_of_claims', 0), 1, True),
                    },
                })

    @classmethod
    def _export_light(cls):
        return super(Party, cls)._export_light() | {'claims'}

    @fields.depends('claims')
    def on_change_with_number_of_claims(self, name=None):
        return len(self.claims)

    @classmethod
    @model.CoopView.button_action('claim.act_claims_button')
    def open_claims(cls, objs):
        pass

    def get_last_claim_id(self, name):
        return self.claims[-1].id if self.claims else None

    @staticmethod
    def default_number_of_claims():
        return 0


class PartyInteraction:
    __name__ = 'party.interaction'

    @classmethod
    def __setup__(cls):
        super(PartyInteraction, cls).__setup__()
        cls.for_object_ref.selection.append(['claim', 'Claim'])
