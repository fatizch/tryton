# encoding: utf-8
from trytond.pool import PoolMeta
from trytond.model import Unique

from trytond.modules.cog_utils import model, fields, coop_string

__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    'UnderwritingDecision',
    ]

UNDERWRITING_STATUSES = [
    ('accepted', 'Accepted'),
    ('denied', 'Denied'),
    ('postponed', 'PostPoned'),
    ('pending', 'Pending'),
    ]


class UnderwritingDecision(model.CoopSQL, model.CoopView):
    'Underwriting Decision'

    __name__ = 'underwriting.decision'
    _func_key = 'code'

    code = fields.Char('Code', required=True, select=True)
    name = fields.Char('Name', required=True)
    status = fields.Selection(UNDERWRITING_STATUSES, 'Status', required=True)
    with_exclusion = fields.Boolean('With Exclusion')
    with_subscriber_validation = fields.Boolean('With Subscriber Validation')

    @classmethod
    def __setup__(cls):
        super(UnderwritingDecision, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(t, t.code), 'The code must be unique'),
            ]

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)


class Product:
    __name__ = 'offered.product'

    @classmethod
    def kind_list_for_extra_data_domain(cls):
        kinds = super(Product, cls).kind_list_for_extra_data_domain()
        kinds.append('contract_underwriting')
        return kinds


class OptionDescription:
    __name__ = 'offered.option.description'

    with_underwriting = fields.Selection([
            ('never_underwrite', 'Never underwrite'),
            ('always_underwrite', 'Always underwrite')], 'With Underwriting')

    @staticmethod
    def default_with_underwriting():
        return 'never_underwrite'

    @classmethod
    def kind_list_for_extra_data_domain(cls):
        kinds = super(OptionDescription, cls).kind_list_for_extra_data_domain()
        kinds.append('option_underwriting')
        return kinds
