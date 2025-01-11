"""The main arboral module."""
import inspect 
import sys
import warnings
from typing import Any
from typing import Callable
from typing import Dict
from typing import get_args
from typing import get_origin
from typing import get_type_hints
from typing import Iterable
from typing import List
from typing import Tuple
from typing import Union

class TransformerException(Exception):
    pass


class ParsingError(Exception):
    pass


class Operation():
    
    def __call__(self, input_: Any) -> None:
        ...


class Singleton(Operation):
    pass


class Iterator(Operation):
    pass


class Context(Operation):

    def transform(self, input_: Any) -> "Context":
        return self


class RootOperation(Singleton):

    def __call__(self, input_: Any) -> Any:
        return input_


class TransformationTree():

    def __init__(
            self,
            operation: Callable,
            args: dict,
            path: List[str],
            children: Dict[str, "TransformationTree"],
            context_args: dict = {},
            is_context: bool = False,
            is_iterator: bool = False,
            anonymous_child: bool = False,
            ):
        self.operation = operation
        self.args = args
        self.path = path
        self.children = children
        self.context_args = context_args
        self.is_context = is_context
        self.is_iterator = is_iterator
        self.anonymous_child = anonymous_child

    @property
    def path_str(self):
        return '.'.join(self.path)

    @property
    def name(self):
        return self.path[-1]

    def __repr__(self):
        args_repr = ','.join(f'{k}={v}' for k, v in self.args.items())
        children_repr = ','.join(f'{k}={v}' for k, v in self.children.items())
        return f'{self.operation.__name__}({args_repr}, {children_repr})'

    @property
    def is_terminal(self):
        return len(self.children) == 0


