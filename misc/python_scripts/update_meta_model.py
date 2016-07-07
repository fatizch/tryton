from trytond.pool import Pool


def update_model(files):
    if not check_debug_installed():
        return
    models = extract_models(files)
    do_update_models(models)


def check_debug_installed():
    Module = Pool().get('ir.module')
    return bool(Module.search([
                ('name', '=', 'debug'),
                ('state', '=', 'installed')]))


def extract_models(files):
    models = set()
    for cur_file in files:
        with open(cur_file, 'r') as f:
            if cur_file.endswith('.py'):
                models |= extract_py_models(f)
            elif cur_file.endswith('.xml'):
                models |= extract_xml_models(f)
    pool = Pool()
    return [x for x in models if pool.get(x)]


def extract_py_models(f):
    models = set()
    for line in f.readlines():
        line = line.strip()
        if line.startswith('__name__'):
            models.add(line[12:-1])
    return models


def extract_xml_models(f):
    models = set()
    for line in f.readlines():
        line = line.strip()
        if line.startswith('<field name="model">'):
            models.add(line[20:-8])
    return models


def do_update_models(models):
    Pool().get('debug.model').refresh(None, models)
