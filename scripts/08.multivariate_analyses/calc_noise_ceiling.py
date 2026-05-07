"""
Representational Similarity Analysis (RSA) Script

This script calculates the noise ceiling based on a group of subject neural RDMs for a set of ROIs. 

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page

"""
import sys
import pandas as pd
import numpy as np
import argparse
import os.path as op
import os
from scipy.stats import rankdata
from scipy.spatial.distance import squareform

def calc_noise_ceiling(projDir, sharedDir, resultsDir, subjects, conditions, mask_opts):
    
    # check that subject list includes at least 2 subjects
    if len(subjects) < 2:
        raise ValueError('At least 2 subjects are required to calculate a noise ceiling!')
    
    # define group rsa directory to save outputs
    groupDir = op.join(resultsDir, 'group_rdms')
    os.makedirs(groupDir, exist_ok=True)
    
    # initialise noise ceiling stats
    ceiling_stats = []
    
    # loop over ROIs 
    for roi in mask_opts:
        print('Generating noise ceiling estimates for: {}'.format(roi))
        
        # initalise subject RDMs dataframes
        cor_files = []
        euc_files = []
        
        # for each subject in the list of subjects
        for sub in subjects:
            # define subject RDM directory and check that it exists
            rdmDir = op.join(resultsDir, '{}'.format(sub), 'rsa', 'neural_rdms')
            
            if not op.exists(rdmDir):
                raise IOError('neural RDM directory {} not found.'.format(rdmDir))
                
            # read in averaged neural RDMs for this ROI
            sub_cor_file = op.join(rdmDir, '{}_{}_correlation_averaged_rdm.csv'.format(sub, roi))
            sub_euc_file = op.join(rdmDir, '{}_{}_euclidean_averaged_rdm.csv'.format(sub, roi))
            
            # append subject RDM to list of files
            cor_files.append(sub_cor_file)
            euc_files.append(sub_euc_file)
        
        # convert rdms to vectors and store as array
        cor_rdms = np.array([vectorise_rdm(f, diag=0) for f in cor_files])
        euc_rdms = np.array([vectorise_rdm(f, diag=0) for f in euc_files])
        
        # rank-transform the vectors (just to calculate average across subjects)
        cor_rdms_rank = np.array([rankdata(v) for v in cor_rdms])
        euc_rdms_rank = np.array([rankdata(v) for v in euc_rdms])
        
        # print the dimensions of the stacked rdms as a data checking step
        print('Dimensions of the stacked vectors for {} [subjects X number of paired comparisons]: {}'.format(roi, cor_rdms_rank.shape))
        
        # calculate group mean including all subjects
        print('Averaging all {} neural RDMs to generate group RDM for upper bound calculation...'.format(roi))
        group_cor_rdm = cor_rdms_rank.mean(axis=0)
        group_euc_rdm = euc_rdms_rank.mean(axis=0)
        
        # convert vectors back to symmetric matrices
        group_cor_mat = squareform(group_cor_rdm)
        group_euc_mat = squareform(group_euc_rdm)
        
        # convert matrices to dataframes
        group_cor_df = pd.DataFrame(group_cor_mat)
        group_euc_df = pd.DataFrame(group_euc_mat)
            
        # save group average RDMs
        group_cor_file = op.join(groupDir, 'group_rdm_{}-correlation.csv'.format(roi))
        group_euc_file = op.join(groupDir, 'group_rdm_{}-euclidean.csv'.format(roi))
        group_cor_df.to_csv(group_cor_file, index=False)
        group_euc_df.to_csv(group_euc_file, index=False)
        print('Saved {} group average RDMs to: {}'.format(roi, group_cor_file))
        print('Saved {} group average RDMs to: {}'.format(roi, group_euc_file))
        
        # STEP 1: calculate upper bound by correlating each subject RDM with the rank-transformed group RDM
        # tau-a using custom function
        ## correlation distance
        tau_cor_upper = [kendall_tau_a(cor_rdms[s], group_cor_rdm)
        for s in range(len(cor_rdms))]
        
        ## euclidean distance
        tau_euc_upper = [kendall_tau_a(euc_rdms[s], group_euc_rdm)
        for s in range(len(euc_rdms))]
        
        # take average across subjects as the upper bound
        upper_cor = np.mean(tau_cor_upper)
        upper_euc = np.mean(tau_euc_upper)
        
        #print('Subject correlations with average group correlation RDM: {}'.format(tau_cor_upper))
        print('Upper bound (correlation distance): {}'.format(upper_cor))
        
        #print('Subject correlations with average group Euclidean RDM: {}'.format(tau_euc_upper))
        print('Upper bound (Euclidean distance): {}'.format(upper_euc))
        
        # initialise subject level outputs
        sub_stats = []
        
        for sub, upper_cor_sub, upper_euc_sub in zip(subjects, tau_cor_upper, tau_euc_upper):

            # append subject upper bound stats to dataframe
            sub_stats.append({'sub': sub,
                              'roi': roi,
                              'type': 'upper',
                              'tau_a_cor': upper_cor_sub,
                              'tau_a_euc': upper_euc_sub})         
        
        # STEP 2: calculate lower bound by correlating each subject RDM with the leave-one-subject-out rank-transformed group RDM
        print('Generating leave-one-subject-out group RDMs for lower bound calculation...')
        
        # sum rank-transformed RDMs across all subjects
        cor_rdms_sum = cor_rdms_rank.sum(axis=0)
        euc_rdms_sum = euc_rdms_rank.sum(axis=0)
        
        # initialise lists to store subject correlations
        tau_cor_lower = []
        tau_euc_lower = []
        
        # loop over subjects
        for s, sub in enumerate(subjects):
            
            # calculate leave-one-subject-out average RDMs
            loso_cor_rdm = (cor_rdms_sum - cor_rdms_rank[s]) / (len(subjects) - 1)
            loso_euc_rdm = (euc_rdms_sum - euc_rdms_rank[s]) / (len(subjects) - 1)
            
            # correlate subject RDM with leave-one-subject-out group RDM
            tau_cor = kendall_tau_a(cor_rdms[s], loso_cor_rdm)
            tau_euc = kendall_tau_a(euc_rdms[s], loso_euc_rdm)
        
            # append subject statistics
            tau_cor_lower.append(tau_cor)
            tau_euc_lower.append(tau_euc)
            
            # append subject lower bound stats to dataframe
            sub_stats.append({'sub': sub,
                              'roi': roi,
                              'type': 'lower',
                              'tau_a_euc': tau_euc,
                              'tau_a_cor': tau_cor})
        
        # take average across subjects as the lower bound
        lower_cor = np.mean(tau_cor_lower)
        lower_euc = np.mean(tau_euc_lower)
        
        print('Lower bound (correlation distance): {}'.format(lower_cor))
        print('Lower bound (Euclidean distance): {}'.format(lower_euc))
        
        # convert subject statistics to dataframe
        sub_stats_df = pd.DataFrame(sub_stats)
        
        # save subject statistics
        stats_file = op.join(groupDir, 'sub_stats_{}.csv'.format(roi))
        sub_stats_df.to_csv(stats_file, index=False)
        
        print('Saved subject noise ceiling statistics to: {}'.format(stats_file))
        
        # add mean stats to noise ceiling data
        ceiling_stats.append({'roi': roi,
                              'upper_cor': upper_cor,
                               'upper_euc': upper_euc,
                               'lower_cor': lower_cor,
                               'lower_euc': lower_euc})
    
    # convert noise ceiling stats to dataframe
    ceiling_stats_df = pd.DataFrame(ceiling_stats)
    
    # save ROI summary statistics
    noise_ceiling_file = op.join(groupDir, 'noise_ceilings.csv')
    ceiling_stats_df.to_csv(noise_ceiling_file, index=False)
    
    print('Saved noise ceilings to: {}'.format(noise_ceiling_file))
    
    
