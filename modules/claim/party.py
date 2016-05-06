import copy
from sql.aggregate import Max
from sql import Literal
from trytond.pool import PoolMeta, Pool
from trytond.pyson import PYSONEncoder
from trytond.wizard import Wizard

from trytond.modules.cog_utils import model, fields, coop_string, UnionMixin

__metaclass__ = PoolMeta

__all__ = [
    'Party',
    'PartyInteraction',
    'SynthesisMenuClaim',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    ]


class Party:
    __name__ = 'party.party'

    claims = fields.One2Many('claim', 'claimant', 'Claims', readonly=True)
    last_claim = fields.Function(
        fields.Many2One('claim', 'Last Claim'),
        'get_last_claim_id')

    @classmethod
    def _export_light(cls):
        return super(Party, cls)._export_light() | {'claims'}

    @classmethod
    @model.CoopView.button_action('claim.act_claims_button')
    def open_claims(cls, objs):
        pass

    def get_last_claim_id(self, name):
        return self.claims[-1].id if self.claims else None


class PartyInteraction:
    __name__ = 'party.interaction'

    @classmethod
    def __setup__(cls):
        super(PartyInteraction, cls).__setup__()
        cls.for_object_ref.selection.append(['claim', 'Claim'])


class SynthesisMenuClaim(model.CoopSQL):
    'Party Synthesis Menu Claim'
    __name__ = 'party.synthesis.menu.claim'

    name = fields.Char('Claims')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        Claim = pool.get('claim')
        ClaimSynthesis = pool.get('party.synthesis.menu.claim')
        party = pool.get('party.party').__table__()
        claim = Claim.__table__()
        query_table = party.join(claim, 'LEFT OUTER', condition=(
            party.id == claim.claimant))
        return query_table.select(
            party.id,
            Max(claim.create_uid).as_('create_uid'),
            Max(claim.create_date).as_('create_date'),
            Max(claim.write_uid).as_('write_uid'),
            Max(claim.write_date).as_('write_date'),
            Literal(coop_string.translate_label(ClaimSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'claim'

    def get_rec_name(self, name):
        ClaimSynthesis = Pool().get('party.synthesis.menu.claim')
        return coop_string.translate_label(ClaimSynthesis, 'name')


class SynthesisMenu(UnionMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def union_models(cls):
        res = super(SynthesisMenu, cls).union_models()
        res.extend([
                'party.synthesis.menu.claim',
                'claim',
                ])
        return res

    @classmethod
    def union_field(cls, name, Model):
        union_field = super(SynthesisMenu, cls).union_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.claim':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'claim':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['claimant'])
                union_field.model_name = 'party.synthesis.menu.claim'
                return union_field
            elif name == 'name':
                return Model._fields['name']
        return union_field

    @classmethod
    def menu_order(cls, model):
        res = super(SynthesisMenu, cls).menu_order(model)
        if model == 'party.synthesis.menu.claim':
            res = 50
        return res


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    def get_action(self, record):
        Model = record.__class__
        if Model.__name__ != 'party.synthesis.menu.claim':
            return super(SynthesisMenuOpen, self).get_action(record)
        domain = PYSONEncoder().encode([('claimant', '=', record.id)])
        actions = {
            'res_model': 'claim',
            'pyson_domain': domain,
            'views': [(Pool().get('ir.ui.view').search([('xml_id', '=',
                    'claim.claim_view_tree')
                        ])[0].id, 'tree'),
                    (Pool().get('ir.ui.view').search([('xml_id', '=',
                        'claim.claim_view_form')
                            ])[0].id, 'form')]
        }
        return actions