class DictParser():

    def __init__(self):
        self.operations: Dict[str, type] = {}
        self.mappings: Dict[type, Tuple[type, type]] = {}
        self.register(RootOperation)

    def parse_dict(self, d: dict) -> TransformationTree:
        return self._parse(d)

    def _get_context_args(self, tree: dict):
        return {k[2:]: v for k, v in tree.items() if k[:2] == '__'}

    def _get_args(self, tree: dict):
        return {k[1:]: v for k, v in tree.items() if k[0] == '_' and k[1] != '_'}

    def _get_children(self, tree: dict):
        return [(k, v) for k, v in tree.items() if k[0] != '_']

    def _resolve_operation(self, name, path):
        components = name.split('=')
        name = None
        if len(components) == 1:
            operation_name, = components
        elif len(components) == 2:
            name, operation_name = components
        else:
            raise ParsingError(f'[at {path}] illegal operation '
                f'specification: {name}')
        if not operation_name in self.operations:
            raise ParsingError(f'[at {path}] {operation_name} is '
                f'not a registered operation')
        return name, self.operations[operation_name]
        #return self.operations[self.operation_names[operation_name]]

    def _types_consistent(self, output_type, input_type):
        """Check if types are consistent.

        Given an output_type of a parent node and the input_type
        of the current node, check if input_type is consistent
        with output type.
        """
        if get_origin(input_type) is Union:
            return any(self._types_consistent(output_type, t) for t in get_args(input_type))
        elif get_origin(output_type) is Union:
            return all(self._types_consistent(t, input_type) for t in get_args(output_type))
        else:
            return issubclass(output_type, input_type)

    def _parse(
            self,
            tree: dict,
            operation: str = RootOperation,
            tree_cls=TransformationTree,
            path: List[str] = ['root']
            ) -> TransformationTree:
        """Parse a dictionary.

        Return a nested structure of TransformationTree objects.
        """
        child_trees = {}
        codomain = self.mappings[operation][1]
        path_str = ".".join(path)
        for name, subtree in self._get_children(tree):
            name, soperation = self._resolve_operation(name, path_str)
            child_domain = self.mappings[soperation][0]
            if child_domain != Any:
                def to_str(t):
                    if isinstance(t, type):
                        return t.__name__
                    else:
                        return repr(t)
                if codomain == Any:
                    if operation != RootOperation:
                        warnings.warn(f'cannot do type checking for {path_str} which returns "Any"', stacklevel=1)
                elif not self._types_consistent(codomain, child_domain):
                    raise ParsingError(
                            f'value of {path_str} is of type '
                            f'{to_str(codomain)}, but {name} wants input of type '
                            f'{to_str(child_domain)}')
            if name is None:
                # There may be at most one anonymous child
                if len(child_trees) != 0:
                    raise ParsingError(
                            f'{to_str(soperation)} at {path_str} is anonymous '
                            f'and therefore must be the only of its parent, '
                            f'but it is not')
            child_trees[name] = self._parse(
                    subtree,
                    operation=soperation,
                    tree_cls=TransformationTree,
                    path=path + [(to_str(soperation) if name is None else name)],
                )
        return tree_cls(
                operation = operation,
                args = self._get_args(tree),
                context_args = self._get_context_args(tree),
                children = child_trees,
                path = path,
                is_context = issubclass(operation, Context),
                is_iterator = not issubclass(operation, Singleton),
                anonymous_child = len(child_trees) == 1 and child_trees.get(None) is not None
            )

    def _validate(self, operation: type) -> Tuple[type, type]:
        if issubclass(operation, Context):
            assert '__enter__' in dir(operation)
            assert '__exit__' in dir(operation)
        else:
            assert '__call__' in dir(operation)
        assert inspect.isfunction(operation.__call__) 
        type_hints = get_type_hints(operation.__call__)
        assert len(type_hints) == 2 # must take one argument
        assert 'return' in type_hints # must have return type
        codomain = type_hints.pop('return')
        domain = (
                Any if issubclass(operation, Context) else
                next(iter(type_hints.values()))
            )
        if issubclass(operation, Iterator):
            # codomain must be iterable and must specify contents
            assert get_origin(codomain) is not None
            assert issubclass(get_origin(codomain), Iterable)
            assert len(codomain.__args__) == 1
            codomain = codomain.__args__[0]
        return domain, codomain

    def register(self, *operations: List[type]) -> None:
        """Register new operations with the parser"""
        for operation in operations:
            if operation.__name__ in self.operations:
                warnings.warn(f'skipping duplicate operation {operation.__name__}', stacklevel=2)
                continue
            if not issubclass(operation, Operation):
                raise Exception(f'cannot add {operation.__name__} because it '
                        'does no inherit from arboral.Operation')
            self.operations[operation.__name__] = operation
            domain, codomain = self._validate(operation)
            self.mappings[operation] = (domain, codomain)

CONTEXT = {}


def set_context(tree: TransformationTree, obj: Any):
    CONTEXT[tree.path_str] = obj


def unset_context(tree: TransformationTree):
    del CONTEXT[tree.path_str]


def get_context(path):
    return CONTEXT[path]


def evaluate(tree: TransformationTree, input_: Any = None, stack=['root']):
    context = {name: get_context(path)
               for name, path in tree.context_args.items()}
    operation = tree.operation(**tree.args, **context)
    try:
        result = operation(input_)
    except Exception as e:
        raise type(e)(f'[at {".".join(stack)}] {str(e)}').with_traceback(
                sys.exc_info()[2])
        # raise TransformerException(
        #     f'An exception occurred at {".".join(stack)}')

    def trav():
        if tree.is_terminal:
            return result
        if tree.is_iterator:
            return [_traverse(tree, r, stack) for r in result]
        return _traverse(tree, result, stack)
    set_context(tree, result)
    if tree.is_context:
        with operation:
            r = trav()
    else:
        r = trav()
    unset_context(tree)
    return r


def _traverse(tree: TransformationTree, result: Any, stack):
    if tree.anonymous_child:
        _, subtree = next(iter(tree.children.items()))
        return evaluate(subtree, result, stack + [subtree.operation.__name__])
    else:
        return {
                name: evaluate(subtree, result, stack + [name]) for name, subtree in tree.children.items()
            }
