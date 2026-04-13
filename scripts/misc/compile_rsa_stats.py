"""
Compiles stats csv files within a results directory into a single csv file

At the moment, this script will process any *mean* stats (skipping voxelwise stats files) for every
subject in the resultsDir provided in the config file. The output is a single compiled_stats.csv file in the resultsDir.

"""
import os
import os.path as op
import numpy as np
import argparse
import pandas as pd
import glob
import sys

# define compilation function
def compile_stats(projDir, resultsDir):
    
    print('Searching for RSA stats files in {}'.format(resultsDir))

    # define subDirs from folders in directory provided
    subDirs = glob.glob(op.join(resultsDir, 'sub-*'))
    
    # initialize dataframe
    compiled_stats = []
    
    # loop over subjects
    for s, result in enumerate(subDirs):
        # extract subject number
        sub = result.split('sub-')[-1]
        
        print('Compiling RSA stats for sub-{}'.format(sub))

        # find rsa file in subject folder
        rsa_file = op.join(resultsDir, 'sub-{}'.format(sub), 'rsa', 'sub-{}-rsa_results.csv'.format(sub))
        
        if not op.exists(rsa_file):
            print('No RSA file found for sub-{}, skipping...'.format(sub))
            continue
        else:
            # read in csv file
            rsa_dat = pd.read_csv(rsa_file) # header=None
                    
            # merge with compiled stats
            compiled_stats.append(rsa_dat)
    
    # concatenate and sort dataframes
    compiled_df = pd.concat(compiled_stats, ignore_index=True).sort_values(by=['sub', 'roi', 'model', 'metric']).reset_index(drop=True)
    
    # save as csv file in resultsDir
    compiled_file = op.join(resultsDir, 'compiled_rsa_stats.csv')
    compiled_df.to_csv(compiled_file, index=False)

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
    resultsDir=config_file.loc['resultsDir',1]
    
    # pass inputs defined above to main resampling function
    compile_stats(args.projDir, resultsDir)
   
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()