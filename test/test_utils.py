'''A set of tests for functions in util.py'''

import os
import sys

import pandas as pd
import pytest

whistl_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(whistl_path + '/../whistl')
import util


data = {'sample1': [1, 1], 'sample2': [2, 2], 'sample3': [3, 3]}
df = pd.DataFrame.from_dict(data)

sample_to_label_1 = {'sample1': 'good', 'sample2': 'bad', 'sample3': 'good'}
sample_to_label_2 = {'sample1': 'bad', 'sample2': 'bad', 'sample3': 'good'}
label_to_encoding_1 = {'good': 1, 'bad': 0}
label_to_encoding_2 = {'good': 0, 'bad': 1}


@pytest.mark.parametrize('df,sample_to_label,label_to_encoding,correct_output',
                         [(df, sample_to_label_1, label_to_encoding_1, [1, 0, 1]),
                          (df, sample_to_label_1, label_to_encoding_2, [0, 1, 0]),
                          (df, sample_to_label_2, label_to_encoding_1, [0, 0, 1]),
                          (df, sample_to_label_2, label_to_encoding_2, [1, 1, 0]),
                          ])
def test_get_labels(df, sample_to_label, label_to_encoding, correct_output):
    assert correct_output == util.get_labels(df, sample_to_label, label_to_encoding)


@pytest.mark.parametrize('df,sample_to_label,label_to_remove,correct_cols',
                         [(df, sample_to_label_1, 'bad', ['sample1', 'sample3']),
                          (df, sample_to_label_1, 'good', ['sample2']),
                          ])
def test_remove_samples_with_label(df, sample_to_label, label_to_remove, correct_cols):
    filtered_df = util.remove_samples_with_label(df, sample_to_label, label_to_remove)
    assert len(filtered_df.columns) == len(correct_cols)
    for test_column, correct_column in zip(filtered_df.columns, correct_cols):
        assert(test_column == correct_column)