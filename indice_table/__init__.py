from trytond.pool import Pool


def register():
    Pool.register(
        module='indice_table', type_='model')
