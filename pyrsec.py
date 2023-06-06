from __future__ import annotations
from dataclasses import dataclass
from typing import TypeVar, Generic, Tuple, Literal
import re

T = TypeVar("T")


@dataclass
class COk(Generic[T]):
    value: T


@dataclass
class EOk(Generic[T]):
    value: T


@dataclass
class EErr:
    pass


@dataclass
class CErr:
    pass


@dataclass
class State:
    source: str
    i: int = 0
    expected: Tuple[str] = tuple()

    def advance(self, j):
        return State(self.source, i=self.i + j)

    def append_expected(self, s):
        return State(self.source, self.i, (*self.expected, s))

    def reset_expected(self):
        return State(self.source, self.i)


class Parser:
    def __init__(self, p):
        self.p = p

    def __call__(self, state):
        match state:
            case str(source):
                state = State(source)
            case State(_):
                pass
            case _:
                raise TypeError("Argument must be a string or a State instance.")
        return self.p(state)

    @property
    def desc(self):
        return getattr(self, "_desc", None)

    @staticmethod
    def alt(*args):
        def q(state):
            for p in args:
                result, state = p(state)
                match result:
                    case COk(_) | EOk(_):
                        return result, state
                    case CErr():
                        return CErr(), state
                    case _:
                        continue
            return EErr(), state

        return Parser(q)

    @staticmethod
    def seq(*args):
        def q(state):
            consumed = False
            values = []
            for p in args:
                result, state = p(state)
                match result:
                    case COk(value):
                        consumed = True
                        values.append(value)
                    case EOk(value):
                        values.append(value)
                    case CErr():
                        return CErr(), state
                    case EErr():
                        if consumed:
                            return CErr(), state
                        else:
                            return EErr(), state
            if consumed:
                return COk(values), state
            else:
                return EOk(values), state

        return Parser(q)

    def set_desc(self, _desc):
        self._desc = _desc
        return self

    def chain(self, f):
        def q(state):
            result, state = self(state)
            match result:
                case COk(value):
                    result, state = f(value)(state)
                    match result:
                        case COk(value) | EOk(value):
                            return COk(value), state
                        case EErr() | CErr():
                            return CErr(), state
                case EOk(value):
                    result, state = f(value)(state)
                    match result:
                        case COk(value):
                            return COk(value), state
                        case EOk(value):
                            return EOk(value), state
                        case _:
                            return result, state
                case _:
                    return result, state

        return Parser(q)

    def map(self, f):
        return self.chain(lambda x: Return(f(x)))

    def then(self, q):
        return self.chain(lambda _: q)

    def skip(self, q):
        return self.chain(lambda x: q.map(lambda _: x))

    def t(self):
        return self.skip(opt_whitespace)

    def lookahead(self):
        def q(state):
            result, _ = self(state)
            match result:
                case COk(value) | EOk(value):
                    return EOk(value), state
                case _:
                    return EErr()

        return Parser(q)

    def or_(self, q):
        def r(state):
            result, state = self(state)
            match result:
                case COk(_) | EOk(_) | CErr():
                    return result, state
                case EErr():
                    return q(state)

        return Parser(r)

    def pair(self, q, f=None):
        return self.chain(lambda x: q.map(lambda y: (x, y) if f is None else f(x, y)))

    def many(self):
        def r(state):
            consumed = False
            values = []
            while True:
                result, state = self(state)
                match result:
                    case COk(value):
                        consumed = True
                        values.append(value)
                    case EOk(value):
                        raise Exception("Parser must consume.")
                    case EErr():
                        break
                    case CErr():
                        return CErr(), state
            if consumed:
                return COk(values), state
            else:
                values == []
                return EOk(values), state

        return Parser(r)

    def many1(self):
        return self.chain(lambda x: self.many().map(lambda xs: [x, *xs]))

    def sep_by(self, q):
        return self.chain(lambda x: q.then(self).many().map(lambda xs: [x, *xs])).or_(
            Return([])
        )


class Return(Parser):
    def __init__(self, value):
        self.value = value

    def __call__(self, state):
        match state:
            case str(source):
                state = State(source)
            case State(_):
                pass
            case _:
                raise TypeError("Argument must be a string or a State instance.")
        return EOk(self.value), state


class Error(Parser):
    def __init__(self, desc=None):
        self._desc = desc

    def __call__(self, state):
        match state:
            case str(source):
                state = State(source)
            case State(_):
                pass
            case _:
                raise TypeError("Argument must be a string or a State instance.")
        return EErr(), state


class EOF(Parser):
    def __init__(self, desc="EOF"):
        self._desc = desc

    def __call__(self, state):
        match state:
            case str(source):
                state = State(source)
            case State(_):
                pass
            case _:
                raise TypeError("Argument must be a string or a State instance.")
        if state.i == len(state.source):
            return EOk(None), state
        else:
            return EErr(), state


class Lazy(Parser):
    def __init__(self, thunk):
        self.thunk = thunk

    def __call__(self, state):
        return self.thunk()(state)


class String(Parser):
    def __init__(self, s):
        if s == "":
            raise ValueError("Argument cannot be the empty string.")
        self.s = s

    def __call__(self, state):
        match state:
            case str(source):
                state = State(source)
            case State(_):
                pass
            case _:
                raise TypeError("Argument must be a string or a State instance.")
        j = len(self.s)
        if state.source[state.i : state.i + j] == self.s:
            return COk(self.s), state.advance(j)
        else:
            return EErr(), state


class RegExp(Parser):
    def __init__(self, pattern):
        self.pattern = re.compile(pattern)
        self._desc = pattern

    def __call__(self, state):
        match state:
            case str(source):
                state = State(source)
            case State(_):
                pass
            case _:
                raise TypeError("Argument must be a string or a State instance.")
        match = self.pattern.match(state.source, state.i)
        if match:
            value = match.group(0)
            if value != "":
                return COk(value), state.advance(len(value))
            else:
                return EOk(""), state
        else:
            return EErr(), state


opt_whitespace = RegExp("\\s*")
