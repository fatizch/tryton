from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.modules.cog_utils import export, fields, utils, coop_string

__metaclass__ = PoolMeta

__all__ = [
    'Move',
    'Line',
    ]


class Move(export.ExportImportMixin):
    __name__ = 'account.move'

    icon = fields.Function(
        fields.Char('Icon'),
        'get_icon')
    kind = fields.Function(
        fields.Selection([('', '')], 'Kind'),
        'get_kind')
    origin_item = fields.Function(
        fields.Reference('Origin', selection='get_origin'),
        'get_origin_item')
    cancel_moves = fields.One2Many('account.move', 'origin', 'Cancel Moves')
    cancel_move = fields.Function(
        fields.Many2One('account.move', 'Cancel Move'),
        'get_cancel_move')
    is_origin_canceled = fields.Function(
        fields.Boolean('Origin Canceled'),
        'get_is_origin_canceled')
    synthesis_rec_name = fields.Function(
        fields.Char('Information'),
        'get_synthesis_rec_name')

    def get_kind(self, name):
        return ''

    def get_icon(self, name):
        if self.origin_item and getattr(self.origin_item, 'icon', None):
            return self.origin_item.icon
        elif self.is_origin_canceled:
            return 'cancel-list'

    def get_origin_item(self, name):
        if self.origin:
            if self.origin.__name__ == 'account.move':
                origin_item = self.origin.origin_item
            else:
                origin_item = self.origin
            if origin_item:
                return '%s,%s' % (origin_item.__name__, origin_item.id)

    def get_cancel_move(self, name):
        return self.cancel_moves[0].id if self.cancel_moves else None

    def get_is_origin_canceled(self, name):
        return (self.cancel_move is not None
            or self.origin and self.origin.__name__ == 'account.move')

    def get_synthesis_rec_name(self, name):
        if self.origin:
            if (getattr(self.origin, 'get_synthesis_rec_name', None)
                    is not None):
                return self.origin.get_synthesis_rec_name(name)
            return self.origin.get_rec_name(name)
        elif self.description and self.journal:
            return '%s %s' % (coop_string.translate_value(
                    self.journal, 'type'), self.description)
        elif self.description:
            return self.description
        elif self.journal:
            return self.journal.rec_name
        return self.get_rec_name(name)

    def _cancel_default(self):
        defaults = super(Move, self)._cancel_default()
        if 'date' in defaults or self.date >= utils.today():
            return defaults
        date = utils.today()
        period_id = Pool().get('account.period').find(self.company.id,
            date=date)
        defaults.update({
                'date': date,
                'period': period_id,
                })
        return defaults


