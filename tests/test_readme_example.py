
import data_algebra
import data_algebra.test_util

from data_algebra.data_ops import *  # https://github.com/WinVector/data_algebra



def test_readme_example_1():
    d_local = data_algebra.default_data_model.pd.DataFrame({
        'subjectID': [1, 1, 2, 2],
        'surveyCategory': ["withdrawal behavior", "positive re-framing", "withdrawal behavior", "positive re-framing"],
        'assessmentTotal': [5., 2., 3., 4.],
        'irrelevantCol1': ['irrel1'] * 4,
        'irrelevantCol2': ['irrel2'] * 4,
    })

    scale = 0.237

    ops = data_algebra.data_ops.describe_table(d_local, 'd'). \
        extend({'probability': f'(assessmentTotal * {scale}).exp()'}). \
        extend({'total': 'probability.sum()'},
               partition_by='subjectID'). \
        extend({'probability': 'probability/total'}). \
        extend({'sort_key': '-probability'}). \
        extend({'row_number': '_row_number()'},
               partition_by=['subjectID'],
               order_by=['sort_key']). \
        select_rows('row_number == 1'). \
        select_columns(['subjectID', 'surveyCategory', 'probability']). \
        rename_columns({'diagnosis': 'surveyCategory'})

    expect = data_algebra.default_data_model.pd.DataFrame({
        'subjectID': [1, 2],
        'diagnosis': ['withdrawal behavior', 'positive re-framing'],
        'probability': [0.670622, 0.558974],
    })

    data_algebra.test_util.check_transform(ops, data=d_local, expect=expect, float_tol=1e-4)

    py_source = ops.to_python(pretty=True)
    assert isinstance(py_source, str)