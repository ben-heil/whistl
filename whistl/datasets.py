'''Functions for creating dataset objects from the raw data directories/compendia and otherwise
decoupling the data access, and model training portions of the code'''
import functools
import json
import os

import numpy as np
import pandas as pd
from torch.utils.data import Dataset

import utils


def get_labels_for_expression_df(df, sample_to_label, encoder):
    '''Get the encoded labels corresponding to the dataframe's samples' phenotypes

    Arguments
    ---------
    df: pandas DataFrame
        The gene expression data to get labels for
    sample_to_label: dict
        A dict mapping samples accessions to their corresponding phenotype label
    encoder: sklearn.preprocessing.LabelEncoder
        An encoder object that maps phenotype names to labels

    Returns
    -------
    labels: list of strs
    '''
    samples = df.columns
    labels = []

    for sample in samples:
        labels.append(sample_to_label[sample])
    labels = encoder.transform(labels)

    return labels


@functools.lru_cache()
def load_compendium_file(compendium_path):
    '''Load the compendium data from a tsv file

    Arguments
    ---------
    compendium_path: str or Path
        The path to the tsv containing gene expression data

    Returns
    -------
    expression_df: pandas DataFrame
        A dataframe where the rows are genes and the columns are samples
    '''
    expression_df = pd.read_csv(compendium_path, sep='\t', index_col=0)

    return expression_df


def parse_metadata_file(metadata_path):
    '''

    Arguments
    ---------
    metadata_path: str or Path object
        The file containing metadata for all samples in the compendium

    Returns
    -------
    metadata: json
        The json object stored at metadata_path
    '''
    with open(metadata_path) as metadata_file:
        metadata = json.load(metadata_file)
        return metadata


def create_sample_to_study_mapping(metadata):
    '''Generate a dictionary mapping each sample to the study it came from

    Arguments
    ---------
    metadata: json
        A json object containing the metadata for a study

    Returns
    -------
    sample_to_study: dict
        A dictionary mapping each sample accession to its corresponding study accession
    '''
    sample_to_study = {}

    experiment_metadata = metadata['experiments']

    for experiment in experiment_metadata:
        try:
            samples = experiment_metadata[experiment]['sample_accession_codes']
            for sample in samples:
                sample_to_study[sample] = experiment
        except KeyError:
            # If an experiment doesn't have any samples for some reason, skip it
            pass

    return sample_to_study


def create_study_to_sample_mapping(metadata):
    '''Create a dictionary mapping study accessions to the accessions of samples in the study

    Arguments
    ---------
    metadata: json
        A json object containing the metadata for a study

    Returns
    -------
    study_to_sample: dict
        A dict mapping study accessions to the accessions of samples they contain
    '''
    study_to_sample = {}

    experiment_metadata = metadata['experiments']

    for experiment in experiment_metadata:
        try:
            study_to_sample[experiment] = experiment_metadata[experiment]['sample_accession_codes']
        except KeyError:
            # If an experiment doesn't have any samples for some reason, skip it
            pass

    return study_to_sample


def subset_expression_by_study(expression_df, studies, sample_to_study):
    '''Subset a dataframe to contain only the samples contained in the given studies

    Arguments
    ---------
    expression_df: pandas Dataframe
        A dataframe where the rows are genes and the columns are sample
    studies: list of strr
        A list of the accessions for studies to be included in the dataset
    sample_to_study: dict
        A dict mapping sample accessions to their corresponding studies

    Returns
    -------
    subset_df: pandas DataFrame
        The subset of the dataframe passed in containing only samples from the given studies
    '''
    study_set = set(studies)
    samples_to_keep = []

    all_samples = expression_df.columns

    for sample in all_samples:
        if sample_to_study[sample] in study_set:
            samples_to_keep.append(sample)

    subset_df = expression_df.loc[:, samples_to_keep]

    return subset_df


def subset_expression_by_class(expression_df, classes, sample_to_label):
    '''Subset a dataframe to contain only samples with the phenotypes passed in

    Arguments
    ---------
    expression_df: pandas Dataframe
        A dataframe where the rows are genes and the columns are samples
    classes: list of str
        A list of the phenotypes to be included in the dataset
    sample_to_label: dict
        A dict mapping samples accessions to their corresponding phenotype label

    Returns
    -------
    subset_df: pandas.DataFrame
        The subset of the dataframe passed in containing only samples with the given phenotypes
    '''
    # It may be more efficient to just iterate over all samples in the dataframe.
    # It shouldn't be a big difference either way, so I'll leave it be for now
    labeled_samples = set(sample_to_label.keys())
    intersect_samples = labeled_samples.intersection(expression_df.columns)

    samples_to_keep = []
    for sample in intersect_samples:
        if sample_to_label[sample] in classes:
            samples_to_keep.append(sample)

    subset_df = expression_df.loc[:, samples_to_keep]

    return subset_df


