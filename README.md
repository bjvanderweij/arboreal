[![Build Status](https://travis-ci.org/bjvanderweij/arboral.svg?branch=master)](https://travis-ci.org/bjvanderweij/arboral)

# Arboral - domain specific languages in Python

Arboral is a minimalist library that defines a customizable parser and an interpreter of simple tree-structured instructions. 
It allows you to define domain-specific languages by providing the parser with as a set of operations.

The tree-structured instructions can be regarded a kind of "computational template" that produces a nested mapping obtained by filling the nodes of the tree.

*Beware: this is work in progress. The documentation is incomplete and not all functionality has been tested.*

# What does it do?

The interpreter takes as its input a tree-like data structure (an expression in a domain-specific language).
This input can be regarded a kind of "computational template" for a datastructure that specifies how to populate itself.

The use-case that inspired me to make this is a YAML language for defining scrapers.
The language simultaneously defines how to scrape a website and the hierarchical structure of the resulting data 
For example, the YAML expression below defines a scraper for a Dutch news site that extracts headlines, links, and descriptions:

```yaml
nos=Fetch:
    _url: "https://www.nos.nl"
    html=Parse:
        news_items=SelectElements:
            _selector: "li.cb-mab"
            title=SelectElement:
                _selector: "h2"
                _value: "text"
            link=SelectElement:
                _selector: "a"
                _value: ".href"
            description=SelectElement:
                _selector: "p"
                _value: "text"
```

The scraping language used here uses four operations of a custom scraping language: `Fetch`, `Parse`, `SelectElement`, and `SelectElements`.
Evaluating it results in something like this:

```json
{
  "nos": {
    "html": {
      "news_items": [
        {
          "title": "Oranjes herdenken Philip 'met groot respect' ...",
          "link": "/liveblog/2376017-oranjes-herdenken-philip-met...",
          "description": "De Britse prins Philip is op 99-jarige ..."
        },
        {
          "title": "Prins Philip: steun en toeverlaat van de Brit...",
          "link": "/artikel/2376012-prins-philip-steun-en-toeverl...",
          "description": "De echtgenoot van koningin Elizabeth wa..."
        },
        ...
      ]
    }
  }
}
```

As you can see, the arboral language makes it very easy to define scrapers that transform an HTML document into a python dictionary.  
A limitation inherent in this design is that the the produced data structure is constrained by the hierarchical structure of an HTML document.

# How does it work?

A semantics is defined by a set of operations and a program is defined as a tree of named nodes.
The result of an operations is either a singleton or an iterable.
The two cases are defined below.

## Singleton operations

For example, the tree below specifies a program in a language with three operations: `F`, `U`, and `V`.

```yaml
foo=F:
    bar=U: {}
    oof=V: {}
```

here, `foo`, `bar`, and `oof` are node names, and `F`, `U`, and `V` are operations provided to the parser.
Note that some custom syntax is embedded in the YAML syntax here in order to be able to name nodes.

Shown as a Python dictionary below is the result of evaluating the above template on the input `x`:

```python
{
  "foo": {
    "bar": U(F(x)),
    "oof": V(F(x))
  }
}
```

Each node (associated with a *name* and an *operation*) produces a *value* which is the result of applying its operation to its *input*.
If a node is a leaf node, its *result* is its value.
If a node has children, its result is a mapping from child names to child results.

In the example above, `foo` has child nodes produces a mapping from child-node names to the child-node results.
The nodes `bar` and `oof` are leafs, so their result is their value.
The value of a leaf node is the result of applying its operation to its input.
In the case of `bar`, the input is the value of `foo`, which is `f(x)` (since `x` was the top-level input).

It is also possible to provide custom arguments to the operations in a YAML program.
For this purpose, we'll introduce embed another bit of custom syntax into YAML: keys whose names starts with an underscore are interpreted as arguments.

```yaml
foo=F:
    _arg: "barfoo"
    bar=U: {}
        _another_arg: "foobar"
    oof=V: {}
        _arg_of_oof: "barfoo"
```

The result, in Python code, is:

```python
{
  "foo": {
    "bar": u(f(x, arg="barfoo"), another_arg="foobar"),
    "oof": v(f(x, arg="barfoo"), arg_op_oof="barfoo")
  }
}
```

## Iterables

An iterable operation produces more than one value.
Its result is a list consisting of mappings from child nodes to their results obtained by applying the evaluating the child nodes for each result value. 

To make that more concrete, imagine, for example, that `F(x)` produces two values.
The result of the example program

```yaml
foo=F:
    _arg: "barfoo"
    bar=U:
        _u_arg: "foobar"
    oof=V:
        _arg_of_v: "barfoo"
```

given that F is now an Iterator, will evaluate to the following Python code 

```python
{
  "foo": [
      {
        "bar": U(F(x, arg="barfoo")[0], u_arg="foobar"),
        "oof": V(F(x, arg="barfoo")[0], arg_of_v="barfoo")
      },
      {
        "bar": U(F(x, arg="barfoo")[1], u_arg="foobar"),
        "oof": V(F(x, arg="barfoo")[1], arg_of_v="barfoo")
      }
}
```

## Accessing results of ancestors

Sometimes you need to access the result of an ancestor that isn't an immediate parent.
This can be done using arguments that start with `__` (a double underscore).
The value of these arguments is a tree path constructed by the names of nodes, separated by dots.

```yaml
foo=F:
    _arg: "barfoo"
    bar=U:
        _u_arg: "foobar"
        barbar:
            __foo: "foo"
    oof=V:
        _arg_of_v: "barfoo"
```

Here, the value given to the argument `__foo` is the value of the node `foo`, as indicated by the path "foo".
If we had wanted to access the value of `bar`, we'd have used "foo.bar" as a path.
We can only access the values of ancestors of a node. From within `barbar`, the path "foo.oof" is inaccessible.

## Contexts

A context is a special operation that is implemented by a Python context manager.
Its result is an instance of the context manager itself.

An example of using contexts is when defining scrapers of websites that require login.

For more details, see [defining context operations](#defining-context-operations).

## Defining operations

As you may have guessed by now, operations are simply Python functions.
However, in order to make operations extensible and to easily identify their type (singleton or iterable), they are defined as Python classes.

For example, we could define the operation `F` as follows:

```python
class F(arboral.Singleton):

    def __init__(self, arg, optional_arg=None):
        self.arg = arg
        self.optional_arg = optional_arg
    
    def __call__(self, inp: str) -> str:
        return f'result of f applied to {inp} with argument {self.arg} and {self.optional_arg}'
```

Note that *operations have typed arguments and typed results*.
The arboral parser validates whether the types of the operations used in a program match.

The arguments to init correspond to arguments that can be passed in a YAML program using keys preceded by `_` (a single underscore).

By default, operations are assumed to be iterators.
To define a singleton operation, the operation class should inherit from `arboral.Singleton`.

The code below shows a (self-contained) possible definition of the language used in the examples above:

```python
import arboral

from typing import List

class F(arboral.Iterator):

    def __init__(self, arg):
        self.arg = arg
    
    def __call__(self, inp: str) -> List[str]:
        return [
            f'first result of F applied to {inp} with argument {self.arg}',
            f'second result of F applied to {inp} with argument {self.arg}'
        ]

class U(arboral.Singleton):

    def __init__(self, u_arg):
        self.arg = u_arg
    
    def __call__(self, inp: str) -> str:
        return f'result of U applied to {inp} with argument {self.arg}'

class V(arboral.Singleton):

    def __init__(self, arg_of_v):
        self.arg = arg_of_v
    
    def __call__(self, inp: str) -> str:
        return f'result of V applied to {inp} with argument {self.arg}'

class ExampleParser(arboral.DictParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register(F, U, V) # register custom operations

```

The following code could be used to evaluate the examples given earlier:

```python
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
result = arboral.evaluate(ast, 'x')
print(json.dumps(result, indent=2))
```

Running it will print

```
{
  "foo": [
    {
      "bar": "U(F(x, barfoo)[0], foobar)",
      "oof": "V(F(x, barfoo)[0], barfoo)"
    },
    {
      "bar": "U(F(x, barfoo)[1], foobar)",
      "oof": "V(F(x, barfoo)[1], barfoo)"
    }
  ]
}
```

### Defining context operations

To define a context operation, simply define a context manager and make sure it inherits from `arboral.Context`.

The following excerpt illustrates the general way of defining a Context operation:

```python
class ExampleContext(arboral.Context):

    def __enter__(self):
        # Setup context
        pass

    def __exit__(self):
        # Tear down context
        pass
```

Because arboral uses Python classes to define operations, it is easy to mix in functionality from other classes.
For example, creating a Context operation that creates a HTTP session context is as simple as:

```python
import requests

class Session(requests.Session, arboral.Context):
    pass
```

## Error handling and type checking

TODO

# Use case: a language for defining scrapers

Arboral can be used to create a domain-specific language for defining scrapers.
The file `examples/scraping.py` shows how such a language could look.

To try this out, install arboral, clone this repository, and navigate to the `examples` directory.

The script `examples/present.py` takes as its argument file containing a Jinja2 template and (Jekyll-style) YAML frontmatter.
It parses YAML frontmatter using the domain-specific language defined in the file [examples/scraping.py](examples/scraping.py), evaluates the resulting scraper, and applies the resulting dictionary to the template.

For example, the file below defines scrapers for two popular Dutch news websites and renders the results as a markdown file.

```markdown
---
nos=PageFetcher:
    _url: "https://www.nos.nl"
    html=HtmlParser:
        news_items=ElementsSelector:
            _selector: "li.cb-mab"
            title=ElementSelector:
                _selector: "h2"
                _value: "text"
            link=ElementSelector:
                _selector: "a"
                _value: ".href"
            description=ElementSelector:
                _selector: "p"
                _value: "text"
nu=PageFetcher:
    _url: "https://www.nu.nl"
    html=HtmlParser:
        article_lists=ElementsSelector:
            _selector: "div.articlelist.block"
            type=ElementProperty:
                _value: ".data-section"
            articles=ElementsSelector:
                _selector: "li.list__item--text"
                title=ElementSelector:
                    _selector: "span.item-title__title"
                    _value: "text"
                link=ElementSelector:
                    _selector: "a"
                    _value: ".href"
---
## NOS.nl headlines

{% for item in nos.html.news_items %}* [{{ item.title }}]({{item.link}})
{% endfor %}

## NU.nl headlines

{% for article_list in nu.html.article_lists %}### {{article_list.type}}

{% for article in article_list.articles %}* [{{ article.title }}]({{article.link}})
{% endfor %}
{% endfor %}
```



To test this, we first invoke [examples/present.py](examples/present.py) on the above file (assuming it's called `headlines.scraper`)

```bash
$ python present.py headlines.scraper > headlines.md
$ pandoc headlines.md -o headlines.pdf # optionally render markdown to PDF
```

We can also render the results to a CSV file.
To do that, replace the template part of the file above with:

```
title,link,description,category
{% for item in nos.html.news_items -%}
{{ item.title }},{{item.link}},{{item.description}},
{%- endfor %}
{% for article_list in nu.html.article_lists -%}
{% for article in article_list.articles -%}
{{ article.title }},{{article.link}},,{{article_list.type}}
{%- endfor %}
{%- endfor %}
```

## Features

* *Embedded* in Python:
    * Operations are extensible Python classes
    * Typing is builts on standard Python type hinting (and plays nicely with type checkers)
* No dependencies:
    * Arboral uses only the standard library

## To do

* add types and type casting for operation arguments
