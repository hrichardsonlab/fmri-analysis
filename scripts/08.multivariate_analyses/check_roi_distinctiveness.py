"""
Representational Similarity Analysis (RSA) Script

This script checks the distinctiveness of neural RDMs for pairs of ROIs

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page

"""
import sys
import pandas as pd
import numpy as np
import argparse
import os.path as op
import os
from itertools import combinations
from scipy.stats import rankdata

def calc_roi_distinctiveness(resultsDir, subjects, mask_opts):
    
    # check that subject list includes at least 2 subjects
    if len(subjects) < 2:
        raise ValueError('At least 2 subjects are required to calculate ROI distinctiveness!')
    
    # check that subject IDs aren't duplicated because this would break the leave-one-subject-out group average
    if len(subjects) != len(set(subjects)):
        raise ValueError('Duplicate subject IDs found in subject list!')
        
    # define group rsa directory to save outputs
    relDir = op.join(resultsDir, 'group_rdms')
    os.makedirs(relDir, exist_ok=True)
    
    # initialise ROI dictionaries where vectorised subject data will be stored
    roi_data_cor = {}
    roi_data_euc = {}
    roi_data_sqeuc = {}

    # read in all subject RDMs and save as stacked dataframe
    for roi in mask_opts:
        # initalise subject RDMs dataframes
        cor_rdms = []
        euc_rdms = []
        sqeuc_rdms = []
        
        # for each subject in the list of subjects
        for sub in subjects:
            # define subject RDM directory and check that it exists
            rdmDir = op.join(resultsDir, '{}'.format(sub), 'rsa', 'neural_rdms')
            
            if not op.exists(rdmDir):
                raise IOError('neural RDM directory {} not found.'.format(rdmDir))
        
            # read in averaged neural RDMs for this ROI
            sub_cor_file = op.join(rdmDir, '{}_{}_correlation_averaged_rdm.csv'.format(sub, roi))
            sub_euc_file = op.join(rdmDir, '{}_{}_euclidean_averaged_rdm.csv'.format(sub, roi))
            sub_sqeuc_file = op.join(rdmDir, '{}_{}_squared_euclidean_averaged_rdm.csv'.format(sub, roi))
            
            # vectorise and append subject RDM to list of files (this includes the diagonal)
            cor_rdms.append(vectorise_rdm(sub_cor_file, include_diag='yes'))
            euc_rdms.append(vectorise_rdm(sub_euc_file, include_diag='yes'))
            sqeuc_rdms.append(vectorise_rdm(sub_sqeuc_file, include_diag='yes'))
            
        # stack ROI RDMs into dictionary with ROI label
        roi_data_cor[roi] = np.vstack(cor_rdms)
        roi_data_euc[roi] = np.vstack(euc_rdms)
        roi_data_sqeuc[roi] = np.vstack(sqeuc_rdms)
    
    # define all possible ROI pairs
    roi_pairs = list(combinations(mask_opts, 2))

    # organise the RDM dictionaries by metric
    roi_data_all = {'correlation': roi_data_cor,
                    'euclidean': roi_data_euc,
                    'squared_euclidean': roi_data_sqeuc}


    # rank-transform each subject RDM separately for the group averages
    roi_data_rank = {}

    for metric, roi_data in roi_data_all.items():
        roi_data_rank[metric] = {}

        for roi in mask_opts:
            roi_data_rank[metric][roi] = np.array([rankdata(v) for v in roi_data[roi]])
            
            
    # initialise results
    all_results = []

    # loop over ROI pairs
    for roi1, roi2 in roi_pairs:

        print('Calculating ROI distinctiveness between {} - {}'.format(roi1, roi2))

        # loop over metrics
        for metric, roi_data in roi_data_all.items():
        
            # get rank-transformed RDMs for this metric
            ranked_rdms = roi_data_rank[metric]

            # loop over individual subjects
            for sub_idx, sub in enumerate(subjects):

                # calculate within and across correlations and difference score
                scores = calc_diff_score(roi_data, ranked_rdms, roi1, roi2, sub_idx)

                # append subject-level results
                all_results.append({'subject': sub,
                                    'roi1': roi1,
                                    'roi2': roi2,
                                    'metric': metric,
                                    **scores})

    # convert results to dataframe
    results_df = pd.DataFrame(all_results).sort_values(by=['subject', 'roi1', 'roi2', 'metric']).reset_index(drop=True)
    
    # save results
    results_df.to_csv(op.join(relDir, 'ROI_distinctiveness.csv'), index=False)
    
