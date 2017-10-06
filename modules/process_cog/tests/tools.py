# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from proteus import Wizard


__all__ = [
    'test_import_processes',
    ]


def test_import_processes():
    ImportProcessWiz = Wizard('import.process')
    for process in ImportProcessWiz.form.processes:
        process.to_install = True
    ImportProcessWiz.execute('import_process')