# define function to vectorise the RDMs
def vectorise_rdm(rdm_file, diag):
    # load rdm
    rdm_mat = pd.read_csv(rdm_file, sep=',')
    
    # returns the upper triangle as vector
    # k=0 will include diagonal; k=1 will exclude diagonal
    return rdm_mat.values[np.triu_indices_from(rdm_mat, k=diag)]

# define function to calculate Kendall's tau-a
def kendall_tau_a(sub_vec, group_vec):
    
    n = len(sub_vec)
    
    # pairwise differences
    sub_diff = sub_vec[:, None] - sub_vec
    group_diff = group_vec[:, None] - group_vec
    
    # calculate concordance/discordance
    discord = sub_diff * group_diff
    
    # take the upper triangle only (excluding diagonal)
    tri_indx = np.triu_indices(n, k=1)
    
    # extract concordant and discordant values
    C = np.sum(discord[tri_indx] > 0)
    D = np.sum(discord[tri_indx] < 0)
    
    # use values in kendall's tau-a formula
    tau_a = (C - D) / (n * (n - 1) / 2)
    
    return tau_a
    
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
    sharedDir=config_file.loc['sharedDir',1]
    bidsDir=config_file.loc['bidsDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    conditions=config_file.loc['events',1].replace(' ','').split(',')
    mask_opts=config_file.loc['mask',1].replace(' ','').split(',')
    
    # lowercase conditions to avoid case errors - allows flexibility in how users specify events in config and contrasts files
    conditions = [c.lower() for c in conditions]
    
    # print if results directory is not specified or found
    if resultsDir == None:
        raise IOError('No resultsDir was specified in config file, but is required to calculate a noise ceiling!')
    
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
    
    # create a calc_noise_ceiling workflow with the inputs defined above
    calc_noise_ceiling(args.projDir, sharedDir, resultsDir, args.subjects, conditions, mask_opts)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()
    