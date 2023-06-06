from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

from pyrsec import (
    Lazy,
    Parser,
    RegExp,
    String,
)
import pytest
import ast


@dataclass
class UnOp:
    op: Literal["+", "-"]
    operand: int | UnOp | BinOp

    def __str__(self) -> str:
        operand = str(self.operand).strip()
        return f"({self.op}{operand})"


@dataclass
class BinOp:
    op: Literal["+", "-", "*", "/", "**"]
    left: int | UnOp | BinOp
    right: int | UnOp | BinOp

    def __str__(self) -> str:
        left = str(self.left).strip()
        right = str(self.right).strip()
        return f"({left} {self.op} {right})"


opt_whitespace = RegExp("\\s*")
identifier = RegExp(r"[a-zA-Z]\w*").t().map(ast.Name)
number = RegExp(r"[1-9]\d*\s*|0+").t().map(lambda x: ast.Constant(int(x)))
primitive = number.or_(identifier)
expop = String("**").t()
lparen = String("(").t()
rparen = String(")").t()
lbrak = String("[").t()
rbrak = String("]").t()
addop = RegExp("[-+]").t()
mulop = RegExp("[*/]").t()
unop = RegExp("[+-]").t()
pow = String("**").t()
dot = String(".").t()
comma = String(",").t()


def binop_node(op: Literal["+", "-", "*", "/", "**"]):
    match op:
        case "+":
            return ast.Add()
        case "-":
            return ast.Sub()
        case "*":
            return ast.Mult()
        case "/":
            return ast.Div()
        case "**":
            return ast.Pow()


def unop_node(op: Literal["+", "-"]):
    match op:
        case "+":
            return ast.UAdd()
        case "-":
            return ast.USub()


def f(x, ys):
    for y in ys:
        x = ast.BinOp(left=x, op=binop_node(y[0]), right=y[1])
    return x


def g(x, xs):
    x, *xs = [x, *xs][::-1]
    for y in xs:
        x = ast.BinOp(left=y, op=ast.Pow(), right=x)
    return x


def h(op, operand):
    return ast.UnaryOp(unop_node(op), operand)


def attribute_map(value, attrs):
    for attr in attrs:
        value = ast.Attribute(value, attr.id)
    return value


def subscript_map(value, slices):
    for slice in slices:
        value = ast.Subscript(value, slice.body)
    return value


def commma_map(xs):
    if len(xs) == 1:
        ...


@dataclass
class ArgWrapper:
    expr: ast.Expression

    def __repr__(self):
        return f"ArgWrapper({repr(ast.dump(self.expr))})"


def access_map(value, props):
    for prop in props:
        match prop:
            case ast.Name(id):
                value = ast.Attribute(value, id)
            case ArgWrapper(expr):
                if isinstance(expr.body, ast.Tuple):
                    value = ast.Call(func=value, args=expr.body.elts)
                else:
                    value = ast.Call(func=value, args=[expr.body])
                # args = (
                #     expr.body.elts if isinstance(expr.body, ast.Tuple) else [expr.body]
                # )
                # return ast.Call(func=value, args=args)
            case ast.Expression(body):
                value = ast.Subscript(value, body)
            case _:
                raise Exception()
    return value


parenexpr = lparen.then(
    rparen.map(lambda _x: ast.Tuple([])).or_(
        Lazy(lambda: expr).map(lambda x: x.body).skip(rparen)
    )
)  # could be empty tuple
primary = Parser.alt(primitive, parenexpr)
property = Parser.alt(
    dot.then(identifier),
    lbrak.then(Lazy(lambda: expr)).skip(rbrak),
    lparen.then(Lazy(lambda: expr.map(ArgWrapper))).skip(rparen),
)
access = primary.pair(property.many(), access_map)
expexpr = access.pair(expop.then(Lazy(lambda: unary)).many(), g)
unary = unop.pair(Lazy(lambda: unary), h).or_(expexpr)
mulexpr = unary.pair(mulop.pair(unary).many(), f)
sumexpr = mulexpr.pair(addop.pair(mulexpr).many(), f)
tupleexpr = sumexpr.sep_by(comma).map(
    lambda elts: elts[0] if len(elts) == 1 else ast.Tuple(elts)
)
expr = tupleexpr.map(lambda body: ast.Expression(body))

source = "f(x, y+z) + 1"
print(ast.dump(expr(source)[0].value, indent=4))
# print(ast.dump(expr(source)[0].value.body, indent=4))


