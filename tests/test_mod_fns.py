

import data_algebra.test_util
from data_algebra.data_ops import *

import data_algebra
import data_algebra.util
import data_algebra.test_util
import data_algebra.PostgreSQL
import data_algebra.BigQuery
import data_algebra.MySQL
import data_algebra.SparkSQL

import pytest


def test_mod_fns_one():
    d = data_algebra.default_data_model.pd.DataFrame(
        {"a": [1, 2, 3, 4], "b": [2, 2, 3, 3],}
    )

    ops = (
        descr(d=d)
            .extend({
                'p': 'a % b',
                'q': 'a.mod(b)',
                'r': 'a.remainder(b)',
            })
    )

    expect = data_algebra.default_data_model.pd.DataFrame({
        'a': [1, 2, 3, 4],
        'b': [2, 2, 3, 3],
        'p': [1, 0, 0, 1],
        'q': [1, 0, 0, 1],
        'r': [1, 0, 0, 1],
        })
    res_pandas = ops.transform(d)
    assert data_algebra.test_util.equivalent_frames(res_pandas, expect)

    with pytest.warns(UserWarning):  # TODO: elim these warnings
        data_algebra.test_util.check_transform(
            ops=ops,
            data=d,
            expect=expect,
            models_to_skip={
                # TODO: run these down
                str(data_algebra.PostgreSQL.PostgreSQLModel()),  # SQLAlchemy throws a type error on conversion
                str(data_algebra.BigQuery.BigQueryModel()),
                str(data_algebra.MySQL.MySQLModel()),
                str(data_algebra.SparkSQL.SparkSQLModel())
            })


def test_mod_fns_one_edited():
    d = data_algebra.default_data_model.pd.DataFrame(
        {"a": [1, 2, 3, 4], "b": [2, 2, 3, 3],}
    )

    ops = (
        descr(d=d)
            .extend({
                'q': 'a.mod(b)',
                'r': 'a.remainder(b)',
            })
    )

    expect = data_algebra.default_data_model.pd.DataFrame({
        'a': [1, 2, 3, 4],
        'b': [2, 2, 3, 3],
        'q': [1, 0, 0, 1],
        'r': [1, 0, 0, 1],
        })
    res_pandas = ops.transform(d)
    assert data_algebra.test_util.equivalent_frames(res_pandas, expect)

    with pytest.warns(UserWarning):  # TODO: elim these warnings
        data_algebra.test_util.check_transform(
            ops=ops,
            data=d,
            expect=expect,
            models_to_skip={
                # TODO: run these down
                str(data_algebra.PostgreSQL.PostgreSQLModel()),  # REMAINDER not applicable to given column types
                str(data_algebra.BigQuery.BigQueryModel()),  # fn not named REMAINDER
                str(data_algebra.MySQL.MySQLModel()),  # fn not named REMAINDER
                str(data_algebra.SparkSQL.SparkSQLModel()),  # fn not named REMAINDER
            }
        )
