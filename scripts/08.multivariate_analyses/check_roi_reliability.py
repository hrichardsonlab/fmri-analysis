"""
Representational Similarity Analysis (RSA) Script

This script calculates the split-half reliability for neural RDMs for pairs of ROIs following the approach described in Skerry & Saxe, 2015

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page

"""
import sys
import pandas as pd
import numpy as np
import argparse
import os.path as op
import os
from itertools import combinations

def calc_roi_reliability(projDir, resultsDir, subjects, mask_opts, niter, nperm):
    
    # check that subject list includes at least 2 subjects
    if len(subjects) < 2:
        raise ValueError('At least 2 subjects are required to calculate ROI reliability!')
        
    # confirm config options
    print('Running ROI split-half reliability analysis using {} iterations'.format(int(niter)))
    
    # define group rsa directory to save outputs
    relDir = op.join(resultsDir, 'group_rdms', 'splithalf_reliability')
    os.makedirs(relDir, exist_ok=True)
    
    # initialise ROI dictionaries where vectorised subject data will be stored
    roi_data_cor = {}
    roi_data_euc = {}

    # read in all subject RDMs and save as stacked dataframe
    for roi in mask_opts:
        # initalise subject RDMs dataframes
        cor_rdms = []
        euc_rdms = []
        
        # for each subject in the list of subjects
        for sub in subjects:
            # define subject RDM directory and check that it exists
            rdmDir = op.join(resultsDir, '{}'.format(sub), 'rsa', 'neural_rdms')
            
            if not op.exists(rdmDir):
                raise IOError('neural RDM directory {} not found.'.format(rdmDir))
        
            # read in averaged neural RDMs for this ROI
            sub_cor_file = op.join(rdmDir, '{}_{}_correlation_averaged_rdm.csv'.format(sub, roi))
            sub_euc_file = op.join(rdmDir, '{}_{}_euclidean_averaged_rdm.csv'.format(sub, roi))
            
            # vectorise and append subject RDM to list of files (this includes the diagonal)
            cor_rdms.append(vectorise_rdm(sub_cor_file, diag=0))
            euc_rdms.append(vectorise_rdm(sub_euc_file, diag=0))
            
        # stack ROI RDMs into dictionary with ROI label
        roi_data_cor[roi] = np.vstack(cor_rdms)
        roi_data_euc[roi] = np.vstack(euc_rdms)
    
    # define all possible ROI pairs
    roi_pairs = list(combinations(mask_opts, 2))
    
    # initialise outputs
    all_iter = []
    all_perm = []
    all_results = []
    
    # loop over ROIs 
    for roi1, roi2 in roi_pairs:
        # initialise outputs
        iter_results = []
        
        print('Calculating split half RDM reliability for ROI pair: {} - {}'.format(roi1, roi2))
            
        # start iteration loop
        for i in range(int(niter)):
            
            # shuffle subject indices
            subject_idx = np.random.permutation(len(subjects))
            
            # use number of subjects to determine how large each half should be (odd number sample sizes will result in uneven groups)
            half = len(subject_idx) // 2
            
            # select subject groups
            group1 = subject_idx[:half]
            group2 = subject_idx[half:]
            
            # print out subject indices as an optional data checking step
            #print('Subject indices for group 1 {}'.format(group1))
            #print('Subject indices for group 2 {}'.format(group2))
            
            # calculate difference scores (and return within and across variables for data checking)  
            within_cor, across_cor, diff_cor = calc_diff_score(roi_data_cor, roi1, roi2, group1, group2)
            within_euc, across_euc, diff_euc = calc_diff_score(roi_data_euc, roi1, roi2, group1, group2)
            
            # append iteration outputs
            # correlation
            iter_results.append({'roi1': roi1,
                                 'roi2': roi2,
                                 'iteration_num': i,
                                 'metric': 'correlation',
                                 'within': within_cor,
                                 'across': across_cor,
                                 'difference': diff_cor})
            
            # euclidean
            iter_results.append({'roi1': roi1,
                                 'roi2': roi2,
                                 'iteration_num': i,
                                 'metric': 'euclidean',
                                 'within': within_euc,
                                 'across': across_euc,
                                 'difference': diff_euc})
            
        # convert iteration results to dataframe
        iter_df = pd.DataFrame(iter_results)
        
        # calculate discrim index separately for each metric (correlation and euclidean) by taking the mean difference score
        discrim_df = (iter_df.groupby(['roi1', 'roi2', 'metric'])['difference']
                             .agg(['mean']).reset_index()
                             .rename(columns={'mean': 'discrim_index'}))
        
        print('{}'.format(discrim_df[['metric', 'discrim_index']]))
        
        # permutation test
        print('Running permutation test using {} permutations'.format(int(nperm)))
        
        # initialise outputs
        perm_results = []
        
        # extract difference scores
        diff_cor_vec = iter_df.query("metric == 'correlation'")['difference'].values
        diff_euc_vec = iter_df.query("metric == 'euclidean'")['difference'].values
        
        for p in range(int(nperm)):
            # generate a random vector the same length as the difference score vector (i.e., number of iterations) of 1s and -1s
            signs = np.random.choice([-1, 1], size=int(niter))
            
            # generate a mean score for this iteration and store all values
            # correlation
            perm_results.append({'roi1': roi1,
                                 'roi2': roi2,
                                 'perm_num': p,
                                 'metric': 'correlation',
                                 'perm_discrim_index': np.mean(diff_cor_vec * signs)})
            
            # euclidean
            perm_results.append({'roi1': roi1,
                                 'roi2': roi2,
                                 'perm_num': p,
                                 'metric': 'euclidean',
                                 'perm_discrim_index': np.mean(diff_euc_vec * signs)})
        
        # convert permutation results to dataframe
        perm_df = pd.DataFrame(perm_results)
        
        # merge perm_df with discrim_df
        p_values = (perm_df.merge(discrim_df, on=['roi1', 'roi2', 'metric']))
        
        # compute a p-value based on the proportion of permuted values that are larger than the observed discrim_index 
        # (i.e., proportion of permuted statistics that are at least as extreme as the observed statistic)
        p_values = (p_values.groupby(['roi1', 'roi2', 'metric'])
                            .apply(lambda x: (x['perm_discrim_index'] >= x['discrim_index'].iloc[0]).mean()).reset_index(name='p_value'))
        
        # merge into results dataframe
        results_df = discrim_df.merge(p_values, on=['roi1', 'roi2', 'metric'])
        
        # append results for this ROI pair
        all_iter.extend(iter_results)
        all_perm.extend(perm_results)
        all_results.append(results_df)

    # convert results to dataframes
    iter_df = pd.DataFrame(all_iter)
    perm_df = pd.DataFrame(all_perm)
    results_df = pd.concat(all_results, ignore_index=True)
    
    # save results
    iter_df.to_csv(op.join(relDir, 'splithalf-iterations.csv'), index=False)
    perm_df.to_csv(op.join(relDir, 'splithalf-permutations.csv'), index=False)
    results_df.to_csv(op.join(relDir, 'splithalf-results.csv'), index=False)

