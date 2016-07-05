# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import relation_mixin

__metaclass__ = PoolMeta
__all__ = [
    'HealthComplement',
    'EndorsementParty',
    'EndorsementPartyHealthComplement',
    ]


class HealthComplement(object):
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'health.party_complement'

    def get_rec_name(self, name):
        if self.party:
            return self.party.rec_name
        else:
            return ''


class EndorsementPartyHealthComplement(relation_mixin(
            'endorsement.party.health_complement.field', 'health_complement',
            'health.party_complement', 'Health Complement'),
        model.CoopSQL, model.CoopView):
    'Endorsement Health Complement'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.party.health_complement'

    party_endorsement = fields.Many2One(
        'endorsement.party', 'Party Endorsement',
        required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.party_endorsement.definition.id

    @property
    def new_health_complement(self):
        elems = set([x for x in self.party.health_complement])
        for elem in getattr(self, 'health_complement', []):
            if elem.action == 'add':
                elems.add(elem)
            elif elem.action == 'remove':
                elems.remove(elem.health_complement)
            else:
                elems.remove(elem.health_complement)
                elems.add(elem)
        return elems

    @classmethod
    def updated_struct(cls, health_complement):
        return {}


class EndorsementParty:
    __name__ = 'endorsement.party'

    @classmethod
    def __setup__(cls):
        super(EndorsementParty, cls).__setup__()
        cls._error_messages.update({
                'msg_hc_modifications':
                'Health Complement Modifications',
                })

    health_complement = fields.One2Many('endorsement.party.health_complement',
        'party_endorsement', 'health_complement', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'party', 'definition'],
        context={'definition': Eval('definition')}, delete_missing=True)

    @classmethod
    def _get_restore_history_order(cls):
        return super(EndorsementParty, cls)._get_restore_history_order() + \
            ['health.party_complement']

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementParty, cls)._prepare_restore_history(instances,
            at_date)
        for party in instances['party.party']:
            instances['health.party_complement'] += party.health_complement

    def get_endorsement_summary(self, name):
        result = super(EndorsementParty, self).get_endorsement_summary(name)
        health_complement_summary = [health_complement.get_diff(
            'health.party_complement', health_complement.health_complement)
                for health_complement in self.health_complement]
        if health_complement_summary:
            result[1].append(['%s :' % self.raise_user_error(
                        'msg_hc_modifications',
                        raise_exception=False),
                    health_complement_summary])
        return result

    @property
    def new_health_complement(self):
        elems = set([x for x in self.party.health_complement])
        for elem in getattr(self, 'health_complement', []):
            if elem.action == 'add':
                elems.add(elem)
            elif elem.action == 'remove':
                elems.remove(elem.health_complement)
            else:
                elems.remove(elem.health_complement)
                elems.add(elem)
        return elems

    @property
    def updated_struct(self):
        pool = Pool()
        EndorsementHealthComplement = pool.get(
                'endorsement.party.health_complement')
        res = super(EndorsementParty, self).updated_struct
        health_complements = {}
        for health_complement in self.new_health_complement:
            health_complements[health_complement] =\
                    EndorsementHealthComplement.updated_struct(
                            health_complement)
        res.update({'health_complement': health_complements})
        return res

    def apply_values(self):
        values = super(EndorsementParty, self).apply_values()
        health_complements = []
        for health_complement in self.health_complement:
            health_complements.append(health_complement.apply_values())
        if health_complements:
            values['health_complement'] = health_complements
        return values
