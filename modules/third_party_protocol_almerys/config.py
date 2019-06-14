# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSingleton

from trytond.modules.coog_core import model, fields
from trytond.modules.company.model import (
    CompanyValueMixin, CompanyMultiValueMixin)

customer_number = fields.Char("Customer Number", required=True)
customer_label = fields.Char("Customer Label", required=True)
number_sequence_v3 = fields.Many2One('ir.sequence', "Number Sequence V3",
    required=True, ondelete='RESTRICT',
    domain=[
        ('code', '=', 'third_party_protocol.almerys.v3'),
        ])
protocol_version = fields.Char("Protocol Version", required=True)


class AlmerysConfig(
        ModelSingleton, model.CoogSQL, model.CoogView, CompanyMultiValueMixin):
    "Almerys Configuration"
    __name__ = 'third_party_protocol.almerys.configuration'

    customer_number = fields.MultiValue(customer_number)
    customer_label = fields.MultiValue(customer_label)
    number_sequence_v3 = fields.MultiValue(number_sequence_v3)
    protocol_version = fields.MultiValue(protocol_version)


class ConfigurationNumberSequenceV3(model.CoogSQL, CompanyValueMixin):
    "Almerys Configuration - Number Sequence V3"
    __name__ = 'third_party_protocol.almerys.configuration.number_sequence_v3'

    number_sequence_v3 = number_sequence_v3


class ConfigurationProtocolVersion(model.CoogSQL, CompanyValueMixin):
    "Almerys Configuration - Protocol Version"
    __name__ = 'third_party_protocol.almerys.configuration.protocol_version'

    protocol_version = protocol_version


class ConfigurationCustomerNumber(model.CoogSQL, CompanyValueMixin):
    "Almerys Configuration - Customer Number"
    __name__ = 'third_party_protocol.almerys.configuration.customer_number'

    customer_number = customer_number


class ConfigurationCustomerLabel(model.CoogSQL, CompanyValueMixin):
    "Almerys Configuration - Customer Label"
    __name__ = 'third_party_protocol.almerys.configuration.customer_label'

    customer_label = customer_label
