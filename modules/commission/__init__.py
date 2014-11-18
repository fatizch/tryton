from trytond.pool import Pool


def register():
    Pool.register(
        module='commission', type_='model')
