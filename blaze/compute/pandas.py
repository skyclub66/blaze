"""

>>> from blaze.expr.table import TableSymbol
>>> from blaze.compute.pandas import compute

>>> accounts = TableSymbol('{name: string, amount: int}')
>>> deadbeats = accounts['name'][accounts['amount'] < 0]

>>> from pandas import DataFrame
>>> data = [['Alice', 100], ['Bob', -50], ['Charlie', -20]]
>>> df = DataFrame(data, columns=['name', 'amount'])
>>> compute(deadbeats, df)
1        Bob
2    Charlie
Name: name, dtype: object
"""
from __future__ import absolute_import, division, print_function

import pandas as pd
from pandas import DataFrame, Series
from multipledispatch import dispatch
import numpy as np

from ..expr.table import *


@dispatch(Projection, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    return parent[list(t.columns)]


@dispatch(Column, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    return parent[t.columns[0]]


@dispatch(BinOp, DataFrame)
def compute(t, df):
    lhs = compute(t.lhs, df)
    rhs = compute(t.rhs, df)
    return t.op(lhs, rhs)


@dispatch(Selection, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    predicate = compute(t.predicate, df)
    return parent[predicate]


@dispatch(TableSymbol, DataFrame)
def compute(t, df):
    if not list(t.columns) == list(df.columns):
        # TODO also check dtype
        raise ValueError("Schema mismatch: \n\nTable:\n%s\n\nDataFrame:\n%s"
                        % (t, df))
    return df


@dispatch(Join, DataFrame, DataFrame)
def compute(t, lhs, rhs):
    """ Join two pandas data frames on arbitrary columns

    The approach taken here could probably be improved.

    To join on two columns we force each column to be the index of the
    dataframe, perform the join, and then reset the index back to the left
    side's original index.
    """
    lhs = compute(t.lhs, lhs)
    rhs = compute(t.rhs, rhs)
    old_left_index = lhs.index
    old_right_index = rhs.index
    if lhs.index.name:
        old_left = lhs.index.name
        rhs = lhs.reset_index()
    if rhs.index.name:
        rhs = rhs.reset_index()

    lhs = lhs.set_index(t.on_left)
    rhs = rhs.set_index(t.on_right)
    result = lhs.join(rhs)
    return result.reset_index()[t.columns]


@dispatch(UnaryOp, DataFrame)
def compute(t, s):
    parent = compute(t.parent, s)
    op = getattr(np, t.symbol)
    return op(parent)


@dispatch(Reduction, DataFrame)
def compute(t, s):
    parent = compute(t.parent, s)
    assert isinstance(parent, Series)
    op = getattr(Series, t.symbol)
    return op(parent)


@dispatch(distinct, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    return parent.drop_duplicates()


@dispatch(By, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    grouper = compute(t.grouper, parent)
    if type(t.grouper) == Projection and t.grouper.parent == t.parent:
        grouper = list(grouper.columns)

    return parent.groupby(grouper).apply(lambda x: compute(t.apply, x))


@dispatch(Sort, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    if isinstance(parent, Series):
        result = parent.copy()
        result.sort(t.column, ascending=t.ascending)
    else:
        result = parent.sort(t.column, ascending=t.ascending)
    return result


@dispatch(Head, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    return parent.head(t.n)


@dispatch(Label, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    if isinstance(parent, Series):
        return Series(parent, name=t.label)
    if isinstance(parent, DataFrame):
        return DataFrame(parent, columns=[t.label])


@dispatch(ReLabel, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    return DataFrame(parent, columns=t.columns)


@dispatch(Map, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    if isinstance(parent, Series):
        return parent.map(t.func)
    else:
        return parent.apply(lambda tup: t.func(*tup), axis=1)


@dispatch(Apply, DataFrame)
def compute(t, df):
    parent = compute(t.parent, df)
    return t.func(parent)
