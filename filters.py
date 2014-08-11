import pycurl
import re


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
        parser.add_argument('--hc', type=int, default=None, nargs='*', help='HTTP result codes to hide (--hc 404 403)')

    def __init__(self, vars):
        BaseFilter.__init__(self)
        try:
            self._hide_codes = vars
        except:
            #When vars is invalid raise InvalidVar
            raise InvalidVar

    #Returns true if the url should be shown
    #curl = curl object after calling perform()
    #file = the response body including headers
    def filter(self, curl, file):
        return not curl.getinfo(pycurl.RESPONSE_CODE) in self._hide_codes


class Time(BaseFilter):
    @staticmethod
    def set_arguments(parser):
        parser.add_argument('--ht', type=int, default=None, help='hide requests which took less than X seconds (--ht 2)')

    def __init__(self, vars):
        BaseFilter.__init__(self)
        try:
            self._seconds = vars
        except:
            raise InvalidVar

    def filter(self, curl, file):
        return (curl.getinfo(pycurl.TOTAL_TIME) - curl.getinfo(pycurl.PRETRANSFER_TIME)) > self._seconds


class Lines(BaseFilter):
    @staticmethod
    def set_arguments(parser):
        parser.add_argument('--hl', type=int, default=None, nargs='*', help='hide results with X lines (--hl 5 6 78)')

    def __init__(self, vars):
        BaseFilter.__init__(self)
        try:
            self._lines = vars
        except:
            raise InvalidVar

    def filter(self, curl, file):
        return not file.count("\n") in self._lines


class LinesOrMore(BaseFilter):
    @staticmethod
    def set_arguments(parser):
        parser.add_argument('--hl+', type=int, default=None, help='hide results with more than X lines (--hl+ 20)')

    def __init__(self, vars):
        BaseFilter.__init__(self)
        try:
            self._lines = vars
        except:
            raise InvalidVar

    def filter(self, curl, file):
        return not (file.count("\n") > self._lines)


class Grep(BaseFilter):
    @staticmethod
    def set_arguments(parser):
        parser.add_argument('--grep', type=str, default=None, nargs='*', help='Show results matching a regular expression')

    def __init__(self, vars):
        BaseFilter.__init__(self)
        try:
            self._regex = vars
        except:
            raise InvalidVar

    def filter(self, curl, file):
        for regex in self._regex:
            if re.search(regex, file):
                return True
        return False


FILTER_MAPING = {'hc': Code,
                 'ht': Time,
                 'hl': Lines,
                 'hl+': LinesOrMore,
                 'grep': Grep}

