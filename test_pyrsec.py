from pyrsec import (
    State,
    Parser,
    Lazy,
    EOF,
    RegExp,
    String,
    Return,
    Error,
    COk,
    EOk,
    CErr,
    EErr,
)
import json


def test_return():
    state = State("")
    p = Return("hi")
    result, new_state = p(state)
    assert result == EOk("hi") and new_state == state


def test_error():
    state = State("")
    p = Error()
    result, new_state = p(state)
    assert result == EErr() and new_state == state


def test_string():
    state = State("abc")
    p = String("abc")
    result, new_state = p(state)
    assert result == COk("abc") and new_state == state.advance(3)
    p = String("abd")
    result, new_state = p(state)
    assert result == EErr() and new_state == state


def test_then():
    state = State("abcdef")
    p = String("abc")
    q = String("def")
    result, new_state = p.then(q)(state)
    assert result == COk("def") and new_state == state.advance(6)

    state = State("abc")
    p = String("abc")
    q = Return(None)
    result, new_state = p.then(q)(state)
    assert result == COk(None) and new_state == state.advance(3)

    state = State("abc")
    p = Return(None)
    q = String("abc")
    result, new_state = p.then(q)(state)
    assert result == COk("abc") and new_state == state.advance(3)

    state = State("")
    p = Return(None)
    q = Return(None)
    result, new_state = p.then(q)(state)
    assert result == EOk(None) and new_state == state


def test_skip():
    state = State("abcdef")
    p = String("abc")
    q = String("def")
    result, new_state = p.skip(q)(state)
    assert result == COk("abc") and new_state == state.advance(6)

    state = State("abc")
    p = String("abc")
    q = Return(None)
    result, new_state = p.skip(q)(state)
    assert result == COk("abc") and new_state == state.advance(3)

    state = State("abc")
    p = Return(None)
    q = String("abc")
    result, new_state = p.skip(q)(state)
    assert result == COk(None) and new_state == state.advance(3)

    state = State("")
    p = Return(None)
    q = Return(None)
    result, new_state = p.skip(q)(state)
    assert result == EOk(None) and new_state == state


def test_regexp():
    state = State("ababac")
    p = RegExp("(?:ab)+")
    result, new_state = p(state)
    assert result == COk("abab") and new_state == state.advance(4)

    state = State("babac")
    p = RegExp("(?:ab)+")
    result, new_state = p(state)
    assert result == EErr() and new_state == state

    state = State("babac")
    p = RegExp("(?:ab)*")
    result, new_state = p(state)
    assert result == EOk("") and new_state == state


def test_balanced_braks():
    def balanced_braks(n):
        if n == 1:
            return tuple([[]])
        X = []
        for y in balanced_braks(n - 1):
            X.append([y])
        for k in range(1, n):
            for y in balanced_braks(k):
                for z in balanced_braks(n - k):
                    X.append([y, z])
        return X

    def stringify(x):
        if len(x) == 0:
            return "[]"
        else:
            return "".join([stringify(y) for y in x])

    left = String("[")
    right = String("]")
    balanced = (
        left.then(
            right.map(lambda _x: []).or_(
                Lazy(lambda: balanced).map(lambda x: [x]).skip(right)
            )
        )
        .many()
        .map(lambda xs: xs[0] if len(xs) == 1 else xs)
    )

    for k in range(1, 7):
        for x in balanced_braks(k):
            y = stringify(x)
            state = State(y)
            result, _ = balanced.skip(EOF())(state)
            z = stringify(result.value)
            assert y == z
