"""
Get information about each functional run

This script will output a csv file with the run information (i.e., number of volumes) for the subject specified.
This is useful for identifying runs that were converted (contained more than 2/3rds of the volumes per run), but are incomplete.

"""
import nilearn
from nibabel import load
import os
import os.path as op
import numpy as np
import argparse
import pandas as pd
import glob
import shutil
import re

# define run volumes function
def run_volumes(bidsDir, qcDir, ses):

    # define subDirs from folders in directory provided
    subDirs = glob.glob(op.join(bidsDir, 'sub-*'))
    
    # sort subDirs
    subDirs = sorted(subDirs, key=lambda x: int(re.search(r'(\d+)$', x).group()))

    # delete run_info.tsv file if it already exists
    run_info_file = op.join(qcDir, 'run_info.tsv')
    if os.path.exists(run_info_file):
        os.remove(run_info_file)
        
    # initialize dataframe and list of rows
    run_info = pd.DataFrame(columns=['sub', 'filename', 'nVols'])
    row_list = []
    
    # loop over subjects
    for s, subDir in enumerate(subDirs):
        sub = subDir.split('/')[-1]
        
        # define subject func directory depending on whether data are organized in session folders
        if ses != 'no':
            funcDir = op.join(subDir, 'ses-{}'.format(ses), 'func')
            prefix = '{}_ses-{}'.format(sub, ses)
            
        else: # if session was 'no'
            funcDir = op.join(subDir, 'func')
            prefix = '{}'.format(sub)   
    
        # check whether subject has functional data
        if os.path.isdir(funcDir):
            print('Checking functional data found for {}'.format(sub))
            
            files = glob.glob(op.join(funcDir, '*bold.nii*'))
            
            for f, func in enumerate(files):
                # get filename
                filename = os.path.basename(func)
            
                # get number of volumes in functional run
                nVols = (load(func).shape[3])
                
                # add row to list
                row_list.append({'sub': sub, 'filename': filename, 'nVols': nVols})

        else:
            print('No functional data found for {}'.format(sub))
        
        # concatenate all rows into the dataframe
        run_info = pd.concat([run_info, pd.DataFrame(row_list)], ignore_index=True)

        # save as file in qcDir
        run_info.to_csv(run_info_file, index=False, sep ='\t')
        
# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-p', dest='projDir',
                        help='Project directory')
    parser.add_argument('-c', dest='config',
                        help='Configuration file')                                            
    return parser

# define main function that parses the config file and runs the functions defined above
def main(argv=None):
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
    bidsDir=config_file.loc['bidsDir',1]
    ses=config_file.loc['sessions',1]
    
    # print if the derivatives directory is not found
    if not op.exists(bidsDir):
        raise IOError('BIDS directory {} not found.'.format(bidsDir))
    
    # make QC directory
    qcDir = op.join(args.projDir, 'analysis')
    os.makedirs(qcDir, exist_ok=True)

    # pass inputs defined above to main get run info function
    run_volumes(bidsDir, qcDir, ses)
   
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()
