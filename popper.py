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

NO_URLS_LEFT = False
POST_DATA_NOT_SENT = False
JOB_STATUS_HIDDEN = 1
JOB_STATUS_ABORTED = 2


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
                    for filter in self._filter_list:
                        if (not filter.filter(job['url'], self._curl, self._curl_buffer)) != filter.negate: # != is logical xor for booleans
                            self._result_list.put(JOB_STATUS_HIDDEN)
                            break
                    else:
                        self._result_list.put({'url': job['url'],
                                               'time': self._curl.getinfo(pycurl.TOTAL_TIME) - self._curl.getinfo(pycurl.PRETRANSFER_TIME),
                                               'code': self._curl.getinfo(pycurl.RESPONSE_CODE),
                                               'size': len(self._curl_buffer),
                                               'lines': self._curl_buffer.count("\n")})
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
                for x in self.generate_jobs(url_template.replace(match.group(0), data, 1), post_data_template, copy.deepcopy(args)): #TODO: deepcopy() just works. Probably something is wrong
                    yield {'url': x['url'], 'post_data': x['post_data']}
        elif post_data_template != POST_DATA_NOT_SENT:
            match = re.search(regex, post_data_template)
            if match:
                p = PAYLOAD_MAPING[match.group(1)](args[match.group(1)])
                for data in p.get_data():
                    for x in self.generate_jobs(url_template, post_data_template.replace(match.group(0), data, 1), copy.deepcopy(args)): #TODO: deepcopy() just works. Probably something is wrong
                        yield {'url': x['url'], 'post_data': x['post_data']}
            else:
                yield {'url': url_template, 'post_data': post_data_template}
        else:
            yield {'url': url_template, 'post_data': post_data_template}

    def print_result(self, result):
        if result == JOB_STATUS_HIDDEN:
            self._hidden_results += 1
        elif result == JOB_STATUS_ABORTED:
            self._aborted_jobs += 1
        else:
            # TODO: lines should be /1000 and add 'k' to save space
            # TODO: size should use kb, mb, etc to save space
            # TODO: what happens with long waits in time? also, the format is wrong
            print(str(result['code']).ljust(3) + ' ' + \
                  str(result['lines']).ljust(4) + ' ' + \
                  str(result['size']).ljust(8) + ' ' + \
                  str(result['time']).ljust(8) + ' ' + \
                  result['url'] + "\n", end='')

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
                    self.print_result(result_list.get_nowait())
                except Queue.Empty:
                    pass

    def __init__(self):
        # Parse argv
        parser = argparse.ArgumentParser(description='')
        parser.add_argument('url', type=str, help='an integer for the accumulator')
        parser.add_argument('--postdata', type=str, help='encoded post data. Implies --post')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--get', action='store_true', help='uses GET method')
        group.add_argument('--post', action='store_true', help='uses POST method')
        group.add_argument('--head', action='store_true', help='uses HEAD method')
        parser.add_argument('--header', type=str, default=[], nargs='*', help='extra http headers (--header "foo: bar" "baz: qux")')
        parser.add_argument('--method', type=str, help='custom http method, useful for DELETE or PUT (see CURLOPT_CUSTOMREQUEST)')

        parser.add_argument('--threads', '-t', type=int, default=10, help='number of threads (default: 10)')
        parser.add_argument('--negate', type=str, default=[], nargs='*', help='list of filter to negate (to show only 200 codes: --negate hc --hc 200)')

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
        if args['postdata']:
            post_data = args['postdata']
        elif args['post']:
            # If CURLOPT_POST is set to 1, CURLOPT_POSTFIELDS must be present
            # See curl.haxx.se/libcurl/c/CURLOPT_POST.html
            post_data = ''  
        else:
            post_data = POST_DATA_NOT_SENT
        if args['method']:
            curl_opts.append((pycurl.CUSTOMREQUEST, args['method']))

        self._hidden_results = 0
        self._aborted_jobs = 0
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
            if post_data == POST_DATA_NOT_SENT:
                job_pool.put({'url': re.sub(regex, '', args['url']), 'post_data': POST_DATA_NOT_SENT})
            else:
                job_pool.put({'url': re.sub(regex, '', args['url']), 'post_data': re.sub(regex, '', post_data)})
            # Print the first result
            self.print_result(result_list.get())

            # Add all the urls to the queue
            for x in self.generate_jobs(args['url'], post_data, args):
                self.put_job_and_print(result_list, job_pool, x)

            # When the threads get this, they will exit
            # TODO: change this (using threading.Event()? can it be made thread safe to avoid blocking on job_list.get()?)
            for x in xrange(args['threads']):
                self.put_job_and_print(result_list, job_pool, NO_URLS_LEFT)

            # Wait for all jobs to be finished while showing results
            # This may exit with threads still alive, but those have already got NO_URLS_LEFT and are exiting
            while job_pool.empty() == False:
                try:
                    self.print_result(result_list.get_nowait())
                    time.sleep(0.1)
                except Queue.Empty:
                    pass

        except KeyboardInterrupt:
            print('Aborting threads...' + "\n", end='', file=sys.stderr)
            abort_event.set()
            # Make sure no thread locks waiting for a job
            for x in xrange(args['threads']):
                self.put_job_and_print(result_list, job_pool, NO_URLS_LEFT)

        # Finish showing results
        while result_list.empty() == False:
            self.print_result(result_list.get_nowait())

        print("\nHidden: " + str(self._hidden_results) + "\n", end='')
        if self._aborted_jobs > 0:
            print("Aborted jobs: " + str(self._aborted_jobs) + "\n", end='')


Popper()
