from trytond.pool import Pool


def register():
    Pool.register(
        module='bank', type_='model')
