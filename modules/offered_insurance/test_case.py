# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


MODULE_NAME = 'offered_insurance'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def insurer_test_case(cls):
        pool = Pool()
        Insurer = pool.get('insurer')
        Party = pool.get('party.party')
        cls.load_resources(MODULE_NAME)
        insurer_file = cls.read_data_file('insurer', MODULE_NAME, ';')
        insurers = []
        for insurer_data in insurer_file:
            insurer_party = cls.new_company(insurer_data[1], insurer_data[0])
            insurer_party.insurer_role = [Insurer()]
            insurers.append(insurer_party)
        Party.create([x._save_values for x in insurers])
        return insurers

    @classmethod
    def create_extra_premium_kind(cls, **kwargs):
        ExtraPremiumKind = Pool().get('extra_premium.kind')
        return ExtraPremiumKind(**kwargs)

    @classmethod
    def extra_premium_kind_test_case(cls):
        ExtraPremiumKind = Pool().get('extra_premium.kind')
        translater = cls.get_translater(MODULE_NAME)
        extra_kinds = []
        for code, name in [
                ('medical_risk', 'Medical Risk'),
                ('professional_risk', 'Professional Risk'),
                ('sport_risk', 'Sport Risk')]:
            extra_kinds.append(cls.create_extra_premium_kind(
                    code=translater(code),
                    name=translater(name)))
        ExtraPremiumKind.create([x._save_values for x in extra_kinds])
