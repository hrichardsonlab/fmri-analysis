"""
Representational Similarity Analysis (RSA) Script

This script calculates the reliability for neural RDMs estimated in independent run folds

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page

"""
import sys
import pandas as pd
import numpy as np
import argparse
import os.path as op
import os
from itertools import combinations
from itertools import chain

def calc_fold_reliability(projDir, resultsDir, sub, sub_runs, mask_opts, fold_stats):
    
    # define subject RDM directory and check that it exists
    rdmDir = op.join(resultsDir, '{}'.format(sub), 'rsa', 'neural_rdms')
    
    if not op.exists(rdmDir):
        raise IOError('neural RDM directory {} not found.'.format(rdmDir))
    
    # define all possible fold pairs (generally there will just be 2 folds, but this allows for more)
    fold_pairs = list(combinations(sub_runs, 2))
    
    # confirm fold pairs
    print('Will test for reliability between the following fold pairs: {}'.format(fold_pairs))
    
    # loop over ROIs
    for roi in mask_opts:
        
        print('Calculating fold reliability for: {}'.format(roi))
        
        # loop over fold pairs
        for fold1, fold2 in fold_pairs:

            # read in averaged neural RDMs for this ROI
            ## fold 1 vs fold 2
            fold1vs2_cor_file = op.join(rdmDir, '{}_{}_fold-{}vs{}_correlation_rdm.csv'.format(sub, roi, fold1, fold2))
            fold1vs2_euc_file = op.join(rdmDir, '{}_{}_fold-{}vs{}_euclidean_rdm.csv'.format(sub, roi, fold1, fold2))
            
            ## fold 2 vs fold 1
            fold2vs1_cor_file = op.join(rdmDir, '{}_{}_fold-{}vs{}_correlation_rdm.csv'.format(sub, roi, fold2, fold1))
            fold2vs1_euc_file = op.join(rdmDir, '{}_{}_fold-{}vs{}_euclidean_rdm.csv'.format(sub, roi, fold2, fold1))
            
            # check that files are found and give informative error if not
            if not op.exists(fold1vs2_cor_file):
                raise IOError('Fold file not found: {}'.format(fold1vs2_cor_file))
            
            if not op.exists(fold1vs2_euc_file):
                raise IOError('Fold file not found: {}'.format(fold1vs2_euc_file))
            
            if not op.exists(fold2vs1_cor_file):
                raise IOError('Fold file not found: {}'.format(fold2vs1_cor_file))
            
            if not op.exists(fold2vs1_euc_file):
                raise IOError('Fold file not found: {}'.format(fold2vs1_euc_file))                
            
            # vectorise the RDMs (this excludes the diagonal)
            ## correlation
            fold1vs2_cor = vectorise_rdm(fold1vs2_cor_file, diag=1)
            fold2vs1_cor = vectorise_rdm(fold2vs1_cor_file, diag=1)

            ## euclidean
            fold1vs2_euc = vectorise_rdm(fold1vs2_euc_file, diag=1)
            fold2vs1_euc = vectorise_rdm(fold2vs1_euc_file, diag=1)
            
            # tau-a using custom function (should return the same values as tau-b in most cases)
            tau_cor = kendall_tau_a(fold1vs2_cor, fold2vs1_cor)
            tau_euc = kendall_tau_a(fold1vs2_euc, fold2vs1_euc)
            
            print('Reliability for correlation RDMs: {}'.format(tau_cor))
            print('Reliability for euclidean RDMs: {}'.format(tau_euc))
            
            # append to fold stats
            # correlation
            fold_stats.append({'sub': sub,
                               'roi': roi,
                               'folds': '{}'.format(list(chain.from_iterable(fold_pairs))),
                               'metric': 'correlation',
                               'tau_a': tau_cor})
            
            # euclidean
            fold_stats.append({'sub': sub,
                               'roi': roi,
                               'folds': '{}'.format(list(chain.from_iterable(fold_pairs))),
                               'metric': 'euclidean',
                               'tau_a': tau_euc})

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
    
    # print if results directory is not specified or found
    if resultsDir == None:
        raise IOError('No resultsDir was specified in config file, but is required to calculate a noise ceiling!')
    
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
    
    # initialise outputs
    fold_stats = []
        
    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        print('Checking fold reliability for {}'.format(sub))
        
        # check that run info was provided in subject list, otherwise throw an error
        if not args.runs:
            raise IOError('Run or fold information missing. Make sure you are passing a subject-run or subject-fold list to the pipeline!')
            
        # pass runs for this sub
        sub_runs=args.runs[index]
        sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
        sub_runs=list(map(int, sub_runs)) # convert to integers
    
        # create a calc fold workflow with the inputs defined above
        calc_fold_reliability(args.projDir, resultsDir, sub, sub_runs, mask_opts, fold_stats)
    
    # define group rsa directory to save outputs
    groupDir = op.join(resultsDir, 'group_rdms')
    os.makedirs(groupDir, exist_ok=True)
    
    # convert fold stats results to dataframe
    fold_df = pd.DataFrame(fold_stats)
    
    # save results
    fold_df.to_csv(op.join(groupDir, 'fold_reliabilities.csv'), index=False)
    
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()
    