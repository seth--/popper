from __future__ import print_function

from constants import *

class Table():
    def __init__(self):
        self._hidden_results = 0
        self._aborted_jobs = 0
        self._first_line = True

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
        order = ['code', 'lines', 'size', 'time', None, 'url', 'post_data']
        if field['name'] in order:
            return order.index(field['name'])
        else:
            return order.index(None)

    def _print_first_line(self, result):
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
                if field['name'] == 'size':
                    field['value'] = self._bytes_to_human(field['value'])
                elif (field['name'] == 'post_data') and (field['value'] == POST_DATA_NOT_SENT):
                    continue

                if field['name'] in formats:
                    format = formats[field['name']]
                else:
                    format = '{0}'
                    field['value'] = field['value'].encode('unicode_escape')

                output.append(format.format(field['value']))
            print(' | '.join(output) + "\n", end='')



            #Orden: code, lines, size, time, OTHERS, url, query_string, post_data
    def print_summary(self):
        print("\nHidden: " + str(self._hidden_results) + "\n", end='')
        if self._aborted_jobs > 0:
            print("Aborted jobs: " + str(self._aborted_jobs) + "\n", end='')


class CSV():
    pass

class JSON():
    pass
