import yaml


import arborial

from typing import List

class F(arborial.Iterator):

    def __init__(self, arg):
        self.arg = arg
    
    def __call__(self, inp: str) -> List[str]:
        return [
            f'F({inp}, {self.arg})[0]',
            f'F({inp}, {self.arg})[1]'
        ]

class U(arborial.Singleton):

    def __init__(self, u_arg):
        self.arg = u_arg
    
    def __call__(self, inp: str) -> str:
        return f'U({inp}, {self.arg})'

class V(arborial.Singleton):

    def __init__(self, arg_of_v):
        self.arg = arg_of_v
    
    def __call__(self, inp: str) -> str:
        return f'V({inp}, {self.arg})'

class ExampleParser(arborial.DictParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register(F, U, V) # register custom operations


import yaml
import json

prog = """
foo=F:
    _arg: "barfoo"
    bar=U:
        _u_arg: "foobar"
    oof=V:
        _arg_of_v: "barfoo"
"""

parser = ExampleParser()
d = yaml.load(prog, Loader=yaml.FullLoader)
ast = parser.parse_dict(d)
result = arborial.evaluate(ast, 'x')
print(json.dumps(result, indent=2))
