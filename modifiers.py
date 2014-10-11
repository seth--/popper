class DummyModifier():
    # This is the easiest way to handle the default case
    @staticmethod
    def set_arguments(parser):
        pass

    def __init__(self):
        pass

    def modify(self, string):
        return string

class IntToAscii():
    @staticmethod
    def set_arguments(parser):
        pass

    def __init__(self): #TODO: add arguments and help
        pass

    def modify(self, string):
        try:
            return chr(int(string))
        except ValueError: # For both non numeric strings and non ascii codes
            return string

MODIFIER_MAPING = {'int2ascii': IntToAscii}