import pycurl

class InvalidVar:
    pass


class BaseFilter():
    def __init__(self):
        self.negate = False


class Code(BaseFilter):
    #This should add the needed arguments for this filter
    #parser=an argparse.ArgumentParser object
    @staticmethod
    def set_arguments(parser):
        parser.add_argument('--hc', type=int, default=[], nargs='*', help='HTTP result codes to hide (--hc 404 403)')

    def __init__(self, vars):
        BaseFilter.__init__(self)
        try:
            self._hide_codes = vars
        except:
            #When vars is invalid raise InvalidVar
            raise InvalidVar

    #Returns true if the url should be shown
    #url = 'http://foo/bar'
    #curl = curl object after calling perform()
    #file = the response body including headers
    def filter(self, url, curl, file):
        return not curl.getinfo(pycurl.RESPONSE_CODE) in self._hide_codes


class Time(BaseFilter):
    @staticmethod
    def set_arguments(parser):
        parser.add_argument('--ht', type=int, help='Hide requests which took less than X seconds (--ht X)')

    def __init__(self, vars):
        BaseFilter.__init__(self)
        try:
            self._seconds = vars
        except:
            raise InvalidVar

    def filter(self, url, curl, file):
        return (curl.getinfo(pycurl.TOTAL_TIME) - curl.getinfo(pycurl.PRETRANSFER_TIME)) > self._seconds


class Lines(BaseFilter):
    @staticmethod
    def set_arguments(parser):
        parser.add_argument('--hl', type=int, default=[], nargs='*', help='Hide results with X lines (--hl X)') #TODO add support for "X or longer"

    def __init__(self, vars):
        BaseFilter.__init__(self)
        try:
            self._lines = vars
        except:
            raise InvalidVar

    def filter(self, url, curl, file):
        return not file.count("\n") in self._lines


FILTER_MAPING = {'hc': Code,
                 'ht': Time,
                 'hl': Lines}

