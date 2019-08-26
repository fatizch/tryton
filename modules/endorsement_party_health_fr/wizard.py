# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields, model
from trytond.modules.endorsement.wizard import (EndorsementWizardStepMixin,
    add_endorsement_step)

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
        new_empty_health_complement = dict.fromkeys(
            self._health_complement_fields_to_extract(), None)
        for _, party_endorsement in parties.items():
            updated_struct = party_endorsement.updated_struct
            # init with saved modified data
            health_complement = None
            for health_complement in updated_struct['health_complement']:
                if health_complement.__name__ == \
                        'endorsement.party.health_complement':
                    values = model.dictionarize(
                        health_complement.health_complement,
                        self._health_complement_fields_to_extract()) \
                        if health_complement.health_complement else \
                        new_empty_health_complement
                    values['party'] = party_endorsement.party.id
                    values['date'] = \
                        party_endorsement.endorsement.effective_date
                    values.update(health_complement.values)
                    defaults['new_health_complement'] = [values]
                elif health_complement.__name__ == \
                        'health.party_complement':
                    defaults_current_health_complement = defaults.get(
                        'current_health_complement', None) or []
                    defaults_current_health_complement.append(
                        model.dictionarize(
                            PartyComplement(health_complement),
                            self._health_complement_fields_to_extract()))
                    defaults['current_health_complement'] = \
                        defaults_current_health_complement
            if 'new_health_complement' not in defaults:
                # init from version at endorsement effective date
                version = PartyComplement.get_values([party_endorsement.party],
                    'health_complement',
                    party_endorsement.endorsement.effective_date)
                current_health_complement = version['id'][
                    party_endorsement.party.id]
                values = model.dictionarize(
                    PartyComplement(current_health_complement),
                    self._health_complement_fields_to_extract()) if \
                    current_health_complement else new_empty_health_complement
                values['date'] = party_endorsement.endorsement.effective_date
                values['party'] = party_endorsement.party.id
                defaults['current_health_complement'] = [
                    current_health_complement] if current_health_complement \
                    else []
                defaults['new_health_complement'] = [values]
        return defaults

    def step_update(self):
        pool = Pool()
        Party = pool.get('party.party')
        EndorsementHealthComplement = pool.get(
            'endorsement.party.health_complement')
        PartyComplement = pool.get('health.party_complement')
        parties = self._get_parties()
        for party_id, party_endorsement in parties.items():
            EndorsementHealthComplement.delete(
                party_endorsement.health_complement)
            party = Party(party_id)
            for i, health_complement in enumerate(self.new_health_complement):
                save_values = health_complement._save_values
                dates = [x.date for x in party.health_complement]
                action = 'update' if 'date' not in save_values or \
                    save_values['date'] in dates else 'add'
                if action == 'update':
                    new_values = {k: v for k, v in save_values.items()
                        if k in self._health_complement_fields_to_extract() and
                        v != getattr(self.current_health_complement[0], k)}
                else:
                    new_values = {k: v for k, v in save_values.items()
                        if k in self._health_complement_fields_to_extract()}
                new_values.pop('party', None)
                if (action == 'update' and 'hc_system' in new_values and
                        self.current_health_complement[0].hc_system and
                        new_values['hc_system'] ==
                        self.current_health_complement[0].hc_system.id):
                    new_values.pop('hc_system')
                if not new_values:
                    continue
                all_values = {}
                if self.current_health_complement:
                    all_values = model.dictionarize(PartyComplement(
                            self.current_health_complement[0]),
                        self._health_complement_fields_to_extract())
                all_values.update(new_values)
                test_complement = PartyComplement(**all_values)
                test_complement.insurance_fund = \
                    list(PartyComplement.get_insurance_fund(
                        [test_complement]).values())[0]
                test_complement.check_insurance_fund_number()

                h_complement_endorsement = EndorsementHealthComplement(
                    action=action,
                    party_endorsement=party_endorsement,
                    health_complement=self.current_health_complement[i] if
                    action == 'update' else None,
                    relation=self.current_health_complement[i].id if
                    action == 'update' else None,
                    definition=self.endorsement_definition,
                    values=new_values,
                    )
                h_complement_endorsement.save()
            party_endorsement.save()

    @classmethod
    def check_before_start(cls, select_screen):
        super(ChangePartyHealthComplement, cls).check_before_start(
            select_screen)
        dependents = []
        if select_screen.endorsement:
            dependents = [x.party
                for x in select_screen.endorsement.party_endorsements
                if x.party.social_security_dependent]
        if (getattr(select_screen, 'party', None)
                and select_screen.party.social_security_dependent):
            dependents.append(select_screen.party)
        if dependents:
            cls.append_functional_error(
                ValidationError(gettext(
                        'endorsement_party_health_fr'
                        '.msg_social_security_dependent',
                        full_name=[str(p.rec_name) for p in dependents])))


class StartEndorsement(metaclass=PoolMeta):
    __name__ = 'endorsement.start'


add_endorsement_step(StartEndorsement, ChangePartyHealthComplement,
    'change_health_complement')
