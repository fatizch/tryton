#!/usr/bin/env python
import sys


def convert_file(input_file, output_file):
    with open(input_file) as i_file, open(output_file, 'w') as o_file:
        for line in i_file.readlines():
            if line.startswith('# -*- coding'):
                continue
            elif line.startswith('# #Title# #'):
                o_file.write('=' * (len(line) - 11) + '\n')
                o_file.write(line[11:])
                o_file.write('=' * (len(line) - 11) + '\n')
            elif line.startswith('# #Comment# #'):
                o_file.write('\n')
                o_file.write(line[13:-1] + '::')
                o_file.write('\n\n')
            elif line.startswith('# #Res# #'):
                o_file.write('    ' + line[9:])
            elif line.startswith('# #Hard# #'):
                o_file.write('    ' + line[10:])
            elif line.lstrip().startswith('#'):
                # No need to copy commented lines
                continue
            elif (line.startswith('else:') or
                    line.startswith('except:') or
                    line.startswith('elif:') or
                    line.startswith('finally:')):
                o_file.write('    ... ' + line)
            elif line.startswith('    '):
                o_file.write('    ... ' + line)
            elif line == '\n':
                continue
            else:
                o_file.write('    >>> ' + line)


if __name__ == '__main__':
    if not len(sys.argv) == 3:
        print 'Usage : python test_converter.py input_file output_file'
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        convert_file(input_file, output_file)
