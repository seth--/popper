from __future__ import print_function
import Queue
import threading
import argparse
import re
import time
import copy
import pycurl
import sys

from payloads import PAYLOAD_MAPING
from filters import FILTER_MAPING
import output
from constants import *


class WorkerThread(threading.Thread):

    def __init__(self, job_pool, abort_event, result_list, filter_list, maximum_retries, curl_opts):
        super(WorkerThread, self).__init__()
        self._job_pool = job_pool
        self._abort_event = abort_event
        self._result_list = result_list
        self._filter_list = filter_list
        self._maximum_retries = maximum_retries

        self._curl_buffer = ''
        self._curl = pycurl.Curl()
        self._curl.setopt(pycurl.WRITEFUNCTION, self._write_data)
        self._curl.setopt(pycurl.HEADER, True)
        self._curl.setopt(pycurl.NOSIGNAL, True)
        for opt, value in curl_opts:
            self._curl.setopt(opt, value)

    #Callback for curl
    def _write_data(self, buffer):
        self._curl_buffer += buffer

    def run(self):
        job = self._job_pool.get()
        while (job != NO_URLS_LEFT):
            self._curl.setopt(pycurl.URL, job['url'])
            if job['post_data'] != POST_DATA_NOT_SENT:
                # This must be set after pycurl.HTTPGET, pycurl.POST and pycurl.NOBODY
                self._curl.setopt(pycurl.POSTFIELDS, job['post_data'])
            # Restart retry counter
            retries = self._maximum_retries

            while ((retries > 0) or (self._maximum_retries == 0)) and \
                (not self._abort_event.is_set()): # self._maximum_retries == 0 means unlimited retries

                try:
                    self._curl.perform()
                except pycurl.error, e:
                    retries -= 1
                    if retries == 0:
                        print('Giving up on ' + job['url'] + ': ' + e[1] + "\n", end='', file=sys.stderr)
                        self._result_list.put(JOB_STATUS_ABORTED)
                else:
                    retries = 0
                    result = [{'name': 'url', 'value': job['url']},
                              {'name': 'post_data', 'value': job['post_data']},
                              {'name': 'time', 'value': self._curl.getinfo(pycurl.TOTAL_TIME) - self._curl.getinfo(pycurl.PRETRANSFER_TIME)},
                              {'name': 'code', 'value': self._curl.getinfo(pycurl.RESPONSE_CODE)},
                              {'name': 'size', 'value': len(self._curl_buffer)},
                              {'name': 'lines', 'value': self._curl_buffer.count("\n")}]

                    for filter in self._filter_list:
                        filter_result = filter.filter(self._curl, self._curl_buffer)
                        if (not bool(filter_result)) != filter.negate: # != is logical xor for booleans
                            self._result_list.put(JOB_STATUS_HIDDEN)
                            break
                        result.append(filter_result)
                    else:
                        self._result_list.put(result)
            self._curl_buffer = ''
            self._job_pool.task_done()
            job = self._job_pool.get()
        self._curl.close()
        self._job_pool.task_done()


