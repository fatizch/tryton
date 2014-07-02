import copy
from sql.aggregate import Max
from sql import Literal

from trytond.modules.cog_utils import UnionMixin
from trytond.pool import Pool
from trytond.wizard import Wizard
from trytond.pyson import PYSONEncoder
from trytond.modules.cog_utils import model, fields, coop_string, utils

__all__ = [
    'SynthesisMenuPayment',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    ]


class SynthesisMenuPayment(model.CoopSQL):
    'Party Synthesis Menu payment'
    __name__ = 'party.synthesis.menu.payment'
    name = fields.Char('Outstanding/Failed Payments')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        Payment = pool.get('account.payment')
        payment = Payment.__table__()
        PaymentSynthesis = pool.get('party.synthesis.menu.payment')
        return payment.select(
            payment.party.as_('id'),
            Max(payment.create_uid).as_('create_uid'),
            Max(payment.create_date).as_('create_date'),
            Max(payment.write_uid).as_('write_uid'),
            Max(payment.write_date).as_('write_date'),
            Literal(coop_string.translate_label(PaymentSynthesis, 'name')).
            as_('name'), payment.party,
            group_by=payment.party)

    def get_icon(self, name=None):
        return 'payment'

    def get_rec_name(self, name):
        PaymentSynthesis = Pool().get('party.synthesis.menu.payment')
        return coop_string.translate_label(PaymentSynthesis, 'name')


class SynthesisMenu(UnionMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def union_models(cls):
        res = super(SynthesisMenu, cls).union_models()
        res.extend([
            'party.synthesis.menu.payment',
            'account.payment',
            ])
        return res

    @classmethod
    def union_field(cls, name, Model):
        union_field = super(SynthesisMenu, cls).union_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.payment':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'account.payment':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['party'])
                union_field.model_name = 'party.synthesis.menu.payment'
                return union_field
            elif name == 'name':
                return Model._fields['state']
        return union_field

    @classmethod
    def build_sub_query(cls, model, table, columns):
        if model != 'account.payment':
            return super(SynthesisMenu, cls).build_sub_query(model, table,
                columns)
        filter_date = utils.today()
        filter_date = filter_date.replace(
            year=filter_date.year - 1)
        return table.select(*columns,
            where=(((table.state == 'processing') | (table.state == 'failed'))
                & (table.date >= filter_date)))

    @classmethod
    def menu_order(cls, model):
        res = super(SynthesisMenu, cls).menu_order(model)
        if model == 'party.synthesis.menu.payment':
            res = 29
        return res


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
