import copy
from sql.aggregate import Max
from sql import Literal

from trytond.modules.cog_utils import MergedMixin
from trytond.pool import Pool
from trytond.wizard import Wizard
from trytond.pyson import PYSONEncoder
from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'SynthesisMenuMoveLine',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    ]


class SynthesisMenuMoveLine(model.CoopSQL):
    'Party Synthesis Menu Move line'
    __name__ = 'party.synthesis.menu.move.line'
    name = fields.Char('Payments')
    party = fields.Many2One('party.party', 'Party')

    @staticmethod
    def table_query():
        pool = Pool()
        move_line = pool.get('account.move.line').__table__()
        party = pool.get('party.party').__table__()
        Move_Line_Synthesis = pool.get('party.synthesis.menu.move.line')
        query_table = party.join(move_line, condition=(
            party.id == move_line.party))
        return query_table.select(
            party.id,
            Max(move_line.create_uid).as_('create_uid'),
            Max(move_line.create_date).as_('create_date'),
            Max(move_line.write_uid).as_('write_uid'),
            Max(move_line.write_date).as_('write_date'),
            Literal(coop_string.translate_label(Move_Line_Synthesis, 'name')).
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
            'party.synthesis.menu.move.line',
            'account.move.line',
            ])
        return res

    @classmethod
    def merged_field(cls, name, Model):
        merged_field = super(SynthesisMenu, cls).merged_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.move.line':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'account.move.line':
            if name == 'parent':
                merged_field = copy.deepcopy(Model._fields['party'])
                merged_field.model_name = 'party.synthesis.menu.move.line'
                return merged_field
            elif name == 'name':
                return Model._fields['state']
        return merged_field

    @classmethod
    def menu_order(cls, model):
        res = super(SynthesisMenu, cls).menu_order(model)
        if model == 'party.synthesis.menu.move.line':
            res = 20
        return res

    @classmethod
    def build_sub_query(cls, model, table, columns):
        pool = Pool()
        if model != 'account.move.line':
            return super(SynthesisMenu, cls).build_sub_query(model, table,
                columns)
        account = pool.get('account.account').__table__()
        move = pool.get('account.move').__table__()
        return table.join(account, condition=((account.id == table.account)
                & (account.kind == 'receivable'))).\
            join(move, condition=((move.id == table.move))).\
            select(*columns,
                where=((table.credit > 0) & (table.reconciliation == None)))


class SynthesisMenuOpen(Wizard):
    'Open Party Synthesis Menu'
    __name__ = 'party.synthesis.menu.open'

    def get_action(self, record):
        Model = record.__class__
        if (Model.__name__ != 'party.synthesis.menu.move.line' and
                Model.__name__ != 'account.move.line'):
            return super(SynthesisMenuOpen, self).get_action(record)
        if Model.__name__ == 'party.synthesis.menu.move.line':
            domain = PYSONEncoder().encode([('party', '=', record.id),
                    ('account.kind', '=', 'receivable'),
                    ('credit', '>', 0)])
            actions = {
                'res_model': 'account.move.line',
                'pyson_domain': domain,
                'views': [(Pool().get('ir.ui.view').search([('xml_id', '=',
                    'account_cog.move_line_view_synthesis_tree')])[0].id,
                    'tree'),
                    (Pool().get('ir.ui.view').search([('xml_id', '=',
                    'account_cog.move_line_view_synthesis_form')])[0].id,
                    'form')]
            }
        elif Model.__name__ == 'account.move.line':
            actions = {
                'res_model': 'account.move.line',
                'views': [(Pool().get('ir.ui.view').search([('xml_id', '=',
                    'account_cog.move_line_view_synthesis_form')])[0].id,
                    'form')],
                'res_id': record.id
            }
        return actions
