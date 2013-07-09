from trytond.pool import Pool


def register():
    Pool.register(
        module='bank_fr', type_='model')