# define function to vectorise the RDMs
def vectorise_rdm(rdm_file, include_diag):
    # k=0  will include diagonal; k=1 will exclude diagonal
    if include_diag == 'yes':
        diag = 0
    if include_diag == 'no':
        diag = 1
    
    # load rdm
    rdm_mat = pd.read_csv(rdm_file, sep=',')
    
    # returns the upper triangle as vector
    return rdm_mat.values[np.triu_indices_from(rdm_mat, k=diag)]
    
# define function to calculate Kendall's tau-a
def kendall_tau_a(x_vec, y_vec):
    n = len(x_vec)
    
    # pairwise differences
    x_diff = x_vec[:, None] - x_vec
    y_diff = y_vec[:, None] - y_vec
    
    # calculate concordance/discordance
    #discord = x_diff * y_diff
    discord = np.sign(x_diff) * np.sign(y_diff)
    
    # take the upper triangle only (excluding diagonal)
    tri_indx = np.triu_indices(n, k=1)
    
    # extract concordant and discordant values
    # C = np.sum(discord[tri_indx] > 0)
    # D = np.sum(discord[tri_indx] < 0)
    # numerator (ties naturally become 0 because sign(0)=0)
    numerator = np.sum(discord[tri_indx])
    
    # use values in kendall's tau-a formula
    # tau_a = (C - D) / (n * (n - 1) / 2)
    tau_a = numerator / (n * (n - 1) / 2)
    
    return tau_a
    
# define function to calculate difference score
# this is done with a function to avoid having to duplicate everything for correlation and euclidean RDMs
def calc_diff_score(roi_data, roi_data_rank, roi1, roi2, sub_idx):

    # identify all subjects except the current subject
    n = roi_data[roi1].shape[0]
    group_idx = np.arange(n) != sub_idx

    # extract original individual subject RDMs
    sub_roi1 = roi_data[roi1][sub_idx]
    sub_roi2 = roi_data[roi2][sub_idx]

    # calculate leave-one-subject-out group average using the rank-transformed subject RDMs
    group_roi1 = roi_data_rank[roi1][group_idx].mean(axis=0)
    group_roi2 = roi_data_rank[roi2][group_idx].mean(axis=0)

    # within-ROI similarities
    within_tau1 = kendall_tau_a(sub_roi1, group_roi1)
    within_tau2 = kendall_tau_a(sub_roi2, group_roi2)

    # across-ROI similarities
    across_tau1 = kendall_tau_a(sub_roi1, group_roi2)
    across_tau2 = kendall_tau_a(sub_roi2, group_roi1)

    # average within and across similarities
    within = (within_tau1 + within_tau2) / 2
    across = (across_tau1 + across_tau2) / 2

    # calculate ROI distinctiveness
    difference = within - across

    return {'within_roi1': within_tau1,
            'within_roi2': within_tau2,
            'across_roi1_roi2': across_tau1,
            'across_roi2_roi1': across_tau2,
            'within': within,
            'across': across,
            'difference': difference}

# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-p', dest='projDir',
                        help='Project directory')
    parser.add_argument('-o', dest='outDir', default=os.getcwd(),
                        help='Output directory')
    parser.add_argument('-s', dest='subjects', nargs='*',
                        help='List of subjects to process')
    parser.add_argument('-r', dest='runs', nargs='*',
                        help='List of runs for each subject')    
    parser.add_argument('-c', dest='config',
                        help='Configuration file')                                            
    parser.add_argument('-m', dest='plugin',
                        help='Nipype plugin to use (default: MultiProc)')
    return parser
    
# define main function that parses the config file and runs the functions defined above
def main(argv=None):
    # don't buffer messages
    sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)
    
    # call argparser function that defines command line inputs
    parser = argparser()
    args = parser.parse_args(argv)
    
    # print if config file is not found
    if not op.exists(args.config):
        raise IOError('Configuration file {} not found. Make sure it is saved in your project directory!'.format(args.config))
        
    # read in configuration file and parse inputs
    config_file=pd.read_csv(args.config, sep='\t', header=None, index_col=0).replace({np.nan: None})
    resultsDir=config_file.loc['resultsDir',1]
    mask_opts=config_file.loc['mask',1].replace(' ','').split(',')
    
    # print if results directory is not specified or found
    if resultsDir == None:
        raise IOError('No resultsDir was specified in config file, but is required to calculate ROI distinctiveness!')
    
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
    
    # identify analysis README file
    readme_file=op.join(resultsDir, 'README.txt')
    
    # add config details to project README file
    with open(readme_file, 'a') as file_1:
        file_1.write('\n')
        file_1.write('The distinctiveness of ROI RDMs was assessed using the check_roi_distinctiveness.py script and options specified in the config file: {} \n'.format(args.config))
        file_1.write('The following ROIs were checked: {} \n'.format(mask_opts))
        
    # create a calc roi workflow with the inputs defined above
    calc_roi_distinctiveness(resultsDir, args.subjects, mask_opts)
    
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()
    