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
from json import dumps, loads

opt_whitespace = RegExp("\\s*")

lbrace = String("{").t()
rbrace = String("}").t()

lbrak = String("[").t()
rbrak = String("]").t()

colon = String(":").t()
comma = String(",").t()

true = String("true").then(Return(True)).t()
false = String("false").then(Return(False)).t()
null = String("null").then(Return(None)).t()

string = (
    RegExp(r'"(((?=\\)\\(["\\\/bfnrt]|u[0-9a-fA-F]{4}))|[^"\\\0-\x1F\x7F]+)*"')
    .map(lambda s: s[1:-1])
    .t()
)
number = RegExp(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?").map(float).t()

value = Parser.alt(
    string, number, true, false, null, Lazy(lambda: object), Lazy(lambda: array)
)

object = (
    lbrace.then(Parser.seq(string.skip(colon), value).sep_by(comma))
    .skip(rbrace)
    .map(lambda kvs: {k: v for k, v in kvs})
)

array = lbrak.then(value.sep_by(comma)).skip(rbrak)

json = opt_whitespace.then(value)


def test_primitives():
    assert json("true")[0].value == True
    assert json("false")[0].value == False
    assert json("null")[0].value == None
    assert json('"hi, mom!"')[0].value == "hi, mom!"
    assert json('"hi, mom! 123 $%"')[0].value == "hi, mom! 123 $%"
    assert json("123")[0].value == 123
    assert json("123.456")[0].value == 123.456
    assert json("-123.456e10")[0].value == -123.456e10
    assert json("-123.456E-10")[0].value == -123.456e-10


def test_object():
    source = """{
"ab c'!": "123.0",
"def": 456.0,
"ghi": 789.0,
"jkl": true,
"mno": false,
"pqr": null,
"stu": {"v": 1.0, "w": null},
"x": [1.0,{"y":"z"},3.0]
}
"""
    assert dumps(json(source)[0].value) == dumps(loads(source))
