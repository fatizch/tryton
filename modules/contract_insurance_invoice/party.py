import copy
from sql.aggregate import Max
from sql import Literal

from trytond.modules.cog_utils import MergedMixin
from trytond.pool import Pool
from trytond.wizard import Wizard
from trytond.pyson import PYSONEncoder
from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'SynthesisMenuInvoice',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    ]


class SynthesisMenuInvoice(model.CoopSQL):
    'Party Synthesis Menu Invoice'
    __name__ = 'party.synthesis.menu.invoice'
    name = fields.Char('Invoice')
    party = fields.Many2One('party.party', 'Party')

    @staticmethod
    def table_query():
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceSynthesis = pool.get('party.synthesis.menu.invoice')
        invoice = Invoice.__table__()
        return invoice.select(
            invoice.party.as_('id'),
            Max(invoice.create_uid).as_('create_uid'),
            Max(invoice.create_date).as_('create_date'),
            Max(invoice.write_uid).as_('write_uid'),
            Max(invoice.write_date).as_('write_date'),
            Literal(coop_string.translate_label(InvoiceSynthesis, 'name')).
            as_('name'), invoice.party,
            group_by=invoice.party)

    def get_icon(self, name=None):
        return 'invoice'


class SynthesisMenu(MergedMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'
    __name__ = 'party.synthesis.menu'

    @classmethod
    def merged_models(cls):
        res = super(SynthesisMenu, cls).merged_models()
        res.extend([
            'party.synthesis.menu.invoice',
            'account.invoice',
            ])
        return res

    @classmethod
    def merged_field(cls, name, Model):
        merged_field = super(SynthesisMenu, cls).merged_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.invoice':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'account.invoice':
            if name == 'parent':
                merged_field = copy.deepcopy(Model._fields['party'])
                merged_field.model_name = 'party.synthesis.menu.invoice'
                return merged_field
            elif name == 'name':
                return Model._fields['number']
        return merged_field


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
                    'contract_insurance_invoice.invoice_view_list')
                        ])[0].id, 'tree'),
                    (Pool().get('ir.ui.view').search([('xml_id', '=',
                        'contract_insurance_invoice.invoice_view_form')
                            ])[0].id, 'form')]
        }
        return actions
