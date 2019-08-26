# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import re

from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import PoolMeta

__all__ = [
    'Employment',
    ]


class Employment(metaclass=PoolMeta):
    __name__ = 'party.employment'

    def check_employment_identifier(self):
        if self.is_civil_service_employment:
            if not self.check_civil_service_identifier():
                raise ValidationError(gettext(
                        'party_public_employment_fr'
                        '.msg_invalid_employment_identifier'))

    def check_civil_service_identifier(self):
        if not self.employment_identifier:
            return True
        pattern = "^[0-9]{15}$"
        return re.search(pattern,
            self.employment_identifier, re.X)
