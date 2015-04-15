from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'MoveLine',
    ]


class MoveLine:
    __name__ = 'account.move.line'

    @classmethod
    def payment_outstanding_group_clause(cls, lines, line_table):
        clause = super(MoveLine, cls).payment_outstanding_group_clause(lines,
            line_table)
        if not lines[0].contract:
            return clause
        return (line_table.contract == lines[0].contract.id) & clause

    @classmethod
    def _process_payment_key(cls, line):
        return super(MoveLine, line)._process_payment_key(cls, line) + \
            (line.contact, )
