"""
Compiles timecourse csv files within a results directory into a single csv file

At the moment, this script will process any *mean* timecourses (skipping voxelwise timecourse files) for every
subject in the resultsDir provided in the config file. The output is a single compiled_timecourses.csv file in the resultsDir.

"""
import os
import os.path as op
import numpy as np
import argparse
import pandas as pd
import glob

# define first level workflow function
def compile_timecourses(projDir, resultsDir):
    
    print('Searching for timecourse files in {}'.format(resultsDir))

    # define subDirs from folders in directory provided
    subDirs = glob.glob(op.join(resultsDir, 'sub-*'))
    
    # initialize dataframe
    compiled_tc = pd.DataFrame(columns=['time'])
    
    # loop over subjects
    for s, result in enumerate(subDirs):
        # extract subject number
        sub = result.split('sub-')[-1]
        
        print('Compiling timecourses for sub-{}'.format(sub))

        # define timecourse files in subject folder
        tc_files = glob.glob(op.join(result, 'timecourses', '*.csv'))
        
        # extract timecourse from each file in directory
        for t, timecourse in enumerate(tc_files):
            if 'mean' in timecourse: 
                # extract file name from path
                tc_name = timecourse.replace('whole_brain', 'wholebrain').split('sub-')[-1]
                tc_name = tc_name.split('_mean_timecourse.csv')[0]
                tc_name = tc_name.split('_')

                # extract ROI, run, and splithalf info from file name
                if len(tc_name) == 4: # if splithalf
                    roi_name = tc_name[3]
                    split = tc_name[2]
                    run = tc_name[1]
                elif len(tc_name) == 3:# if runs but no splithalf
                    roi_name = tc_name[2]
                    run = tc_name[1]
                    split = 'no'
                else: # if no runs or splithalf
                    roi_name = tc_name[-1]
                    run = 'no'
                    split = 'no'

                # read in csv file
                tc_dat = pd.read_csv(timecourse, header=None)

                if split != 'no':
                    tc_dat.insert(loc=0, column='half', value=split)
                tc_dat.insert(loc=0, column='ROI', value=roi_name)
                if run != 'no':
                    tc_dat.insert(loc=0, column='run', value=run)
                tc_dat.insert(loc=0, column='sub', value='sub-{}'.format(sub))
                tc_dat.insert(loc=0, column='time', value=range(len(tc_dat)))

                # merge with compiled timecourses
                compiled_tc = compiled_tc.merge(tc_dat, 'outer')

            else:
                print('WARNING: the extracted timecourses are voxelwise instead of mean timecourses, skipping files!')

    # pivot data so ROIs are separated into columns, convert to dataframe, and sort data
    if split != 'no':
        compiled_tc = compiled_tc.pivot_table(index=['time', 'sub', 'run', 'half'], columns='ROI', values=0, dropna=False)
        compiled_tc = pd.DataFrame(compiled_tc.to_records()).sort_values(by=['sub', 'run', 'half', 'time'])
    elif run != 'no':
        compiled_tc = compiled_tc.pivot_table(index=['time', 'sub', 'run'], columns='ROI', values=0, dropna=False)
        compiled_tc = pd.DataFrame(compiled_tc.to_records()).sort_values(by=['sub', 'run', 'time'])
    else:
        compiled_tc = compiled_tc.pivot_table(index=['time', 'sub'], columns='ROI', values=0, dropna=False)
        compiled_tc = pd.DataFrame(compiled_tc.to_records()).sort_values(by=['sub', 'time'])

    # save as csv file in resultsDir
    timecourse_file = op.join(resultsDir, 'compiled_timecourses.csv')
    compiled_tc.to_csv(timecourse_file, index=False)

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
    compile_timecourses(args.projDir, resultsDir)
   
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()