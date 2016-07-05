import copy
from sql.aggregate import Max
from sql import Literal

from trytond.modules.cog_utils import UnionMixin
from trytond.pool import Pool, PoolMeta
from trytond.wizard import Wizard
from trytond.pyson import PYSONEncoder, Eval
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, fields, coop_string
from trytond.modules.currency_cog import ModelCurrency

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'SynthesisMenuMoveLine',
    'SynthesisMenu',
    'SynthesisMenuOpen',
    ]


class Party(ModelCurrency, model.CoopView):
    __name__ = 'party.party'

    payable_icon = fields.Function(
        fields.Char('Payable Icon'),
        'get_payable_receivable_icon')
    payable_today_icon = fields.Function(
        fields.Char('Payable Today Icon'),
        'get_payable_receivable_icon')
    receivable_icon = fields.Function(
        fields.Char('Receivable Icon'),
        'get_payable_receivable_icon')
    receivable_today_icon = fields.Function(
        fields.Char('Receivable Today Icon'),
        'get_payable_receivable_icon')
    negative_payable = fields.Function(
        fields.Numeric('Payable',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_negative_payable', searcher='search_negative_payable')
    negative_payable_today = fields.Function(
        fields.Numeric('Payable Today',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_negative_payable', searcher='search_negative_payable')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls.payable.digits = (16, Eval('currency_digits', 2))
        cls.payable.depends += ['currency_digits']
        cls.payable_today.digits = (16, Eval('currency_digits', 2))
        cls.payable_today.depends += ['currency_digits']
        cls.receivable.digits = (16, Eval('currency_digits', 2))
        cls.receivable.depends += ['currency_digits']
        cls.receivable_today.digits = (16, Eval('currency_digits', 2))
        cls.receivable_today.depends += ['currency_digits']

    def get_currency(self):
        Company = Pool().get('company.company')
        company_id = Transaction().context.get('company', None)
        if company_id:
            return Company(company_id).currency

    def get_negative_payable(self, name):
        amount = getattr(self, name[9:])
        return -1 * amount if amount else amount

    @classmethod
    def search_negative_payable(cls, name, clause):
        clause[0] = clause[0][9:]
        if clause[2] is not None and clause[2] != 0:
            clause[2] = -1 * clause[2]
        if clause[1] is not None:
            if clause[1] == '<':
                clause[1] = '>'
            elif clause[1] == '>':
                clause[1] = '<'
            elif clause[1] == '>=':
                clause[1] = '<='
            elif clause[1] == '<=':
                clause[1] = '>='
            elif clause[1] in ['!=', '=']:
                pass
            else:
                raise NotImplementedError
        return cls.search_receivable_payable(name[9:], clause)

    def get_payable_receivable_icon(self, name):
        code = name[:-5]
        if getattr(self, code) < 0:
            return 'check'
        elif getattr(self, code) > 0:
            return 'rounded_warning'


class SynthesisMenuMoveLine(model.CoopSQL):
    'Party Synthesis Menu Move line'

    __name__ = 'party.synthesis.menu.move.line'

    name = fields.Char('Payments')
    party = fields.Many2One('party.party', 'Party', ondelete='SET NULL')

    @staticmethod
    def table_query():
        pool = Pool()
        move_line = pool.get('account.move.line').__table__()
        party = pool.get('party.party').__table__()
        MoveLineSynthesis = pool.get('party.synthesis.menu.move.line')
        query_table = party.join(move_line, condition=(
            party.id == move_line.party))
        return query_table.select(
            party.id,
            Max(move_line.create_uid).as_('create_uid'),
            Max(move_line.create_date).as_('create_date'),
            Max(move_line.write_uid).as_('write_uid'),
            Max(move_line.write_date).as_('write_date'),
            Literal(coop_string.translate_label(MoveLineSynthesis, 'name')).
            as_('name'), party.id.as_('party'),
            group_by=party.id)

    def get_icon(self, name=None):
        return 'payment'

    def get_rec_name(self, name):
        Move_Line_Synthesis = Pool().get('party.synthesis.menu.move.line')
        return coop_string.translate_label(Move_Line_Synthesis, 'name')


class SynthesisMenu(UnionMixin, model.CoopSQL, model.CoopView):
    'Party Synthesis Menu'

    __name__ = 'party.synthesis.menu'

    @classmethod
    def union_models(cls):
        res = super(SynthesisMenu, cls).union_models()
        res.extend([
            'party.synthesis.menu.move.line',
            'account.move.line',
            ])
        return res

    @classmethod
    def union_field(cls, name, Model):
        union_field = super(SynthesisMenu, cls).union_field(name, Model)
        if Model.__name__ == 'party.synthesis.menu.move.line':
            if name == 'parent':
                return Model._fields['party']
        elif Model.__name__ == 'account.move.line':
            if name == 'parent':
                union_field = copy.deepcopy(Model._fields['party'])
                union_field.model_name = 'party.synthesis.menu.move.line'
                return union_field
            elif name == 'name':
                return Model._fields['state']
        return union_field

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
                'res_id': [record.id],
            }
        return actions
