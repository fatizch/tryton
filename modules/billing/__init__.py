from trytond.pool import Pool


def register():
    Pool.register(
        module='billing', type_='model')
