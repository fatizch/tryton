# -*- coding: utf-8 -*-

import glob


def extract_sh(lines):
    result = []

    def get_indent_level(line):
        i = None
        for (i, c) in enumerate(line):
            if c != ' ':
                break
        return i

    in_sh_code_block = False
    in_config_section = False
    for l in lines:
        if not l.strip('\n'):
            continue
        line_indent = get_indent_level(l.strip('\n'))
        if l.strip() == 'Configuration':  # test bof but good enough
            in_config_section = True
        if in_config_section and '.. code-block:: sh' in l:
            in_sh_code_block = True
            indent_level = line_indent
        elif in_sh_code_block:
            if line_indent is None or line_indent > indent_level:
                result.append(l.lstrip())
            elif line_indent <= indent_level:
                in_sh_code_block = False
    return result


def main():
    """Parse rst files in local directory and print out shell lines of the
    'Configuration' sections.
    """
    sh_lines = []
    for fname in glob.glob('*rst'):
        with open(fname) as f:
            lines = f.readlines()
            sh_lines += extract_sh(lines)

    print '#!/bin/sh\n'
    print ''.join(sh_lines)


if __name__ == '__main__':
    main()