class Line(export.ExportImportMixin):
    'Account Move Line'
    __name__ = 'account.move.line'

    kind = fields.Function(
        fields.Char('Kind'),
        'get_move_field')
    kind_string = fields.Function(
        fields.Char('Kind'),
        'get_kind_string')
    account_kind = fields.Function(
        fields.Char('Account Kind'), 'get_account_kind')
    reconciled_with = fields.Function(
        fields.Many2Many('account.move.line', None, None, 'Reconciled With'),
        'get_reconciled_with')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'), 'get_currency_symbol')
    color = fields.Function(
        fields.Char('Color'),
        'get_color')
    icon = fields.Function(
        fields.Char('Icon'),
        'get_icon')
    origin_item = fields.Function(fields.Reference('Origin',
            selection='get_origin'),
        'get_move_field')
    is_reconciled = fields.Function(
        fields.Boolean('Reconciled'),
        'get_is_reconciled', searcher='search_is_reconciled')
    is_origin_canceled = fields.Function(
        fields.Boolean('Origin Canceled'),
        'get_move_field')
    synthesis_rec_name = fields.Function(
        fields.Char('Information', readonly=True),
        'get_synthesis_rec_name')
    post_date = fields.Function(
        fields.Date('Post Date'),
        'get_move_field', searcher='search_move_field')

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls.account.select = False

    @classmethod
    def __register__(cls, module_name):
        super(Line, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # These indexes optimizes invoice generation
        # And certainly other coog services
        table.index_action('account', 'remove')
        table.index_action(['account', 'reconciliation'], 'add')

    @classmethod
    def view_attributes(cls):
        return super(Line, cls).view_attributes() + [(
                '/tree',
                'colors',
                Eval('color', 'black'))]

    def get_reconciled_with(self, name):
        if self.reconciliation is None:
            return
        return [line.id for line in self.reconciliation.lines if line != self]

    def get_currency_symbol(self, name):
        return self.account.currency.symbol if self.account else ''

    def get_icon(self, name=None):
        if self.move.icon:
            return self.move.icon
        elif self.is_reconciled:
            return 'coopengo-reconciliation'

    def get_color(self, name):
        if self.is_origin_canceled:
            return 'red'
        elif self.is_reconciled:
            return 'green'
        return 'black'

    def get_account_kind(self, name):
        return self.account.kind if self.account else ''

    def get_is_reconciled(self, name):
        return self.reconciliation is not None

    def get_synthesis_rec_name(self, name):
        return self.move.synthesis_rec_name

    def get_kind_string(self, name):
        return coop_string.translate(self.move, 'kind')

    @classmethod
    def search_is_reconciled(cls, name, clause):
        if (clause[1] == '=' and clause[2]
                or clause[1] == '!=' and not clause[2]):
            res = [('reconciliation', '!=', None)]
        elif (clause[1] == '=' and not clause[2]
                or clause[1] == '!=' and clause[2]):
            res = [('reconciliation', '=', None)]
        return res

    @classmethod
    def split_lines(cls, splits, journal=None):
        # splits is a list of line / split_amount tuples :
        # Line.split_lines([line1, split1), (line2, split2)], journal=...)
        if not splits:
            return []
        pool = Pool()
        Move = pool.get('account.move')
        split_moves = {}
        split_amounts = {}
        for line, amount_to_split in splits:
            split_amounts[line] = amount_to_split
            split_moves[line] = line.split(amount_to_split, journal)
        Move.save(split_moves.values())
        Move.post(split_moves.values())
        split_lines = {}
        for source_line, split_move in split_moves.iteritems():
            # Order of move.lines may not always be keep after saving / posting
            split_amount = split_amounts[source_line]
            split, remaining, compensation = None, None, None
            for line in split_move.lines:
                if abs(line.amount) == abs(source_line.amount):
                    compensation = line
                elif abs(line.amount) == split_amount:
                    split = line
                else:
                    remaining = line
            split_lines[source_line] = (split, remaining, compensation)
        return split_lines

    def split(self, amount_to_split, journal=None):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Journal = pool.get('account.journal')

        if journal is None:
            journal = Journal.search([('type', '=', 'split')])[0]

        split_move = Move(journal=journal, company=self.move.company,
            date=utils.today())
        split, remaining, compensation = [
            Line(party=self.party, account=self.account, credit=0, debit=0),
            Line(party=self.party, account=self.account, credit=0, debit=0),
            Line(party=self.party, account=self.account, credit=0, debit=0),
            ]

        if self.credit and self.credit > 0 or self.debit and self.debit < 0:
            base = self.credit - self.debit
            source, dest = 'credit', 'debit'
        else:
            base = self.debit - self.credit
            source, dest = 'debit', 'credit'

        assert amount_to_split < base
        setattr(split, source, amount_to_split)
        setattr(remaining, source, base - amount_to_split)
        setattr(compensation, dest, base)
        split_move.lines = [split, remaining, compensation]
        return split_move

    def _order_move_field(name):
        def order_field(tables):
            pool = Pool()
            Move = pool.get('account.move')
            field = Move._fields[name]
            table, _ = tables[None]
            move_tables = tables.get('move')
            if move_tables is None:
                move = Move.__table__()
                move_tables = {
                    None: (move, move.id == table.move),
                    }
                tables['move'] = move_tables
            return field.convert_order(name, move_tables, Move)
        return staticmethod(order_field)
    order_post_date = _order_move_field('post_date')