def get_data_dirs(data_root):
    ''' Extract all the data subdirectories in a given root directory

    Arguments
    ---------
    data_root: str or Path
        The root directory whose subdirectories contain gene expression data

    Returns
    -------
    data_dirs: list of str or Path
        The list of directories containing gene expression data
    '''
    # List everything in data_root
    subfiles = [os.path.join(data_root, f) for f in os.listdir(data_root)]
    # Keep only data directories, not anything else that might be in data_root

    data_dirs = []
    for f in subfiles:
        if ('SRP' in f or 'GSE' in f or 'E-MEXP' in f) and os.path.isdir(f):
            data_dirs.append(f)

    return data_dirs


def extract_dirs_with_label(data_dirs, disease_label, sample_to_label):
    ''' Split the list of directories passed in into those that contain samples with a given
    disease, and those that don't

    Arguments
    ---------
    data_dirs: list of str or Path
        A list of directories containing gene expression data
    disease_label: str
        The name of the disease whose samples will be used in testing
    sample_to_label: dict
        A string to string dict mapping sample ids to their corresponding label string.
        E.g. {'GSM297791': 'sepsis'}

    Returns
    -------
    dirs_without_label: list of str or Path
        The directories from data_dirs not containing any samples corresponding to disease_label
    dirs_with_label: list of str or Path
        The directories from data_dirs that do contain samples with the provided disease
    '''
    dirs_without_label = []
    dirs_with_label = []

    for data_dir in data_dirs:
        study = os.path.basename(os.path.normpath(data_dir))
        study_file_name = study + '.tsv'
        data_file = os.path.join(data_dir, study_file_name)

        sample_ids = None
        with open(data_file, 'r') as in_file:
            # The tsv header contains all the sample ids for the study
            sample_ids = in_file.readline()
            sample_ids = sample_ids.strip().split('\t')

        for sample_id in sample_ids:
            if sample_id in sample_to_label:
                if sample_to_label[sample_id] == disease_label:
                    dirs_with_label.append(data_dir)
                    break
        else:
            # If the the dir isn't added to dirs_with_label, add to dirs_without_label
            dirs_without_label.append(data_dir)

    return dirs_without_label, dirs_with_label


def get_gene_intersection(data_dirs):
    '''Find the set of genes present in all samples in data_dirs

    Arguments
    ---------
    data_dirs: list of str or Path
        The path to the directories containing the studies used in model training

    Returns
    -------
    genes_to_use: list of str
        The list of gene ids for genes present in all samples in all data directories
    '''
    df_list = []

    for data_dir in data_dirs:
        study = os.path.basename(os.path.normpath(data_dir))
        study_file_name = study + '.tsv'
        data_file = os.path.join(data_dir, study_file_name)
        curr_df = pd.read_csv(data_file, sep='\t')

        curr_df = curr_df.set_index('Gene')
        df_list.append(curr_df)

    combined_df = pd.concat(df_list, axis=1, join='inner')
    genes_to_use = list(combined_df.index)

    return genes_to_use


def get_dataframe_from_dirs(data_dirs, classes, sample_to_label, genes_to_use):
    '''
    Arguments
    ---------
    data_dirs: list of str
        The directories to create a dataframe for
    classes: list of str
        The labels to load data for
    sample_to_label: dict
        A string to string dict mapping sample ids to their corresponding label string.
        E.g. {'GSM297791': 'sepsis'}

    Returns
    -------
    selected_studies_df: pandas.DataFrame
        A dataframe containing the expression data for the studies in data_dirs
    labels: numpy.array
    '''
    disease_and_healthy_classes = classes + ['healthy']
    label_to_encoding = utils.generate_encoding(disease_and_healthy_classes)

    # Extract data from each directory
    df_list = []
    labels = []
    for data_dir in data_dirs:
        curr_df, study_labels = parse_study_dir(data_dir, sample_to_label, label_to_encoding,
                                                genes_to_use)
        if curr_df is None or study_labels is None:
            continue

        df_list.append(curr_df)
        labels.extend(study_labels)

    # Combine dataframes into a single df
    selected_studies_df = pd.concat(df_list, axis=1, join='inner')
    labels = np.array(labels)

    assert len(labels) == len(selected_studies_df.columns)

    return selected_studies_df, labels


def get_dataframe_from_compendium():
    '''

    Arguments
    ---------

    Returns
    -------
    '''
    raise NotImplementedError


