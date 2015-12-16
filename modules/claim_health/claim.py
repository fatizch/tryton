# encoding: utf-8
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import model, fields
from trytond.pyson import Eval, Equal, Bool

__metaclass__ = PoolMeta
__all__ = [
    'HealthLoss',
    'Loss',
    'Claim',
    'ClaimService',
    ]


class HealthLoss(model.CoopSQL, model.CoopView):
    'Health Loss'

    __name__ = 'claim.loss.health'
    _func_key = 'func_key'

    loss = fields.Many2One('claim.loss', 'Loss', required=True,
        ondelete='CASCADE')
    covered_person = fields.Many2One('party.party', 'Covered Person',
        ondelete='RESTRICT', required=True)
    act_description = fields.Many2One('benefit.act.description',
        'Medical Act Description')
    act_date = fields.Date('Date of Medical Act', required=True)
    act_end_date = fields.Date('End Date of Medical Act')
    quantity = fields.Integer('Quantity')
    total_charges = fields.Numeric('Total Charges')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key')

    def get_func_key(self, name):
        return ''

    def get_rec_name(self, name=None):
        return '[%s] ' % self.act_date + self.covered_person.full_name

    @classmethod
    def _export_light(cls):
        return super(HealthLoss, cls)._export_light() | {'covered_person'}

    @property
    def date(self):
        return self.act_date

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = ''


class Loss(model.CoopSQL, model.CoopView):
    'Loss'

    __name__ = 'claim.loss'

    health_loss = fields.One2Many('claim.loss.health', 'loss', 'Health Loss',
        size=1, states={"invisible": ~Bool(Equal(Eval('loss_kind'),
                    'health'))}, depends=['loss_kind'])
    loss_kind = fields.Function(
        fields.Char('Loss Kind'), 'get_loss_kind')

    @classmethod
    def get_date_field_for_kind(cls, kind):
        return 'health_loss.act_date' if kind == 'health' else \
            super(Loss, cls).get_date_field_for_kind(kind)

    def get_date(self):
        return self.health_loss[0].act_date if hasattr(self, 'loss_desc') \
            and self.loss_desc and self.loss_desc.loss_kind == 'health' else \
            super(Loss, self).get_date()

    def get_covered_person(self):
        return self.health_loss[0].covered_person if hasattr(self, 'loss_desc') \
            and self.loss_desc and self.loss_desc.loss_kind == 'health' else \
            super(Loss, self).get_covered_person()

    def get_loss_kind(self, name):
        return self.loss_desc.loss_kind


class Claim:
    __name__ = 'claim'

    quote_date = fields.Date('Quote Date')
    quote_validity_end_date = fields.Date('Quote Validity End Date')


class ClaimService:
    __name__ = 'claim.service'

    def get_covered_person(self):
        if self.loss.loss_desc.loss_kind == 'health':
            return self.loss.health_loss.covered_person
        return super(ClaimService, self).get_covered_person()
