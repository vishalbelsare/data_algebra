

from data_algebra.data_ops import *
import data_algebra.test_util

def test_select_rows_1():
    d = data_algebra.default_data_model.pd.DataFrame({"x": [1, 2], "y": [3, 4]})

    ops = describe_table(d, table_name="d").select_rows("x == 1")

    d_sel = ops.transform(d)
    # note type(d.iloc[0, :]) is pandas.core.series.Series

    assert isinstance(d_sel, data_algebra.default_data_model.pd.DataFrame)


def test_select_rows_2():
    d = data_algebra.default_data_model.pd.DataFrame({"x": [-2, 0, 3], "y": [1, 2, 3]})

    ops = describe_table(d, table_name="d").select_rows("x.sign() == 1")

    d_sel = ops.transform(d)

    expect = data_algebra.default_data_model.pd.DataFrame({'x': [3], 'y': [3]})
    assert data_algebra.test_util.equivalent_frames(d_sel, expect)


def test_select_columns_1():
    d = data_algebra.default_data_model.pd.DataFrame({"x": [1, 2], "y": [3, 4]})

    ops = describe_table(d, table_name="d").select_columns(["x"])

    d_sel = ops.transform(d)
    # note type(d.iloc[:, 0]) is pandas.core.series.Series

    assert isinstance(d_sel, data_algebra.default_data_model.pd.DataFrame)
