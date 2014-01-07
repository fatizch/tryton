__all__ = [
    'ArgsDoNotMatchException',
    'update_args_with_subscriber',
    ]


class ArgsDoNotMatchException(Exception):
    pass


def update_args_with_subscriber(args):
    # TODO : Remove this
    subscriber = None
    if 'contract' in args:
        subscriber = args['contract'].subscriber
        args['subscriber'] = subscriber
    elif 'subscriber' in args:
        subscriber = args['subscriber']
    if not subscriber:
        raise ArgsDoNotMatchException
    if subscriber.__name__ == 'party.party':
        if hasattr(subscriber, 'is_person') and subscriber.is_person:
            args['subscriber_person'] = subscriber
        elif hasattr(subscriber, 'is_company') and subscriber.is_company:
            args['subscriber_company'] = subscriber
        return
