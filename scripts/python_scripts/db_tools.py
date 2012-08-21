#!/bin/python
import os
import sys_tools
import shutil

PY_PATH = sys_tools.get_path()

WORK_PATH = sys_tools.get_workspace_path(path)

DATA_PATH = WORK_PATH + 'data' + os.sep

CONF_PATH = WORK_PATH + 'config' + os.sep 
