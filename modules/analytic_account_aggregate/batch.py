# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.server_context import ServerContext


__all__ = [
    'ExtractAggregatedMove',
    ]


class ExtractAggregatedMove:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.aggregated.extract'

    @classmethod
    def parse_params(cls, params):
        params = super(ExtractAggregatedMove, cls).parse_params(params)
        params['flush_size'] = int(params.get('flush_size'))
        if params.get('analytic', False) and params.get('job_size') != 0:
            assert params.get('flush_size') == 0
        return params

    @classmethod
    def _analytic_match_line(cls, line, analytic):
        # Lines indexes are defined into the method 'transform_values' of
        # account_aggregate/batch.py (and all it's overrides)
        Journal = Pool().get('account.journal')
        l_journal, a_journal = Journal.browse([line[8], analytic[8]])
        agg_idx = 8 if l_journal.aggregate else 0
        return all(line[i] == analytic[i] for i in (7, agg_idx, 9, 10, 11))

    @classmethod
    def lines_with_analytic(cls, lines, *args, **kwargs):
        cursor = Transaction().connection.cursor()
        treatment_date = datetime.datetime.strftime(kwargs.get(
                'treatment_date'), '%Y-%m-%d')
        with ServerContext().set_context(
                snap_ref=kwargs.get('reference', None),
                batch_treatment_date=treatment_date):
            analytic_query = Pool().get('analytic_account.line.aggregated'
                ).table_query()
        cursor.execute(*analytic_query)
        analytic_lines = (rows for rows in cursor.fetchall())
        unmatched_analytic_line = None
        # Aggregated lines and aggregated analytic lines are sorted in the same
        # way.
        for line_packet in lines:
            packet_lines = []
            for line_row in line_packet:
                packet_lines.append(line_row)
                if unmatched_analytic_line:
                    if cls._analytic_match_line(
                         line_row, unmatched_analytic_line):
                        packet_lines.append(unmatched_analytic_line)
                        unmatched_analytic_line = None
                    else:
                        continue
                for analytic_row in analytic_lines:
                    if cls._analytic_match_line(line_row, analytic_row):
                        packet_lines.append(analytic_row)
                    else:
                        unmatched_analytic_line = analytic_row
                        break
            yield tuple(packet_lines)
        assert len(list(analytic_lines)) == 0 and \
            unmatched_analytic_line is None

    @classmethod
    def select_ids(cls, *args, **kwargs):
        lines = super(ExtractAggregatedMove, cls).select_ids(
            *args, **kwargs)
        if not kwargs.get('analytic', False):
            for line in lines:
                yield line
        else:
            for line in cls.lines_with_analytic(lines, *args, **kwargs):
                yield line
