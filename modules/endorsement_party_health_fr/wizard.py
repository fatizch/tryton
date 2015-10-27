from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import (EndorsementWizardStepMixin,
    add_endorsement_step)

__metaclass__ = PoolMeta
__all__ = [
    'ChangePartyHealthComplement',
    'StartEndorsement',
    ]


class ChangePartyHealthComplement(EndorsementWizardStepMixin):
    'Change Party Health Complement'

    __name__ = 'endorsement.party.change_health_complement'

    current_health_complement = fields.One2Many('health.party_complement',
        None, 'Current Health Complement', size=1)
    new_health_complement = fields.One2Many('health.party_complement', None,
        'New Health Complement', size=1)

    @classmethod
    def is_multi_instance(cls):
        return False

    @classmethod
    def state_view_name(cls):
        return 'endorsement_party_health_fr.' \
            'party_change_health_complement_view_form'

    @classmethod
    def _health_complement_fields_to_extract(cls):
        return ['hc_system', 'insurance_fund_number', 'party',
            'insurance_fund', 'date']

    def _get_parties(self):
        return {x.party.id: x
            for x in self.wizard.endorsement.party_endorsements}

    def step_default(self, name):
        pool = Pool()
        PartyComplement = pool.get('health.party_complement')
        defaults = super(ChangePartyHealthComplement, self).step_default()
        parties = self._get_parties()
        for _, party_endorsement in parties.iteritems():
            updated_struct = party_endorsement.updated_struct
            # init with saved modified data
            for health_complement in updated_struct['health_complement']:
                if health_complement.__name__ == \
                        'endorsement.party.health_complement':
                    values = model.dictionarize(
                        health_complement.health_complement,
                        self._health_complement_fields_to_extract())
                    values['date'] = \
                        party_endorsement.endorsement.effective_date
                    values.update(health_complement.values)
                    defaults['current_health_complement'] = [
                        health_complement.health_complement.id]
                    defaults['new_health_complement'] = [values]
            if 'new_health_complement' not in defaults:
                # init from version at endorsement effective date
                version = PartyComplement.get_values([health_complement.party],
                    'health_complement',
                    party_endorsement.endorsement.effective_date)
                values = model.dictionarize(
                    PartyComplement(version['id'][health_complement.party.id]),
                    self._health_complement_fields_to_extract())
                values['date'] = party_endorsement.endorsement.effective_date
                defaults['current_health_complement'] = [
                    version['id'][health_complement.party.id]]
                defaults['new_health_complement'] = [values]
        return defaults

    def step_update(self):
        pool = Pool()
        Party = pool.get('party.party')
        EndorsementHealthComplement = pool.get(
            'endorsement.party.health_complement')
        PartyComplement = pool.get('health.party_complement')
        parties = self._get_parties()
        for party_id, party_endorsement in parties.iteritems():
            EndorsementHealthComplement.delete(
                party_endorsement.health_complement)
            party = Party(party_id)
            for i, health_complement in enumerate(self.new_health_complement):
                new_values = {}
                if hasattr(health_complement, '_save_values'):
                    new_values = {k: v for k, v in
                        health_complement._save_values.iteritems() if k in
                        self._health_complement_fields_to_extract() and
                        v != getattr(self.current_health_complement[0], k)}
                dates = [x.date for x in party.health_complement]
                action = 'update' if 'date' not in new_values or \
                    new_values['date'] in dates else 'add'
                new_values.pop('party', None)
                if (action == 'update' and 'hc_system' in new_values and
                        self.current_health_complement[0].hc_system and
                        new_values['hc_system'] ==
                        self.current_health_complement[0].hc_system.id):
                    new_values.pop('hc_system')
                if not new_values:
                    continue
                all_values = model.dictionarize(PartyComplement(
                        self.current_health_complement[0]),
                    self._health_complement_fields_to_extract())
                all_values.update(new_values)
                test_complement = PartyComplement(**all_values)
                test_complement.insurance_fund = \
                    PartyComplement.get_insurance_fund(
                        [test_complement]).values()[0]
                test_complement.check_insurance_fund_number()

                h_complement_endorsement = EndorsementHealthComplement(
                    action=action,
                    party_endorsement=party_endorsement,
                    health_complement=self.current_health_complement[i],
                    relation=self.current_health_complement[i].id if
                    action == 'update' else None,
                    definition=self.endorsement_definition,
                    values=new_values,
                    )
                h_complement_endorsement.save()
            party_endorsement.save()


class StartEndorsement:
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsement, ChangePartyHealthComplement,
    'change_health_complement')
