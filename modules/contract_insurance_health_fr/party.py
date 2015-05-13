import re
from sql.aggregate import Max
from collections import defaultdict

from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'PartyRelation',
    'HealthPartyComplement',
    ]


class Party:
    __name__ = 'party.party'
    _func_key = 'func_key'

    social_security_dependent = fields.Function(fields.One2Many('party.party',
            None, 'Social Security Dependent', depends=['relations']),
        'get_relations')
    social_security_insured = fields.Function(fields.One2Many('party.party',
            None, 'Social Security Insured', depends=['relations']),
        'get_relations')
    main_insured_ssn = fields.Function(fields.Char('Main Insured SSN'),
        'get_main_insured_ssn', searcher='search_main_insured_ssn')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    def get_main_insured_ssn(self, name):
        if self.social_security_dependent:
            ssns = sorted([x.ssn for x in self.social_security_dependent])
            return ssns[0]

    @classmethod
    def search_main_insured_ssn(cls, name, clause):
        pool = Pool()
        Party = pool.get('party.party')
        party = Party.__table__()
        party1 = Party.__table__()

        Relation = pool.get('party.relation')
        relation = Relation.__table__()

        RelationType = pool.get('party.relation.type')
        relation_type = RelationType.__table__()

        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        query_table = relation_type.join(relation, condition=(
                relation_type.id == relation.type)
            ).join(party, condition=(
                ((relation.to == party.id) &
                    (relation_type.code == 'social_security_insured')) |
                ((relation.from_ == party.id) &
                    (relation_type.code == 'social_security_dependent')))
            ).join(party1, condition=(
                ((relation.to == party1.id) &
                    (relation_type.code == 'social_security_dependent')) |
                ((relation.from_ == party1.id) &
                    (relation_type.code == 'social_security_insured'))) &
                party1.ssn.in_(party.select(Max(party.ssn), where=(
                            relation.to == party.id))))

        query = query_table.select(party.id, where=Operator(
                getattr(party1, 'ssn'), getattr(cls, 'ssn').sql_format(value)))

        return [('id', 'in', query)]

    def get_relations(self, name):
        return [relation.to.id for relation in self.relations
            if (relation.type and relation.type.code == name)]

    def get_SSN_required(self, name=None):
        if self.is_person and not self.social_security_dependent and \
                any([x.product.is_health for x in self.get_all_contracts()]):
            return True
        return super(Party, self).get_SSN_required(name)

    @fields.depends('relations')
    def on_change_with_social_security_dependent(self, name=None):
        return self.get_relations(name)

    @fields.depends('relations')
    def on_change_with_social_security_insured(self, name=None):
        return self.get_relations(name)

    def get_func_key(self, name):
        if self.is_person and self.ssn:
            return self.ssn
        elif self.is_person and self.social_security_dependent:
            return (self.name + '|' + self.first_name + '|' +
                self.main_insured_ssn)
        else:
            return super(Party, self).get_func_key(name)

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            assert len(operands) == 3
            name, first_name, ssn = operands
            res = []
            if name != 'None':
                res.append(('name', clause[1], name))
            if first_name != 'None':
                res.append(('first_name', clause[1], first_name))
            if ssn != 'None':
                res.append(('main_insured_ssn', clause[1], ssn))
            return res
        else:
            return ['OR',
                [('code',) + tuple(clause[1:])],
                [('ssn',) + tuple(clause[1:])],
                ]

    @classmethod
    def add_func_key(cls, values):
        if values.get('code', False):
            super(Party, cls).add_func_key(values)
            return
        if values.get('ssn', False):
            values['_func_key'] = values['ssn']
            return
        if not values.get('is_person', False):
            super(Party, cls).add_func_key(values)
            return
        ssn = 'None'
        for rel in values['relations']:
            if rel['type']['_func_key'] == 'social_security_dependent':
                ssn = rel['to']['_func_key']
                break
        values['_func_key'] = (values['name'] + '|' + values['first_name']
           + '|' + ssn)