def are_equal(x0, x1):
    match (x0, x1):
        case (ast.Expression(body0), ast.Expression(body1)):
            return are_equal(body0, body1)
        case (ast.UnaryOp(op0, operand0), ast.UnaryOp(op1, operand1)):
            return type(op0) == type(op1) and are_equal(operand0, operand1)
        case (ast.BinOp(left0, op0, right0), ast.BinOp(left1, op1, right1)):
            return (
                are_equal(left0, left1)
                and type(op0) == type(op1)
                and are_equal(right0, right1)
            )
        case (ast.Attribute(value0, attr0), ast.Attribute(value1, attr1)):
            return are_equal(value0, value1) and attr0 == attr1
        case (ast.Subscript(value0, slice0), ast.Subscript(value1, slice1)):
            return are_equal(value0, value1) and are_equal(slice0, slice1)
        case (ast.Constant(value0), ast.Constant(value1)):
            return value0 == value1
        case (ast.Name(id0), ast.Name(id1)):
            return id0 == id1
        case (ast.Tuple(elts0), ast.Tuple(elts1)):
            return all([are_equal(x, y) for x, y in zip(elts0, elts1)])
        case (ast.Call(func0, args0), ast.Call(func1, args1)):
            return are_equal(func0, func1) and all(
                are_equal(arg0, arg1) for arg0, arg1 in zip(args0, args1)
            )
        case _:
            return False


source = [
    "1 * 7 + 2 + 5 - 5 - 5 / 10 * 3 - 7 / 8 / 5 + 4 * 1 - 9 + 6 + 9",
    "1 + 2 / 1 * 1 / 5 / 10 + 4 * 1 * 5 - 9 + 10 + 10 + 7 - 5 - 7 * 1",
    "5 + 9 * 7 + 10 * 2 + 9 - 9 + 10 * 2 / 10 - 6 - 6 / 9 / 5 - 8 + 4",
    "8 / 3 / 10 * 10 * 9 / 2 + 4 + 3 - 10 * 3 + 1 / 10 - 7 * 6 + 10 + 6",
    "9 + 10 + 1 * 2 - 1 / 8 / 6 - 7 / 7 + 1 - 6 * 6 * 2 - 4 / 9 - 5",
    "1 * 7 + 2 + 5 - 5 - 5 / 10 * 3 - 7 / 8 / 5 + 4 * 1 - 9 + 6 + 9",
    "1 + 2 / 1 * 1 / 5 / 10 + 4 * 1 * 5 - 9 + 10 + 10 + 7 - 5 - 7 * 1",
    "5 + 9 * 7 + 10 * 2 + 9 - 9 + 10 * 2 / 10 - 6 - 6 / 9 / 5 - 8 + 4",
    "8 / 3 / 10 * 10 * 9 / 2 + 4 + 3 - 10 * 3 + 1 / 10 - 7 * 6 + 10 + 6",
    "9 + 10 + 1 * 2 - 1 / 8 / 6 - 7 / 7 + 1 - 6 * 6 * 2 - 4 / 9 - 5",
    "7 + 5 - (6 - 5 - 3 / 9) * 2 / (7) - (5 + 7 + 1 / 6 / 2 * 7) * 5 * 7",
    "((8 * (3 * 5 - 1 - 8 / 9 - 3 / 5) / 7 + 3 / 7 / 9 * 9 - 8 * 2 + 8))",
    "9 - (4 + 1 + 4) / (5 + (1) + (5 + 6 + 6 * 10) / 5 * 6 * ((4)) + 3) + 8 / 7",
    "4 * 2 * (9 * 4 / (2 - 7) * 10 * 3 + 7 + 9) * (2 - 3 / 8 - 7 * 6 - 4)",
    "10 + 7 / (1 / (7 * 1 - 8) / 5 / 2 + 6) + (4 / 7 + (7 - 1) / 7) / 3 + 5",
    "(2 * 3) * 4",
    "1 + ((5 * 2) ** 1) ** 0",
    "+2",
    "-2",
    "-2**4",
    "-2**3**2",
    "2 - -2",
    "4 / -2",
    "-+ +-+2",
    "-0 - -1/2 + 3*   -+4/-5",
    "-(2 * 2) ** -3 ** (4 + 5 + 6**-7)",
    "1 + 2 * 3 * 4 ** 5 ** 6 ** 7 ** 8",
    "x",
    "x + y",
    "x + ((5 * y) ** 1) ** z",
    "-a * b",
    "a * -b",
    "-+-a * b",
    "a * +-+b",
    "x - -y",
    "a.b",
    "(a.b).c.d",
    "- a.b ** a.b.c",
    "a[b]",
    "-a[b]",
    "a[b + c]",
    "a[b[c]]",
    "a[b][c]",
    "a.b[c]",
    "a[b].c",
    "a[b].c[d]",
    "a.b[c][d]",
    "a[b.c[d[e].f].g.h[i.j[k]].l]",
    "(  )",  # empty tuple
    "(1, 2, 3)",
    "(1)",
    "(x.y, (1, (2, 3), (a + (((b))) + ()), ()))[z]",
    "((()))",  # empty tuple
    "f()",
    "f(x)",
    "f(x,y)",
    "f(g(x) + h(y, z))",
    "f(g(x + y)[z ** 2]().prop)",
    "a.b(c[d.e(f)]).g.h.i",
    "2**f(3)**4*5+6",
]