def parse_study_dir(data_dir, sample_to_label, label_to_encoding, genes_to_keep):
    '''This function extracts the gene expression data and labels for a single study

    Arguments
    ---------
    data_dir: str
        The path to the directories where the data are stored. These are generally directories
        within the unzipped main directory downloaded from refine.bio, and will contain
        data for a single study.
    sample_to_label: dict
        A dictionary mapping sample identifiers to their corresponding labels
    label_to_encoding: dict
        A dictionary mapping the string label (e.g. 'sepsis') to a numerical target like 0
    genes_to_keep: list of strs
        The list of gene identifiers to be kept in the dataframe

    Returns
    -------
    curr_df: pandas.DataFrame
        A single dataframe containing the expression data of all genes in genes_to_keep for all
        samples in the study
    study_labels: list of ints
        Labels corresponding to whether each sample contains to septic or healthy gene expression
    '''
    study = os.path.basename(os.path.normpath(data_dir))
    study_file_name = study + '.tsv'
    data_file = os.path.join(data_dir, study_file_name)
    curr_df = pd.read_csv(data_file, sep='\t')

    curr_df = curr_df.set_index('Gene')

    # Remove samples that don't fall into a class of interest
    labels_to_keep = label_to_encoding.keys()
    curr_df = utils.keep_samples_with_labels(curr_df, sample_to_label, labels_to_keep)

    # If keep_samples_with_labels returns None, we should return None for the labels as well
    if curr_df is None:
        return (None, None)

    # Retrieve labels for each sample
    study_labels = utils.get_labels(curr_df, sample_to_label, label_to_encoding)

    curr_df = curr_df.loc[genes_to_keep, :]

    return curr_df, study_labels


class RefineBioDataset(Dataset):
    ''' A dataset of one or more studies pulled from refine.bio'''
    def get_feature_count(self):
        '''Get the number of features for the samples in the dataset'''
        return len(self.gene_expression.columns)

    def __init__(self, data_dirs, classes, sample_to_label, genes_to_use):
        ''' The dataset's constructor function

        Arguments
        ---------
        '''
        data, labels = get_dataframe_from_dirs(data_dirs, classes, sample_to_label,
                                               genes_to_use)

        self.gene_expression = data
        self.labels = labels

    def __getitem__(self, idx):
        '''

        Arguments
        ---------
        idx: int
            The index of the sample to retrieve

        Returns
        -------
        sample: numpy.array
            The gene expression information for the sample at index idx
        label: int
            The label for the sample at index idx
        id_: string
            The sample identifier for the given sample
        '''
        sample = self.gene_expression.iloc[:, idx].values
        label = np.array(self.labels[idx])
        id_ = self.gene_expression.columns[idx]

        return sample, label, id_

    def __len__(self):
        '''Provides the number of samples in the dataset'''
        return len(self.labels)


class CompendiumDataset(Dataset):
    '''A dataset of one or more studies pulled from the refine.bio human compendium'''

    def __init__(self, studies, classes, sample_to_label, metadata_path, compendium_path, encoder):
        '''Initialize a CompendiumDataset object

        Arguments
        ---------
        studies: list of str
            The accessions of studies to be included in the dataset
        classes: list of str
            The phenotypes to be included in the dataset
        sample_to_label: dict
            A dictionary mapping sample identifiers to their corresponding labels
        metadata_path: str or Path object
            The file containing metadata for all samples in the compendium
        compendium_path: str or Path object
            The path to the tsv containing gene expression data
        encoder: sklearn.preprocessing.LabelEncoder
            An encoder object that maps phenotype names to labels
        '''

        metadata = parse_metadata_file(metadata_path)
        sample_to_study = create_sample_to_study_mapping(metadata)

        all_data = load_compendium_file(compendium_path)
        data = subset_expression_by_study(all_data, studies, sample_to_study)
        data = subset_expression_by_class(data, classes, sample_to_label)
        labels = get_labels_for_expression_df(data, sample_to_label, encoder)

        self.gene_expression = data
        self.labels = labels
        self.encoder = encoder

    def __getitem__(self, idx):
        '''

        Arguments
        ---------
        idx: int
            The index of the sample to retrieve

        Returns
        -------
        sample: numpy.array
            The gene expression information for the sample at index idx
        label: int
            The label for the sample at index idx
        id_: string
            The sample identifier for the given sample
        '''
        sample = self.gene_expression.iloc[:, idx].values
        label = np.array(self.labels[idx])
        id_ = self.gene_expression.columns[idx]

        return sample, label, id_

    def __len__(self):
        '''Provides the number of samples in the dataset'''
        return len(self.labels)
