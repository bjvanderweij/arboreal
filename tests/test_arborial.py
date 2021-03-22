import arboral
import pytest
import typing as T

class Number(arboral.Singleton):

    def __init__(self, value: int):
        self.value =  value

    def __call__(self, input_: T.Any) -> int:
        return self.value

class AddOne(arboral.Singleton):
    
    def __call__(self, input_: int) -> int:
        return input_ + 1

class IntToStr(arboral.Singleton):

    def __call__(self, input_: int) -> str:
        return str(input_)

class AppendA(arboral.Singleton):

    def __call__(self, input_: str) -> str:
        return input_ + 'a'

class StrToInt(arboral.Singleton):

    def __call__(self, input_: str) -> int:
        return int(input_)

test_parser = arboral.DictParser()
test_parser.register(Number, AddOne, IntToStr, AppendA, StrToInt)

def test_is_terminal():
    node = arboral.TransformationTree(
            operation=StrToInt,
            args={},
            path='root',
            children={})
    node_2 = arboral.TransformationTree(
            operation=StrToInt,
            args={},
            path='root',
            children={'child':node})
    assert node.is_terminal
    assert not node_2.is_terminal

# Test the parse and evaluate functions
def test_parse():
    # type mismatch raises error
    prog = {'x=Number': {'_value': 4, 'a=AddOne': {'b=StrToInt': {}}}}
    with pytest.raises(arboral.ParsingError) as excinfo:
        ast = test_parser.parse_dict(prog)
    assert 'root.x.a' in str(excinfo.value)
    # nonexistent operation raises error
    prog = {'a=DoesNotExist': {}}
    with pytest.raises(arboral.ParsingError) as excinfo:
        ast = test_parser.parse_dict(prog)
    # program parses correctly
    prog = {'x=Number': {'_value': 4, 'a=AddOne': {'aa=IntToStr': {}, 'ab=AddOne': {}}}}
    ast = test_parser.parse_dict(prog)
    assert not ast.is_iterator
    assert not ast.is_context 
    assert set(ast.children.keys()) == {'x'}
    ast = ast.children['x']
    assert set(ast.children.keys()) == {'a'}
    ast = ast.children['a']
    assert set(ast.children.keys()) == {'aa', 'ab'}
    assert ast.children['aa'].is_terminal
    assert ast.children['ab'].is_terminal

def test_evaluate():
    prog = {'x=Number': {'_value': 4, 'a=AddOne': {'aa=IntToStr': {}, 'ab=AddOne': {}}}}
    ast = test_parser.parse_dict(prog)
    assert arboral.evaluate(ast) == {'x': {'a': {'aa':"5", 'ab': 6}}}

# Test register (must check for type hints)
def test_parser_register():
    parser = arboral.DictParser()
    parser.register(AddOne)
    assert 'AddOne' in parser.operations
    assert AddOne in parser.mappings
    assert parser.mappings[AddOne] == (int, int)
    # ensure warning for duplicate operation
    with pytest.warns(UserWarning):
        parser.register(AddOne)

# Test register operation validation (type hints, inheritance, etc.)

def test_parser_types_consistent():
    pass

# Operation with error raises exception with path
# Incompatible types are flagged
# Program executes correctly:
    # Singletons translate to dicts
    # Iterators translate to lists of dicts
