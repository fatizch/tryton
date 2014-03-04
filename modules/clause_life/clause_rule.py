from trytond.pool import PoolMeta


__metaclass__ = PoolMeta
__all__ = [
    'ClauseRule',
    ]


class ClauseRule:
    __name__ = 'clause.rule'

    def give_me_all_clauses(self, args):
        # Only add one benficiary clause by default
        beneficiary_clause_found = False
        result = []
        for clause in self.clauses:
            if clause.kind != 'beneficiary':
                result.append(clause)
            elif beneficiary_clause_found:
                continue
            else:
                result.append(clause)
                beneficiary_clause_found = True
        return result, []
