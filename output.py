from __future__ import print_function

from constants import *

class Table():
    def __init__(self):
        self._hidden_results = 0
        self._aborted_jobs = 0
        self._first_line = True
        self.hide = []

    def _bytes_to_human(self, num):
        # Takes a size in bytes and makes it human readable
        format = '{0:d}{1}'
        for x in ['B','KB','MB','GB']:
            if num < 1024.0:
                return format.format(num, x)
            num /= 1024.0
            format = '{0:.1f}{1}'
        return format.format(num, 'TB')

    def _sort(self, field):
        # Used as key argument for sorted()
        order = ['code', 'lines', 'size', 'time', None, 'url', 'post_data', 'header']
        if field['name'] in order:
            return order.index(field['name'])
        else:
            return order.index(None)

    def _print_first_line(self, result):
        # The first line has the columns names
        self._first_line = False
        basic_widths = {'code': 4,
                       'lines': 8,
                       'size': 10,
                       'time': 9}
        output = []
        for field in result:
            # Spcial case
            if (field['name'] == 'post_data') and (field['value'] == POST_DATA_NOT_SENT):
                continue
            elif (field['name'] == 'header') and (len(field['value']) == 0):
                continue
            elif field['name'] in self.hide:
                continue

            if 'width' in field:
                width = field['width']
            elif field['name'] in basic_widths:
                width = basic_widths[field['name']]
            else:
                width = len(field['name']) + 2

            output.append(str(field['name']).center(width))

        print('|'.join(output) + "\n", end='')

    def print_result(self, result):
        if result == JOB_STATUS_HIDDEN:
            self._hidden_results += 1
        elif result == JOB_STATUS_ABORTED:
            self._aborted_jobs += 1
        else:
            result = sorted(result, key=self._sort)
            if self._first_line:
                self._print_first_line(result)

            formats = {'code': '{0:>3d}',
                       'lines': '{0:>6d}',
                       'size': '{0:>8s}',
                       'time': '{0:>7.3f}'}
            output = []
            for field in result:
                # Special cases:
                if (field['name'] == 'post_data') and (field['value'] == POST_DATA_NOT_SENT):
                    continue
                elif field['name'] in self.hide:
                    continue
                elif field['name'] == 'header':
                    if len(field['value']) == 0:
                        continue
                    else:
                        field['value'] = "\r\n".join(field['value'])
                elif field['name'] == 'size':
                    field['value'] = self._bytes_to_human(field['value'])


                if field['name'] in formats:
                    format = formats[field['name']]
                else:
                    format = '{0}'
                    field['value'] = field['value'] = field['value'].replace("\r", "\\r").replace("\n", "\\n")

                output.append(format.format(field['value']))
            print(' | '.join(output) + "\n", end='')

    def print_summary(self):
        # The last line
        print("\nHidden: " + str(self._hidden_results) + "\n", end='')
        if self._aborted_jobs > 0:
            print("Aborted jobs: " + str(self._aborted_jobs) + "\n", end='')


class CSV():
    # TODO
    pass

class JSON():
    # TODO
    pass
