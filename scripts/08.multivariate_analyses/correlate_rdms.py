"""
Representational Similarity Analysis (RSA) Script

This script compares the neural and theoretical/model representational dissimilarity matrices (RDMs) for a set of ROIs. 

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page

"""
import sys
import pandas as pd
import numpy as np
import argparse
import scipy.stats
import os.path as op
import os
import glob
import shutil

def correlate_rdms(projDir, sharedDir, dataset, resultsDir, sub, conditions, mask_opts, subject_rdms, model_rdms):
    
    # define rsa directory and check that it exists
    rsaDir = op.join(resultsDir, '{}'.format(sub), 'rsa')
    rdmDir = op.join(rsaDir, 'neural_rdms')
    
    if not op.exists(rdmDir):
        raise IOError('neural RDM directory {} not found.'.format(rdmDir))
    
    # load model RDMs, depending on whether subject or group RDMs were specified
    model_files = list()
    if subject_rdms == 'yes':
        print('Will use subject specific model RDMs')
        
        # loop over models provided in config file
        for m in model_rdms:
            # look for model file in project directory
            model_file = glob.glob(op.join(projDir, 'files', 'model_rdms', '{}*RDM-{}.csv'.format(sub, m)))[0]
            
            # if model file not found in project directory, look for it in the shared directory
            if not model_file:
                model_file = glob.glob(op.join(sharedDir, 'processing', 'model_rdms', '{}'.format(dataset), '{}*RDM-{}.csv'.format(sub, m)))[0]
            
            print('Using {} model RDM file from: {}'.format(m, model_file))
            
            model_files.append(model_file)
    else:
        print('Will use the same group model RDMs for all subjects')
        
        # loop over models provided in config file
        for m in model_rdms:
            # look for model file in project directory
            model_file = glob.glob(op.join(projDir, 'files', 'model_rdms', '*RDM-{}.csv'.format(m)))[0]
            
            # if model file not found in project directory, look for it in the shared directory
            if not model_file:
                model_file = glob.glob(op.join(sharedDir, 'processing', 'model_rdms', '{}'.format(dataset), '*RDM-{}.csv'.format(m)))[0]
            
            print('Using {} model RDM file from: {}'.format(m, model_file))
            
            model_files.append(model_file)
            
    # vectorise model files
    models = {}
    for index, m in enumerate(model_files):
        
        # read in model data
        rdm = pd.read_csv(m, index_col=0)
        
        # force the model RDM to be symmetric (this might already be true)
        rdm = rdm.loc[rdm.index, rdm.index]
        
        # vectorise and store column and run order
        models[m] = {'model': model_rdms[index],
                     'vector': vectorise_rdm(rdm),
                     'column_order': rdm.columns.tolist(),
                     'row_order': rdm.index.tolist()}
    
    # initalise output
    results = []
    
    # loop over ROIs 
    for roi in mask_opts:
        # read in averaged neural RDMs for this ROI
        correl_rdm_file = op.join(rdmDir, '{}_{}_correlation_averaged_rdm.csv'.format(sub, roi))
        euclid_rdm_file = op.join(rdmDir, '{}_{}_euclidean_averaged_rdm.csv'.format(sub, roi))
        correl_rdm = pd.read_csv(correl_rdm_file, sep=',')
        euclid_rdm = pd.read_csv(euclid_rdm_file, sep=',')
        
        # add row names to ensure the same order as model RDMs
        correl_rdm.index = correl_rdm.columns
        euclid_rdm.index = euclid_rdm.columns
                
        # loop over models      
        for m in models:
            # force neural RDMs to have the same column and row order as the model (which has been forced to be symmetric)
            order = models[m]['row_order']
            correl_aligned = correl_rdm.loc[order, order]
            euclid_aligned = euclid_rdm.loc[order, order]
            
            # vectorise neural RDMs
            correl_vec = vectorise_rdm(correl_aligned)
            euclid_vec = vectorise_rdm(euclid_aligned)
            
            # extract model vector
            model_vec = models[m]['vector']
            
            # Kendall's tau
            # the scipy stats function defaults to tau-b and does not have a tau-a implementation
            tau_b_correl, p_correl = scipy.stats.kendalltau(correl_vec, model_vec)
            tau_b_euclid, p_euclid = scipy.stats.kendalltau(euclid_vec, model_vec)
            
            # tau-a using custom function (should return the same values as tau-b in most cases)
            tau_a_correl = kendall_tau_a(correl_vec, model_vec)
            tau_a_euclid = kendall_tau_a(euclid_vec, model_vec)
            
            # save correlation results
            results.append({'sub': sub,
                            'roi': roi,
                            'model': models[m]['model'],
                            'metric': 'correlation',
                            'tau_a': tau_a_correl,
                            'tau_b': tau_b_correl})
        
            # save euclidean results
            results.append({'sub': sub,
                            'roi': roi,
                            'model': models[m]['model'],
                            'metric': 'euclidean',
                            'tau_a': tau_a_euclid,
                            'tau_b': tau_b_euclid})

    # save outputs
    results_df = pd.DataFrame(results)
    results_file = op.join(rsaDir, '{}-rsa_results.csv'.format(sub))
    results_df.to_csv(results_file, index=False)
    print('Saved RSA results to: {}'.format(results_file))
    
# define function to vectorise the RDMs
def vectorise_rdm(dat):
    # returns the upper triangle (excluding diagonal) as vector
    # k=0  will include diagonal
    return dat.values[np.triu_indices_from(dat, k=1)]

# define function to calculate Kendall's tau-a
def kendall_tau_a(neural_vec, model_vec):
    n = len(neural_vec)
    
    # pairwise differences
    neural_diff = neural_vec[:, None] - neural_vec
    model_diff = model_vec[:, None] - model_vec
    
    # calculate concordance/discordance
    discord = neural_diff * model_diff
    
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
    subject_rdms=config_file.loc['subject_rdms',1]
    model_rdms=config_file.loc['model_rdms',1].replace(' ','').split(',')
    
    # extract dataset name from the bidsDir provided in the config file
    dataset = os.path.basename(bidsDir)
    
    # lowercase conditions to avoid case errors - allows flexibility in how users specify events in config and contrasts files
    conditions = [c.lower() for c in conditions]
    
    # print if results directory is not specified or found
    if resultsDir == None:
        raise IOError('No resultsDir was specified in config file, but is required to correlate RDMs!')
    
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
        
    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        print('Correlating neural and model RDMs for {}'.format(sub))
        
        # create a process_subject workflow with the inputs defined above
        correlate_rdms(args.projDir, sharedDir, dataset, resultsDir, sub, conditions, mask_opts, subject_rdms, model_rdms)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()
    