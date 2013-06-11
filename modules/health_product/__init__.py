from trytond.pool import Pool


def register():
    Pool.register(
        module='health_product', type_='model')
