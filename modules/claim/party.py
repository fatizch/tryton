# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
from sql.aggregate import Max
from sql import Literal
from trytond.pool import PoolMeta, Pool
from trytond.pyson import PYSONEncoder
from trytond.wizard import Wizard

from trytond.modules.coog_core import model, fields, coog_string

__metaclass__ = PoolMeta

__all__ = [
    'Party',
    'SynthesisMenuClaim',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    'InsurerDelegation',
    'PartyReplace',
    ]


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    claims = fields.One2Many('claim', 'claimant', 'Claims', readonly=True)
    last_claim = fields.Function(
        fields.Many2One('claim', 'Last Claim'),
        'get_last_claim_id')

    @classmethod
    def _export_light(cls):
        return super(Party, cls)._export_light() | {'claims'}

    @classmethod
    @model.CoogView.button_action('claim.act_claims_button')
    def open_claims(cls, objs):
        pass

    def get_last_claim_id(self, name):
        return self.claims[-1].id if self.claims else None


class SynthesisMenuClaim(model.CoogSQL):
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
            Literal(coog_string.translate_label(ClaimSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'claim'

    def get_rec_name(self, name):
        ClaimSynthesis = Pool().get('party.synthesis.menu.claim')
        return coog_string.translate_label(ClaimSynthesis, 'name')


class SynthesisMenu:
    __metaclass__ = PoolMeta
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
                    'claim.claim_view_list')
                        ])[0].id, 'tree'),
                    (Pool().get('ir.ui.view').search([('xml_id', '=',
                        'claim.claim_view_form')
                            ])[0].id, 'form')]
        }
        return actions


class InsurerDelegation:
    __metaclass__ = PoolMeta
    __name__ = 'insurer.delegation'

    claim_create = fields.Boolean('Claim Creation')

    @classmethod
    def __setup__(cls):
        super(InsurerDelegation, cls).__setup__()
        cls._delegation_flags.append('claim_create')

    @classmethod
    def default_claim_create(cls):
        return True


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('claim', 'claimant'),
            ]
