from trytond.pool import PoolMeta
from trytond.pyson import Eval, Less

from trytond.modules.coop_utils import model, fields

__metaclass__ = PoolMeta

__all__ = [
    'Party',
    ]


class Party():
    'Party'

    __name__ = 'party.party'

    claims = fields.One2Many('ins_claim.claim', 'claimant', 'Claims')
    number_of_claims = fields.Function(
        fields.Integer('Number Of Claims', on_change_with=['claims'],
            states={'invisible': True}),
        'on_change_with_number_of_claims')
    last_claim = fields.Function(
        fields.Many2One('ins_claim.claim', 'Last Claim'),
        'get_last_claim_id')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._buttons.update({
                'open_claims': {
                    'invisible': Less(Eval('number_of_claims', 0), 1, True),
                    },
                })

    def on_change_with_number_of_claims(self, name=None):
        return len(self.claims)

    @classmethod
    @model.CoopView.button_action('insurance_claim.act_claims_button')
    def open_claims(cls, objs):
        pass

    def get_last_claim_id(self, name):
        return self.claims[-1].id if self.claims else None
