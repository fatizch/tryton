import copy
from sql.aggregate import Max
from sql import Literal

from trytond.modules.cog_utils import MergedMixin
from trytond.pool import Pool
from trytond.wizard import Wizard
from trytond.pyson import PYSONEncoder
from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'SynthesisMenuPayment',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    ]


class SynthesisMenuPayment(model.CoopSQL):
    'Party Synthesis Menu payment'
    __name__ = 'party.synthesis.menu.payment'
    name = fields.Char('Payment')
    party = fields.Many2One('party.party', 'Party')

    @staticmethod
    def table_query():
        pool = Pool()
        Payment = pool.get('account.payment')
        payment = Payment.__table__()
        party = pool.get('party.party').__table__()
        PaymentSynthesis = pool.get('party.synthesis.menu.payment')
        query_table = party.join(payment, 'LEFT OUTER', condition=(
            party.id == payment.party))
        return query_table.select(
            party.id,
            Max(payment.create_uid).as_('create_uid'),
            Max(payment.create_date).as_('create_date'),
            Max(payment.write_uid).as_('write_uid'),
            Max(payment.write_date).as_('write_date'),
            Literal(coop_string.translate_label(PaymentSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'payment'


class SynthesisMenu(MergedMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def merged_models(cls):
        res = super(SynthesisMenu, cls).merged_models()
        res.extend([
            'party.synthesis.menu.payment',
            'account.payment',
            ])
        return res

    @classmethod
    def merged_field(cls, name, Model):
        merged_field = super(SynthesisMenu, cls).merged_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.payment':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'account.payment':
            if name == 'parent':
                merged_field = copy.deepcopy(Model._fields['party'])
                merged_field.model_name = 'party.synthesis.menu.payment'
                return merged_field
            elif name == 'name':
                return Model._fields['state']
        return merged_field


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    def get_action(self, record):
        Model = record.__class__
        if Model.__name__ != 'party.synthesis.menu.payment':
            return super(SynthesisMenuOpen, self).get_action(record)
        domain = PYSONEncoder().encode([('party', '=', record.id)])
        actions = {
            'res_model': 'account.payment',
            'pyson_domain': domain,
            'views': [(None, 'tree'), (None, 'form')]
        }
        return actions