# define function to vectorise the RDMs
def vectorise_rdm(rdm_file, diag):
    # load rdm
    rdm_mat = pd.read_csv(rdm_file, sep=',')
    
    # returns the upper triangle as vector
    # k=0 will include diagonal; k=1 will exclude diagonal
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
def calc_diff_score(roi_data, roi1, roi2, group1, group2):

    ## calculate mean neural pattern
    # roi 1
    roi1_half1 = roi_data[roi1][group1].mean(axis=0)
    roi1_half2 = roi_data[roi1][group2].mean(axis=0)
    
    # roi 2
    roi2_half1 = roi_data[roi2][group1].mean(axis=0)
    roi2_half2 = roi_data[roi2][group2].mean(axis=0)
    
    ## calculate within roi correlations (tau-a)
    within_tau1 = kendall_tau_a(roi1_half1, roi1_half2)
    within_tau2 = kendall_tau_a(roi2_half1, roi2_half2)
    
    # calculate within ROI average
    within = (within_tau1 + within_tau2) / 2
    
    ## calculate across roi correlations (tau-a)
    across_tau1 = kendall_tau_a(roi1_half1, roi2_half2)
    across_tau2 = kendall_tau_a(roi2_half1, roi1_half2)
    
    # calculate across ROI average
    across = (across_tau1 + across_tau2) / 2

    # calculate difference score and append to list
    difference = within - across
    
    # return all metrics
    return within, across, difference
    
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
                        help='List of subjects to process (default: all)')
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
    
    # print if the project directory is not found
    if not op.exists(args.projDir):
        raise IOError('Project directory {} not found.'.format(args.projDir))    
    
    # print if config file is not found
    if not op.exists(args.config):
        raise IOError('Configuration file {} not found. Make sure it is saved in your project directory!'.format(args.config))
        
    # read in configuration file and parse inputs
    config_file=pd.read_csv(args.config, sep='\t', header=None, index_col=0).replace({np.nan: None})
    resultsDir=config_file.loc['resultsDir',1]
    mask_opts=config_file.loc['mask',1].replace(' ','').split(',')
    niter=config_file.loc['splithalf_iterations',1]
    nperm=int(config_file.loc['npermutations',1])
    
    # print if results directory is not specified or found
    if resultsDir == None:
        raise IOError('No resultsDir was specified in config file, but is required to calculate a noise ceiling!')
    
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
    
    # create a calc roi workflow with the inputs defined above
    calc_roi_reliability(args.projDir, resultsDir, args.subjects, mask_opts, niter, nperm)
    
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()
    