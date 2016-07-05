# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
from sql.aggregate import Max
from sql import Literal

from trytond.pool import Pool
from trytond.wizard import Wizard
from trytond.pyson import PYSONEncoder
from trytond.modules.cog_utils import model, fields, coop_string, UnionMixin

__all__ = [
    'SynthesisMenuInvoice',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    ]


class SynthesisMenuInvoice(model.CoopSQL):
    'Party Synthesis Menu Invoice'
    __name__ = 'party.synthesis.menu.invoice'
    name = fields.Char('Invoices')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceSynthesis = pool.get('party.synthesis.menu.invoice')
        party = pool.get('party.party').__table__()
        invoice = Invoice.__table__()
        query_table = party.join(invoice, 'LEFT OUTER', condition=(
            party.id == invoice.party))
        return query_table.select(
            party.id,
            Max(invoice.create_uid).as_('create_uid'),
            Max(invoice.create_date).as_('create_date'),
            Max(invoice.write_uid).as_('write_uid'),
            Max(invoice.write_date).as_('write_date'),
            Literal(coop_string.translate_label(InvoiceSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'invoice'

    def get_rec_name(self, name):
        InvoiceSynthesis = Pool().get('party.synthesis.menu.invoice')
        return coop_string.translate_label(InvoiceSynthesis, 'name')


class SynthesisMenu(UnionMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def union_models(cls):
        res = super(SynthesisMenu, cls).union_models()
        res.extend([
            'party.synthesis.menu.invoice',
            'account.invoice',
            ])
        return res

    @classmethod
    def union_field(cls, name, Model):
        union_field = super(SynthesisMenu, cls).union_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.invoice':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'account.invoice':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['party'])
                union_field.model_name = 'party.synthesis.menu.invoice'
                return union_field
            elif name == 'name':
                return Model._fields['number']
        return union_field

    @classmethod
    def build_sub_query(cls, model, table, columns):
        if model != 'account.invoice':
            return super(SynthesisMenu, cls).build_sub_query(model, table,
                columns)
        return table.select(*columns,
            where=(table.state == 'posted'))

    @classmethod
    def menu_order(cls, model):
        res = super(SynthesisMenu, cls).menu_order(model)
        if model == 'party.synthesis.menu.invoice':
            res = 21
        return res


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    def get_action(self, record):
        Model = record.__class__
        if Model.__name__ != 'party.synthesis.menu.invoice':
            return super(SynthesisMenuOpen, self).get_action(record)
        domain = PYSONEncoder().encode([('party', '=', record.id)])
        actions = {
            'res_model': 'account.invoice',
            'pyson_domain': domain,
            'views': [(Pool().get('ir.ui.view').search([('xml_id', '=',
                    'contract_insurance_invoice.premium_notice_view_list')
                        ])[0].id, 'tree'),
                    (Pool().get('ir.ui.view').search([('xml_id', '=',
                        'account_invoice.invoice_view_form')
                            ])[0].id, 'form')]
        }
        return actions
