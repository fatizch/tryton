from trytond.pool import PoolMeta
from trytond.pyson import Not

from trytond.modules.coop_utils import model, fields, coop_string
from trytond.modules.coop_party.party import STATES_COMPANY

__metaclass__ = PoolMeta

__all__ = [
    'Party',
    'Insurer',
    ]


class Party:
    'Party'

    __name__ = 'party.party'

    insurer_role = fields.One2Many('insurer', 'party', 'Insurer', size=1,
        states={'invisible': Not(STATES_COMPANY)})

    @classmethod
    def _export_force_recreate(cls):
        result = super(Party, cls)._export_force_recreate()
        result.remove('insurer_role')
        return result

    @classmethod
    def get_summary(cls, parties, name=None, at_date=None, lang=None):
        res = super(Party, cls).get_summary(
            parties, name=name, at_date=at_date, lang=lang)
        for party in parties:
            if party.insurer_role:
                res[party.id] += coop_string.get_field_as_summary(party,
                    'insurer_role', True, at_date, lang=lang)
        return res


class Insurer(model.CoopView, model.CoopSQL):
    'Insurer'

    __name__ = 'insurer'

    @classmethod
    def _export_keys(cls):
        return set(['party.name'])

    @classmethod
    def get_summary(cls, insurers, name=None, at_date=None, lang=None):
        return dict([(insurer.id, 'X') for insurer in insurers])