class Popper():

    # Transforms an url with placeholders in lots of urls with the payloads applied
    def generate_jobs(self, url_template, post_data_template, args):
        regex = '\[(' + '|'.join(map(re.escape, PAYLOAD_MAPING)) + ')\]'
        match = re.search(regex, url_template)
        if match:
            p = PAYLOAD_MAPING[match.group(1)](args[match.group(1)])
            for data in p.get_data():
                for x in self.generate_jobs(url_template.replace(match.group(0), data, 1), post_data_template, copy.deepcopy(args)):
                    yield {'url': x['url'], 'post_data': x['post_data']}
        elif post_data_template != POST_DATA_NOT_SENT:
            match = re.search(regex, post_data_template)
            if match:
                p = PAYLOAD_MAPING[match.group(1)](args[match.group(1)])
                for data in p.get_data():
                    for x in self.generate_jobs(url_template, post_data_template.replace(match.group(0), data, 1), copy.deepcopy(args)):
                        yield {'url': x['url'], 'post_data': x['post_data']}
            else:
                yield {'url': url_template, 'post_data': post_data_template}
        else:
            yield {'url': url_template, 'post_data': post_data_template}

    #Prints results while waiting to add a job
    def put_job_and_print(self, result_list, job_pool, job):
            success = False
            while success == False:
                try:
                    job_pool.put(job, True, 0.1)
                    success = True
                except Queue.Full:
                    pass
                try:
                    self._output.print_result(result_list.get_nowait())
                except Queue.Empty:
                    pass

    def __init__(self):
        # Parse argv
        parser = argparse.ArgumentParser(description='')
        parser.add_argument('url', type=str, help='an integer for the accumulator')
        parser.add_argument('--postdata', type=str, default=POST_DATA_NOT_SENT, help='encoded post data. Implies --post')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--get', action='store_true', help='uses GET method')
        group.add_argument('--post', action='store_true', help='uses POST method')
        group.add_argument('--head', action='store_true', help='uses HEAD method')
        parser.add_argument('--header', type=str, default=[], nargs='*', help='extra http headers (--header "foo: bar" "baz: qux")')
        parser.add_argument('--method', type=str, help='custom http method, useful for DELETE or PUT (see CURLOPT_CUSTOMREQUEST)')

        parser.add_argument('--threads', '-t', type=int, default=10, help='number of threads (default: 10)')
        parser.add_argument('--negate', type=str, default=[], nargs='*', help='list of filter to negate (to show only 200 codes: --negate hc --hc 200)')
        parser.add_argument('--output', type=str, default='table', choices=['table','json','csv'], help='output format')
        parser.add_argument('--columns', type=str, default=[], nargs='*', help='Columns to output')

        parser.add_argument('--retry', type=int, default=3, help='times to retry a request when something goes wrong (0 for unlimited)')
        parser.add_argument('--proxy', type=str, default='', help='[socks4|socks4a|socks5|socks5h|http]://host:port')
        parser.add_argument('--timeout', type=int, default=30, help='timeout in seconds')
        parser.add_argument('--connect-timeout', type=int, default=0, help='timeout in seconds for the connection phase')
        parser.add_argument('--fresh', action='store_true', help='don\'t reuse connections')
        parser.add_argument('--no-verify', action='store_true', help='ignore SSL errors')

        for payload_name in PAYLOAD_MAPING:
            parser.add_argument('--' + payload_name, type=str, default='', nargs='*', help=PAYLOAD_MAPING[payload_name].CLI_HELP)
        for filter_name in FILTER_MAPING:
            FILTER_MAPING[filter_name].set_arguments(parser) #TODO: payloads should have this too

        args = vars(parser.parse_args())

        # Curl options
        curl_opts = [(pycurl.HTTPGET, args['get']),
                     (pycurl.POST, args['post']),
                     (pycurl.NOBODY, args['head']),
                     (pycurl.HTTPHEADER, args['header']),
                     (pycurl.PROXY, args['proxy']),
                     (pycurl.TIMEOUT, args['timeout']),
                     (pycurl.CONNECTTIMEOUT, args['connect_timeout']),
                     (pycurl.FORBID_REUSE, args['fresh']),
                     (pycurl.SSL_VERIFYPEER, (0 if args['no_verify'] else 1)),
                     (pycurl.SSL_VERIFYHOST, (0 if args['no_verify'] else 2))]
        if args['method']:
            curl_opts.append((pycurl.CUSTOMREQUEST, args['method']))

        # postdata is different because it can have payloads
        # If CURLOPT_POST is set to 1, CURLOPT_POSTFIELDS must be present
        # See curl.haxx.se/libcurl/c/CURLOPT_POST.html
        if (args['postdata'] == POST_DATA_NOT_SENT) and args['post']:
            args['postdata'] = ''

        # This formats the output
        if args['output'] == 'table':
            self._output = output.Table()
        else:
            print('Not implemented')
            sys.exit()

        # Initialize variables
        job_pool = Queue.Queue(args['threads'] * 10)
        result_list = Queue.Queue(0)

        # Make a list with the needed filter objects
        # TODO: find a better way
        filter_list = []
        for filter_name in FILTER_MAPING:
            try:
                arg = args[filter_name]
                if arg != None:
                    filter = FILTER_MAPING[filter_name](arg)
                    if filter_name in args['negate']:
                            filter.negate = True
                    filter_list.append(filter)
            except IndexError:
                pass

        try:
            # Start all the threads
            abort_event = threading.Event()
            for x in xrange(args['threads']):
               WorkerThread(job_pool, abort_event, result_list, filter_list, args['retry'], curl_opts).start()

            # Add the base url to the queue
            regex = '\[(' + '|'.join(map(re.escape, PAYLOAD_MAPING)) + ')\]'
            if args['postdata'] == POST_DATA_NOT_SENT:
                job_pool.put({'url': re.sub(regex, '', args['url']), 'post_data': POST_DATA_NOT_SENT})
            else:
                job_pool.put({'url': re.sub(regex, '', args['url']), 'post_data': re.sub(regex, '', args['postdata'])})
            # Print the first result
            self._output.print_result(result_list.get())

            # Add all the urls to the queue
            for x in self.generate_jobs(args['url'], args['postdata'], args):
                self.put_job_and_print(result_list, job_pool, x)

            # When the threads get this, they will exit
            # TODO: change this (using threading.Event()? can it be made thread safe to avoid blocking on job_list.get()?)
            for x in xrange(args['threads']):
                self.put_job_and_print(result_list, job_pool, NO_URLS_LEFT)

            # Wait for all jobs to be finished while showing results
            # This may exit with threads still alive, but those have already got NO_URLS_LEFT and are exiting
            while job_pool.empty() == False:
                try:
                    self._output.print_result(result_list.get_nowait())
                    time.sleep(0.1)
                except Queue.Empty:
                    pass

        except KeyboardInterrupt: #TODO: this should handle other exceptions
            print('Aborting threads...' + "\n", end='', file=sys.stderr)
            abort_event.set()
            # Make sure no thread locks waiting for a job
            for x in xrange(args['threads']):
                self.put_job_and_print(result_list, job_pool, NO_URLS_LEFT)

        # Finish showing results
        while result_list.empty() == False:
            self._output.print_result(result_list.get_nowait())

        self._output.print_summary()

Popper()