@pytest.mark.parametrize("source", source)
def test_expr(source):
    x = expr(source)[0].value
    y = ast.parse(source, mode="eval")
    assert are_equal(x, y)


# def test_0():
#     sources = [
#         "1 * 7 + 2 + 5 - 5 - 5 / 10 * 3 - 7 / 8 / 5 + 4 * 1 - 9 + 6 + 9",
#         "1 + 2 / 1 * 1 / 5 / 10 + 4 * 1 * 5 - 9 + 10 + 10 + 7 - 5 - 7 * 1",
#         "5 + 9 * 7 + 10 * 2 + 9 - 9 + 10 * 2 / 10 - 6 - 6 / 9 / 5 - 8 + 4",
#         "8 / 3 / 10 * 10 * 9 / 2 + 4 + 3 - 10 * 3 + 1 / 10 - 7 * 6 + 10 + 6",
#         "9 + 10 + 1 * 2 - 1 / 8 / 6 - 7 / 7 + 1 - 6 * 6 * 2 - 4 / 9 - 5",
#     ]
#     for source in sources:
#         x = expr(source)[0].value
#         y = ast.parse(source, mode="eval")
#         assert are_equal(x, y)


# def test_1():
#     sources = [
#         "7 + 5 - (6 - 5 - 3 / 9) * 2 / (7) - (5 + 7 + 1 / 6 / 2 * 7) * 5 * 7",
#         "((8 * (3 * 5 - 1 - 8 / 9 - 3 / 5) / 7 + 3 / 7 / 9 * 9 - 8 * 2 + 8))",
#         "9 - (4 + 1 + 4) / (5 + (1) + (5 + 6 + 6 * 10) / 5 * 6 * ((4)) + 3) + 8 / 7",
#         "4 * 2 * (9 * 4 / (2 - 7) * 10 * 3 + 7 + 9) * (2 - 3 / 8 - 7 * 6 - 4)",
#         "10 + 7 / (1 / (7 * 1 - 8) / 5 / 2 + 6) + (4 / 7 + (7 - 1) / 7) / 3 + 5",
#     ]
#     for source in sources:
#         x = expr(source)[0].value
#         y = ast.parse(source, mode="eval")
#         assert are_equal(x, y)


# def test_2():
#     source = "(2 * 3) * 4"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_3():
#     source = "1 + ((5 * 2) ** 1) ** 0"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_4():
#     source = "+2"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_5():
#     source = "-2"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_6():
#     source = "-2**4"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_7():
#     source = "-2**3**2"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_8():
#     source = "2 - -2"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_9():
#     source = "4 / -2"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_10():
#     source = "-+ +-+2"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_11():
#     source = "-0 - -1/2 + 3*   -+4/-5"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_12():
#     source = "-(2 * 2) ** -3 ** (4 + 5 + 6**-7)"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_13():
#     source = "1 + 2 * 3 * 4 ** 5 ** 6 ** 7 ** 8"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_14():
#     source = "x"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_15():
#     source = "x + y"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_16():
#     source = "x + ((5 * y) ** 1) ** z"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_17():
#     source = "-a * b"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_18():
#     source = "a * -b"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_19():
#     source = "-+-a * b"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_20():
#     source = "a * +-+b"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_21():
#     source = "x - -y"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_22():
#     source = "a.b"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_23():
#     source = "(a.b).c.d"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_24():
#     source = "- a.b ** a.b.c"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_25():
#     source = "a[b]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_26():
#     source = "-a[b]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_26():
#     source = "a[b + c]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_27():
#     source = "a[b[c]]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_28():
#     source = "a[b][c]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_29():
#     source = "a.b[c]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_30():
#     source = "a[b].c"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_31():
#     source = "a[b].c[d]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_32():
#     source = "a.b[c][d]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_33():
#     source = "a[b.c[d[e].f].g.h[i.j[k]].l]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_34():
#     source = "(  )"  # empty tuple
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_35():
#     source = "(1, 2, 3)"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_36():
#     source = "(1)"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_37():
#     source = "(x.y, (1, (2, 3), (a + (((b))) + ()), ()))[z]"
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)


# def test_38():
#     source = "((()))"  # empty tuple
#     x = expr(source)[0].value
#     y = ast.parse(source, mode="eval")
#     assert are_equal(x, y)
