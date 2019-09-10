import pytest
import numpy as np

from pewpew.lib.pratt import Parser, ParserException, Reducer, ReducerException
from pewpew.lib.pratt import BinaryFunction, TernaryFunction


def test_parser_basic():
    parser = Parser(["a1", "1a"])

    # Test input
    assert str(parser.parse("1.0e-1")) == "1.0e-1"
    assert str(parser.parse("a1")) == "a1"
    assert str(parser.parse("1a")) == "1a"
    # Test ops
    assert str(parser.parse("1 + 2 - 3")) == "- + 1 2 3"
    assert str(parser.parse("1 * 2 / 3")) == "/ * 1 2 3"
    assert str(parser.parse("1 ^ 2")) == "^ 1 2"
    # Test order of ops
    assert str(parser.parse("1 + 2 * 3")) == "+ 1 * 2 3"
    assert str(parser.parse("(1 + 2) * 3")) == "* + 1 2 3"
    assert str(parser.parse("1 ^ 2 * 3")) == "* ^ 1 2 3"
    assert str(parser.parse("1 ^ (2 * 3)")) == "^ 1 * 2 3"
    # Test right assoc
    assert str(parser.parse("1 ^ 2 ^ 3")) == "^ 1 ^ 2 3"
    # Test unary minus
    assert str(parser.parse("-1")) == "u- 1"
    assert str(parser.parse("-1 - 2")) == "- u- 1 2"
    assert str(parser.parse("1 - - 2")) == "- 1 u- 2"
    assert str(parser.parse("1 * - 2 ^ 3")) == "* 1 u- ^ 2 3"
    # Test comparisions
    assert str(parser.parse("1 > 2")) == "> 1 2"
    assert str(parser.parse("1 < 2")) == "< 1 2"
    assert str(parser.parse("1 >= 2 <= 3")) == "<= >= 1 2 3"
    assert str(parser.parse("1 = 2 != 3")) == "!= = 1 2 3"
    # Test if
    assert str(parser.parse("1 > 2 ? 3 : 4")) == "? > 1 2 3 4"
    assert str(parser.parse("if 1 > 2 then 3 else 4")) == "? > 1 2 3 4"
    assert str(parser.parse("1 > 2 ? 3 < 4 ? 5 : 6 : 7")) == "? > 1 2 ? < 3 4 5 6 7"


def test_parser_additional():
    parser = Parser()
    parser.nulls.update({"bf": BinaryFunction("bf"), "tf": TernaryFunction("tf")})

    assert str(parser.parse("bf(1 + 2, 3 * 4)")) == "bf + 1 2 * 3 4"
    assert str(parser.parse("tf(1 + 2, 3, 4 + 5)")) == "tf + 1 2 3 + 4 5"


def test_parser_raises():
    parser = Parser(["a"])
    parser.nulls.update({"tf": TernaryFunction("tf")})

    # Input
    with pytest.raises(ParserException):
        parser.parse("")
    with pytest.raises(ParserException):
        parser.parse("a2")
    with pytest.raises(ParserException):
        parser.parse("a-a")
    with pytest.raises(ParserException):
        parser.parse("1.0.0")
    # Missing op
    with pytest.raises(ParserException):
        parser.parse("1 1 + 2")
    with pytest.raises(ParserException):
        parser.parse("1 + (2 + 3")
    with pytest.raises(ParserException):
        parser.parse("1 + (2 + 3))")
    with pytest.raises(ParserException):
        parser.parse("1 ? 2 3")
    with pytest.raises(ParserException):
        parser.parse("1 ? 2 else 3")
    # Function format
    with pytest.raises(ParserException):
        parser.parse("tf(1 2, 3)")
    with pytest.raises(ParserException):
        parser.parse("tf(1, 2, 3,)")
    with pytest.raises(ParserException):
        parser.parse("tf 1, 2, 3")


def test_reduce_basic():
    reducer = Reducer({"a": np.arange(4).reshape(2, 2)})

    # Values
    assert reducer.reduce("1") == 1.0
    assert np.all(reducer.reduce("a") == np.array([[0, 1], [2, 3]]))
    # Basic
    assert reducer.reduce("+ + 1 2 3") == 6.0
    assert reducer.reduce("* + 1 2 3") == 9.0
    # Conditions
    assert reducer.reduce("< 1 2")
    assert reducer.reduce("> 2 1")
    assert reducer.reduce("<= >= 1 2 3")
    # If
    assert reducer.reduce("? < 1 2 3 4") == 3.0
    assert reducer.reduce("? > 1 2 3 4") == 4.0
    assert reducer.reduce("? < 1 2 ? > 1 2 3 4 5") == 4.0
    # Variable
    assert np.all(reducer.reduce("* a 2") == np.array([[0, 2], [4, 6]]))
    assert np.all(reducer.reduce("? > a 1 a / a 2") == np.array([[0, 0.5], [2, 3]]))


def test_reduce_additional():
    reducer = Reducer({"a": np.arange(4).reshape(2, 2)})
    reducer.operations.update({"avg": (np.average, 1)})

    assert reducer.reduce("avg + a 10") == 11.5


def test_reduce_raises():
    reducer = Reducer()

    with pytest.raises(ReducerException):
        reducer.reduce("")
    with pytest.raises(ReducerException):
        reducer.reduce("a")
    with pytest.raises(ReducerException):
        reducer.reduce("+ 1 2 3")
    with pytest.raises(ReducerException):
        reducer.reduce("? 2 3")
