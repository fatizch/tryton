import os
import sys_tools
import sys
import subprocess

from optparse import OptionParser

PY_PATH = sys_tools.get_path()

WORK_PATH = sys_tools.get_workspace_path(PY_PATH)

DATA_PATH = WORK_PATH + 'data' + os.sep

CONF_PATH = WORK_PATH + 'config' + os.sep

TRYTOND_PATH = WORK_PATH + 'trytond' + os.sep

PROTEUS_PATH = WORK_PATH + 'proteus' + os.sep

sys.path.extend([PROTEUS_PATH, TRYTOND_PATH])

if __name__ == '__main__':
    parser = OptionParser(usage="Usage: %prog script_path script_args")
    options, args = parser.parse_args()
    extra_args = args[1:]
    subprocess.call(
        [sys.executable,
        os.path.abspath(args[0])] + extra_args,
        env={"PYTHONPATH": ":".join(sys.path)})

