from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Not, Bool, Or

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'PartyRelation',
    'HealthPartyComplement',
    ]


class Party:
    __name__ = 'party.party'

    social_security_dependent = fields.Function(fields.One2Many('party.party',
            None, 'Social Security Dependent', depends=['relations']),
        'get_relations')
    social_security_insured = fields.Function(fields.One2Many('party.party',
            None, 'Social Security Insured', depends=['relations']),
        'get_relations')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls.ssn.states['required'] = Or(cls.ssn.states.get('required', False),
            Not(Bool(Eval('social_security_dependent', False))))
        cls.ssn.depends.append('social_security_dependent')

    def get_relations(self, name):
        return [relation.to.id for relation in self.relations
            if (relation.type and relation.type.code == name)]

    @fields.depends('relations')
    def on_change_with_social_security_dependent(self, name=None):
        return self.get_relations(name)

    @fields.depends('relations')
    def on_change_with_social_security_insured(self, name=None):
        return self.get_relations(name)


class PartyRelation:
    __name__ = 'party.relation'

    @classmethod
    def __setup__(cls):
        super(PartyRelation, cls).__setup__()
        cls._error_messages.update({
                'invalid_social_security_relation': "%s can't be both a "
                "social security insured and dependent",
                })

    @classmethod
    def validate(cls, relations):
        pool = Pool()
        RelationType = pool.get('party.relation.type')
        super(PartyRelation, cls).validate(relations)
        social_security_dependent_relation, = RelationType.search([
                ('xml_id', '=', 'contract_insurance_health_fr.'
                    'social_security_dependent_relation_type'),
                ])
        social_security_insured_relation, = RelationType.search([
                ('xml_id', '=', 'contract_insurance_health_fr.'
                    'social_security_insured_relation_type'),
                ])
        for relation in relations:
            if (relation.type == social_security_dependent_relation
                    and (relation.to.social_security_dependent
                        or relation.from_.social_security_insured)
                    or relation.type == social_security_insured_relation
                    and (relation.to.social_security_insured
                        or relation.from_.social_security_dependent)):
                cls.raise_user_error('invalid_social_security_relation',
                    relation.to.rec_name)


class HealthPartyComplement:
    __name__ = 'health.party_complement'

    department = fields.Function(
        fields.Char('Department'),
        'get_department', 'set_void')
    hc_system = fields.Many2One('health.care_system', 'Health Care System',
        ondelete='RESTRICT')
    insurance_fund = fields.Many2One('health.insurance_fund', 'Insurance Fund',
        ondelete='RESTRICT', domain=[
            [If(
                    ~Eval('department'),
                    (),
                    ('department', '=', Eval('department')),
                    )],
            ('hc_system', '=', Eval('hc_system')),
            ], depends=['department', 'hc_system'])

    def get_department(self, name):
        address = self.party.address_get() if self.party else None
        return address.get_department() if address else None

    @classmethod
    def set_void(cls, instances, vals, name):
        pass
