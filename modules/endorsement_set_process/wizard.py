from trytond.pool import PoolMeta


class StartEndorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.start'

    def get_next_state(self, current_state):
        if not self.endorsement or not self.endorsement.endorsement_set \
                or not self.endorsement.endorsement_set.current_state:
            return super(StartEndorsement, self).get_next_state(current_state)
        return self.get_next_view_or_end(current_state)
