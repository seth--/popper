class InvalidVar:
    pass


#class Payload():
#    CLI_HELP = 'a real payload class shows this at --help'
#
#    # vars is the argv value associated with this class in PAYLOAD_MAPING.
#    # It's a list of string. For example, "--payload foo bar" will be ['foo', 'bar'].
#    # You can use pop(0) to handle having the same payload multiple times or do something completly different
#    def __init__(self, vars=''):
#        pass
#
#    #Should yield replacements for [payload]
#    def get_data(self):
#        pass


class Range():
    CLI_HELP = 'min and max values for [range] separated by a comma (--range 1,10)'

    def __init__(self, vars):
        try:
            vars = vars.pop(0).split(',')
            self._min = int(vars[0])
            self._max = int(vars[1]) + 1
        except Exception:
            raise InvalidVar

    def get_data(self):
        for x in xrange(self._min, self._max): #TODO: add step
            yield str(x)


class File():
    CLI_HELP = 'filename for [file]'

    def __init__(self, vars):
        try:
            self._f = open(vars.pop(0), 'r')
        except Exception:
            raise InvalidVar

    def get_data(self):
        for x in self._f:
            x = x[:-1] #TODO: should use x.rstrip()?
            if x:
                yield x
        self._f.close()


class Repeat():
    CLI_HELP = 'a string to repeat up to X times anteceded by X (--repeat 99 ../)'

    def __init__(self, vars):
        try:
            self._max = int(vars[0])
            self._string = vars.pop(1)
        except Exception:
            raise InvalidVar

    def get_data(self):
        for x in xrange(1, self._max + 1):
            yield self._string * x


# The index will be used as placeholder in the url ([index]) and as an cli argument (--index)
PAYLOAD_MAPING = {'range': Range,
                  'file': File,
                  'repeat': Repeat}
