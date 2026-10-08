"""Numbers explicitly present in Russian profile evidence, without model guesses."""
import re

ONES = dict(zip("ноль один одна одно два две три четыре пять шесть семь восемь девять".split(), [0,1,1,1,2,2,3,4,5,6,7,8,9]))
TEENS = dict(zip("десять одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать восемнадцать девятнадцать".split(), range(10,20)))
TENS = dict(zip("двадцать тридцать сорок пятьдесят шестьдесят семьдесят восемьдесят девяносто".split(), range(20,100,10)))
HUNDREDS = dict(zip("сто двести триста четыреста пятьсот шестьсот семьсот восемьсот девятьсот".split(), range(100,1000,100)))
WORDS = {**ONES, **TEENS, **TENS, **HUNDREDS}


def evidence_numbers(text, *, height=False):
    tokens = re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?(?!\w)|[а-яё]+", text.casefold())
    values = set()
    i = 0
    while i < len(tokens):
        start = i
        token = tokens[i]
        if re.fullmatch(r"\d+(?:[.,]\d+)?", token):
            value = float(token.replace(",", "."))
            i += 1
        elif token in WORDS:
            value, previous = 0, 10000
            while i < len(tokens) and tokens[i] in WORDS:
                part = WORDS[tokens[i]]
                rank = 100 if part >= 100 else 10 if part >= 20 else 1
                if rank >= previous: break
                value += part
                previous = rank
                i += 1
        else:
            i += 1
            continue
        if tokens[i:i+2] == ["с", "половиной"]:
            value += 0.5
            i += 2
        elif i + 1 < len(tokens) and tokens[i] == "запятая" and tokens[i+1] in ONES:
            value += ONES[tokens[i+1]] / 10
            i += 2
        values.add(round(value, 6))
        if height and i < len(tokens) and tokens[i] in {"метр", "метра", "метров"}:
            values.add(round(value * 100, 6))
        if height and start > 0 and tokens[start-1] in {"метр", "метра"} and value < 100:
            values.add(100 + value)
    return values
