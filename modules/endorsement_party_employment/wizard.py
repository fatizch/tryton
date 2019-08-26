# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool
from trytond.exceptions import UserError
from trytond.i18n import gettext

from trytond.modules.coog_core import fields, model
from trytond.modules.endorsement.wizard import (EndorsementWizardStepMixin,
    add_endorsement_step)

__all__ = [
    'StartEndorsement',
    'ManagePartyEmployment',
    ]


class StartEndorsement(metaclass=PoolMeta):
    __name__ = 'endorsement.start'


class ManagePartyEmployment(EndorsementWizardStepMixin):
    'Manage Party Employment'

    __name__ = 'endorsement.party.employment.manage_party_employment'

    employment = fields.Many2One('party.employment', 'Employment',
        domain=[('id', 'in', Eval('possible_employments', []))],
        depends=['possible_employments'])
    employment_display = fields.One2Many('party.employment', None,
        'Employment', states={'invisible': ~Bool(Eval('employment', False))},
        depends=['employment'])
    possible_employments = fields.One2Many('party.employment', None,
        'Possible Employments')
    version = fields.One2Many('party.employment.version', None,
        'Version',
        states={'invisible': ~Bool(Eval('employment', False))},
            depends=['employment'])
    employment_endorsements = fields.One2Many('endorsement.party.employment',
        None, 'Employment Endorsement')
    version_id = fields.Integer('Version ID')

    def _get_parties(self):
        return {x.party.id: x
            for x in self.wizard.endorsement.party_endorsements}

    def step_default(self, field_names):
        pool = Pool()
        Party = pool.get('party.party')
        defaults = super(ManagePartyEmployment, self).step_default()

        if len(Transaction().context.get('active_ids')) > 1:
            raise UserError(gettext(
                    'endorsement_party_employment.msg_invalid_active_ids'))

        current_party_id = Transaction().context.get('active_id')
        current_party = Party(current_party_id)
        if not current_party.is_person:
            raise UserError(gettext(
                    'endorsement_party_employment.msg_invalid_type'))
        possible_employments = [x.id for x in current_party.employments]
        if not possible_employments:
            raise UserError(gettext(
                    'endorsement_party_employment.msg_invalid_op'))
        defaults['possible_employments'] = possible_employments
        defaults['employment'] = possible_employments[0]
        # reload objects from previous step
        if (self.wizard.endorsement
                and self.wizard.endorsement.party_endorsements):
            endorsement_party = self.wizard.endorsement.party_endorsements[0]
            defaults['employment_endorsements'] = [x.id for x in
                endorsement_party.employments]
            if endorsement_party.employments:
                defaults['employment'] = \
                    endorsement_party.employments[0].relation

        return defaults

    @classmethod
    def init_new_object(cls, from_object):
        new_object = from_object.__class__()
        for field in from_object.__class__.fields_modifiable_in_endorsement():
            setattr(new_object, field, getattr(from_object, field))
        return new_object

    @classmethod
    def init_from_dict(cls, the_dict, the_class):
        new_object = the_class.__class__()
        for field in the_class.__class__.fields_modifiable_in_endorsement():
            setattr(new_object, field, the_dict[field] if field in the_dict
            else None)
        return new_object

    def current_version_has_effective_date_as_date(self):
        return hasattr(self.version[0], 'date') and self.version[0].date == \
               self.wizard.endorsement.effective_date

    def current_version_has_changed(self):
        Version = Pool().get('party.employment.version')
        old_version_dict = {}
        if self.version_id:
            old_version = Version(self.version_id)
            old_version_dict = model.dictionarize(
                old_version, field_names=old_version.__class__.
                fields_modifiable_in_endorsement(),)
        new_version_dict = model.dictionarize(
            self.version[0],
            field_names=self.version[0].__class__.
            fields_modifiable_in_endorsement())
        return old_version_dict != new_version_dict

    def current_employment_has_changed(self):
        Employment = Pool().get('party.employment')
        old_employment_dict = {}
        if self.employment:
            old_employment = Employment(self.employment.id)
            old_employment_dict = model.dictionarize(old_employment,
                field_names=old_employment.__class__.
                fields_modifiable_in_endorsement())
        new_employment_dict = model.dictionarize(
            self.employment_display[0],
            field_names=self.employment_display[0].__class__.
            fields_modifiable_in_endorsement())
        return new_employment_dict != old_employment_dict

    def build_correct_version(self, instance):
        """
        build new version either from previous step endorsement_version
        values or from current employment
        """
        if (self.employment_endorsements and
                self.employment_endorsements[0].relation ==
                instance.employment.id and
                self.employment_endorsements[0].versions):
            x = self.__class__.init_from_dict(
                self.employment_endorsements[0].versions[0].values, instance)
            return x

        return self.__class__.init_new_object(instance)

    def build_correct_employment_display(self, instance):
        """
        build new employment_display either from previous step
        endorsement_employment or from current employment
        """
        if (self.employment_endorsements and
                self.employment_endorsements[0].relation == instance.id):
            employment = self.employment_endorsements[0]
            new_employment_display = self.__class__.init_from_dict(
                employment.values, instance)
            return new_employment_display
        return self.__class__.init_new_object(instance)

    def extract_correct_saved_values(self, instance):
        saved_values = {k: v for k, v in instance._save_values.items()
            if k in instance.__class__.fields_modifiable_in_endorsement()
        }
        return saved_values

    def step_update(self):
        pool = Pool()
        EmploymentEndorsement = pool.get('endorsement.party.employment')
        EmploymentVersionEndorsement = pool.\
            get('endorsement.party.employment.version')
        for endorsement in self.wizard.endorsement.party_endorsements:
            endorsement.employments = []
            if not self.current_employment_has_changed() \
                    and not self.current_version_has_changed():
                continue
            employment_endorsement = EmploymentEndorsement(
                action='update',
                endorsement_party=endorsement,
                employment=self.employment,
                relation=self.employment.id,
                definition=self.endorsement_definition,
                values=self.extract_correct_saved_values(
                    self.employment_display[0]),)

            if self.current_version_has_effective_date_as_date():
                employment_version_endorsement = \
                    EmploymentVersionEndorsement(
                        action='update',
                        endorsement_party_employment=employment_endorsement,
                        relation=self.version_id,
                        definition=self.endorsement_definition,
                        values=self.extract_correct_saved_values(
                            self.version[0]))
                employment_version_endorsement.save()
                employment_endorsement.versions = [
                    employment_version_endorsement]
            elif self.current_version_has_changed():
                employment_version_endorsement = \
                    EmploymentVersionEndorsement(
                        action='add',
                        endorsement_party_employment=employment_endorsement,
                        definition=self.endorsement_definition,
                        values=self.extract_correct_saved_values(
                            self.version[0]))
                employment_version_endorsement.values['date'] = self.\
                    wizard.endorsement.effective_date
                employment_version_endorsement.save()
                employment_endorsement.versions = [
                    employment_version_endorsement]
            employment_endorsement.save()
            endorsement.employments = [employment_endorsement]
            endorsement.save()

    @fields.depends('employment', 'employment_display', 'version',
        'effective_date', 'employment_endorsements')
    def on_change_employment(self):
        Version = Pool().get('party.employment.version')
        if not self.employment:
            return
        self.employment_display = [self.build_correct_employment_display(
            self.employment)]
        version = Version.version_at_date(self.employment, self.effective_date)
        if version:
            self.version = [self.build_correct_version(version)]
            self.version_id = version.id
        else:
            self.version = [{}]

    @classmethod
    def state_view_name(cls):
        return 'endorsement_party_employment.manage_party_employment_view_form'


add_endorsement_step(StartEndorsement, ManagePartyEmployment,
    'manage_party_employment')
