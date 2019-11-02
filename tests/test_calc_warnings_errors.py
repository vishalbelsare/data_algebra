import pandas
import pytest
from data_algebra.data_ops import *


def test_calc_warnings_errors():
    d = pandas.DataFrame({
        'x': [1, 2, 3],
        'y': [4, 5, 6],
    })

    with pytest.raises(ValueError):
        describe_table(d). \
            extend({
            'x': 'x+1',
            'y': 'x+2'})

    describe_table(d). \
        extend({
        'x': 'x+1',
        'y': '2'})

    with pytest.raises(NameError):
        describe_table(d). \
            extend({
            'x': 'z+1'})

    with pytest.raises(ValueError):
        describe_table(d). \
            extend([
            ('x', 1),
            ('x', 2)])

    with pytest.raises(ValueError):
        describe_table(d). \
            project({
            'x': 'x+1',
            'y': 'x+2'})

    with pytest.raises(NameError):
        describe_table(d). \
            project({
            'x': 'z+1'})

    with pytest.raises(ValueError):
        describe_table(d). \
            project([
            ('x', 1),
            ('x', 2)])

    describe_table(d). \
        project({
        'x': 'x+1',
        'y': '2'})