class PartyRelation:
    __name__ = 'party.relation'

    @classmethod
    def __setup__(cls):
        super(PartyRelation, cls).__setup__()
        cls._error_messages.update({
                'invalid_social_security_relation': "%s can't be both a "
                "social security insured and dependent",
                'SSN_required': 'The SSN is required for %s',
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
                    and relation.to.social_security_dependent
                    or relation.type == social_security_insured_relation
                    and relation.to.social_security_insured):
                cls.raise_user_error('invalid_social_security_relation',
                    relation.to.rec_name)
            if (relation.type == social_security_dependent_relation
                    and relation.from_.social_security_insured
                    or relation.type == social_security_insured_relation
                    and relation.from_.social_security_dependent):
                cls.raise_user_error('invalid_social_security_relation',
                    relation.from_.rec_name)

    @classmethod
    def delete(cls, relations):
        pool = Pool()
        RelationType = pool.get('party.relation.type')
        social_security_dependent_relation, = RelationType.search([
                ('xml_id', '=', 'contract_insurance_health_fr.'
                    'social_security_dependent_relation_type'),
                ])
        social_security_insured_relation, = RelationType.search([
                ('xml_id', '=', 'contract_insurance_health_fr.'
                    'social_security_insured_relation_type'),
                ])
        for relation in relations:
            if (relation.type == social_security_insured_relation and
                    len(relation.to.social_security_dependent) == 1
                    and not relation.to.ssn):
                cls.raise_user_error('SSN_required', relation.to.rec_name)
        super(PartyRelation, cls).delete(relations)


class HealthPartyComplement:
    __name__ = 'health.party_complement'

    department = fields.Function(
        fields.Char('Department'),
        'get_department')
    hc_system = fields.Many2One('health.care_system', 'Health Care System',
        ondelete='RESTRICT')
    insurance_fund = fields.Function(fields.Many2One('health.insurance_fund',
            'Insurance Fund', depends=['insurance_fund_number']),
        'get_insurance_fund')
    insurance_fund_number = fields.Char('Health Care System Number', size=9)

    @classmethod
    def __setup__(cls):
        super(HealthPartyComplement, cls).__setup__()
        cls._error_messages.update({
            'wrong_insurance_fund_number': 'Wrong Insurance Fund Number: %s',
            'hc_system_not_defined': 'HC system must be defined'
            })

    @classmethod
    def get_insurance_fund(cls, complements, name=None):
        ''' Some Insurance funds group more than one insurance fund number
        In this case the last 4 characters of the insurance fund are set to
        0000'''

        pool = Pool()
        cursor = Transaction().cursor
        fund = pool.get('health.insurance_fund').__table__()
        codes = defaultdict(list)
        for complement in complements:
            codes[complement.insurance_fund_number].append(complement)
        result = {x.id: None for x in complements}

        cursor.execute(*fund.select(fund.id, fund.code,
                where=(fund.code.in_([x.insurance_fund_number
                            for x in complements]))))
        for fund_id, fund_code in cursor.fetchall():
            for complement in codes[fund_code]:
                result[complement.id] = fund_id

        outstanding_codes = {}
        for complement in complements:
            if (result[complement.id] is None and
                    complement.insurance_fund_number):
                outstanding_codes[complement.insurance_fund_number[0:5] +
                    '0000'] = complement.insurance_fund_number
        if not outstanding_codes:
            return result
        cursor.execute(*fund.select(fund.id, fund.code,
                where=(fund.code.in_(outstanding_codes.keys()))))
        for fund_id, fund_code in cursor.fetchall():
            for complement in codes[outstanding_codes[fund_code]]:
                result[complement.id] = fund_id

        return result

    @fields.depends('insurance_fund_number')
    def on_change_with_insurance_fund(self):
        return self.__class__.get_insurance_fund([self])[self.id]

    def get_department(self, name):
        address = self.party.address_get() if self.party else None
        return address.get_department() if address else None

    @classmethod
    def _export_light(cls):
        return (super(HealthPartyComplement, cls)._export_light() |
            set(['hc_system', 'insurance_fund']))

    def check_insurance_fund_number(self):
        if not self.insurance_fund_number:
            return
        if not self.hc_system and self.insurance_fund_number:
            self.raise_user_error('hc_system_not_defined')
        if (not re.match('%s[0-9]{7}' % self.hc_system.code,
                self.insurance_fund_number) or not self.insurance_fund):
            self.raise_user_error('wrong_insurance_fund_number',
                self.insurance_fund_number)

    def pre_validate(self):
        super(HealthPartyComplement, self).pre_validate()
        self.check_insurance_fund_number()
