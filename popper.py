# http://pycurl.sourceforge.net/doc/index.html
# http://curl.haxx.se/libcurl/c/
# https://github.com/pycurl/pycurl/blob/master/examples/retriever-multi.py
# http://www.devshed.com/c/a/Python/Basic-Threading-in-Python/
# https://docs.python.org/2/library/thread.html
# https://docs.python.org/2/library/queue.html#module-Queue
# https://docs.python.org/2/library/argparse.html#module-argparse
# http://www.ibm.com/developerworks/library/os-curl/index.html

import Queue
import threading
import argparse
import re
import time
import copy
import pycurl

from payloads import PAYLOAD_MAPING
from filters import FILTER_MAPING

NO_URLS_LEFT = False


class WorkerThread(threading.Thread):

    def __init__(self, job_pool, result_list, filter_list, maximum_retries, curl_opts):
        super(WorkerThread, self).__init__()
        self._job_pool = job_pool
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
        global result_list

        job = self._job_pool.get()
        while job != NO_URLS_LEFT:
            self._curl.setopt(pycurl.URL, job)
            retries = self._maximum_retries # Restart retry counter
            while (retries > 0) or (self._maximum_retries == 0): # self._maximum_retries == 0 means unlimited retries
                try:
                    self._curl.perform()
                except pycurl.error, e:
                    retries -= 1
                    if retries == 0:
                        print 'Giving up on ' + job + ': ' + e[1] + "\n", #TODO: this should be counted
                else:
                    retries = 0
                    for filter in self._filter_list:
                        if (not filter.filter(job, self._curl, self._curl_buffer)) != filter.negate: # != is logical xor for booleans
                            self._result_list.put(False)
                            break
                    else:
                        self._result_list.put({'url': job,
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
    def generate_urls(self, url_template, args):

        match = re.search('\[(' + '|'.join(map(re.escape, PAYLOAD_MAPING)) + ')\]', url_template)
        if match:
            p = PAYLOAD_MAPING[match.group(1)](args[match.group(1)])
            for data in p.get_data():
                for x in self.generate_urls(url_template.replace(match.group(0), data, 1), copy.deepcopy(args)): #TODO: deepcopy() just works. Probably something is wrong
                    yield x
        else:
            yield url_template

    def print_result(self, result):
        if result == False:
            self._hidden_results += 1
        else:
            # TODO: lines should be /1000 and add 'k' to save space
            # TODO: size should use kb, mb, etc to save space
            # TODO: what happens with long waits in time? also, the format is wrong
            print str(result['code']).ljust(3) + ' ' + \
                  str(result['lines']).ljust(4) + ' ' + \
                  str(result['size']).ljust(8) + ' ' + \
                  str(result['time']).ljust(8) + ' ' + \
                  result['url'] + "\n",

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
        parser.add_argument('--postfields', type=str, help='encoded post data. Implies --post')
        parser.add_argument('--get', action='store_true', help='uses GET method')
        parser.add_argument('--post', action='store_true', help='uses POST method')
        parser.add_argument('--head', action='store_true', help='uses HEAD method') #TODO: make these mutually exclusive
        parser.add_argument('--header', type=str, default=[], nargs='*', help='extra http headers (--header "foo: bar" "baz: qux")')
        parser.add_argument('--method', type=str, help='custom http method, useful for DELETE or PUT (see CURLOPT_CUSTOMREQUEST)')

        parser.add_argument('--threads', '-t', type=int, default=10, help='number of threads (default: 10)')
        parser.add_argument('--negate', type=str, default=[], nargs='*', help='list of filter to negate (to show only 200 codes: --negate hc --hc 200)')

        parser.add_argument('--retry', type=int, default=3, help='times to retry a request when something goes wrong (0 for unlimited)')
        parser.add_argument('--proxy', type=str, default='', help='[socks4|socks4a|socks5|socks5h|http]://host:port')
        parser.add_argument('--timeout', type=int, default=0, help='timeout in seconds')
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
        if args['postfields']: #This goes after --get, --post and --head
            curl_opts.append((pycurl.POSTFIELDS, args['postfields']))
        if args['method']:
            curl_opts.append((pycurl.CUSTOMREQUEST, args['method']))

        self._hidden_results = 0
        job_pool = Queue.Queue(args['threads'] * 10)
        result_list = Queue.Queue(0)

        # Make a list with the needed filter objects
        # TODO: find a better way
        filter_list = []
        for filter_name in FILTER_MAPING:
            try:
                arg = args[filter_name]
                filter = FILTER_MAPING[filter_name](arg)
                if filter_name in args['negate']:
                        filter.negate = True
                filter_list.append(filter)
            except IndexError:
                pass
        for x in xrange(args['threads']):
           WorkerThread(job_pool, result_list, filter_list, args['retry'], curl_opts).start()

        # Add all the urls to the queue
        for x in self.generate_urls(args['url'], args):
            self.put_job_and_print(result_list, job_pool, x)

        # When the threads get this, they will exit
        # TODO: change this
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

        # Finish showing results
        while result_list.empty() == False:
            self.print_result(result_list.get_nowait())

        print "\nHidden: " + str(self._hidden_results)


Popper()
