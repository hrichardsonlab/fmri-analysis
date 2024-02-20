# import modules
from bids.layout import BIDSLayout
import bids.variables.kollekshuns
import pandas as pd
from shutil import copyfile
import numpy as np
from collections import defaultdict
import os.path as op
import sys
import glob
import os

# define function that will tag motion outlier volumes/runs based on defined threshold
def mark_motion_exclusions(sub, derivDir):
    
    layout = BIDSLayout(derivDir)
    
    # find the BIDS scans file and make a backup before we start mucking with it
    # scansfiles = glob.glob(op.join(derivDir, '*' + sub, '*_scans.tsv'))
    scansfiles = glob.glob(op.join(derivDir, sub, sub, 'ses-01', 'func', '*_scans.tsv'))
    scansfile = scansfiles[0]

    # copy original scansfiles to a hidden directory in data/ instead of in BIDS
    # (.orig files are not BIDS compatible)
    scansfile_base = op.basename(scansfile)
    copy_orig_dir = op.join(derivDir, 'data/.scansfiles_orig')
    if not op.exists(copy_orig_dir):
        os.makedirs(copy_orig_dir)
    copy_orig_scansfile_path = op.join(copy_orig_dir, scansfile_base)
    if ~op.isfile(copy_orig_scansfile_path + '.orig'):
        copyfile(scansfile, copy_orig_scansfile_path + '.orig')
               
    # read the TSV file into a dataframe, then create one useful dataframe
    df_tsv = pd.read_csv(scansfile, sep='\t')
   
    df_tsv['task'] = df_tsv['filename'].str.split('task-', expand=True).loc[:,1]
    df_tsv['task'] = df_tsv['task'].str.split('_run', expand=True).loc[:,0]
    df_tsv['task'] = df_tsv['task'].str.split('_bold', expand=True).loc[:,0]
    df_tsv['run'] = df_tsv['filename'].str.split('run-', expand=True).loc[:,1]
    df_tsv['run'] = df_tsv['run'].str.split('_bold', expand=True).loc[:,0]
    df_tsv['subject'] = df_tsv['filename'].str.split('func/', expand=True).loc[:,1]
    df_tsv['subject'] = df_tsv['subject'].str.split('_ses', expand=True).loc[:,0]
    
    # dataframe with motion information columns that will be populated with info from confounds file
    df_merge = df_tsv
    df_merge.loc[:,'MotionExclusion'] = False
    df_merge.loc[:,'MeanFD'] = None
    df_merge.loc[:,'#Artifacts_FD'] = None
    df_merge.loc[:,'MeanDVARS'] = None
    df_merge.loc[:,'#Artifacts_DVARS'] = None
    df_merge.loc[:,'OtherExclusion'] = False
    df_merge.loc[:,'OtherExclusionReason'] = None
    
    # extract motion info from confounds file and merge with dataframe
    for index, row in df_merge.iterrows():
        if  not pd.isnull(row['run']):
            task = row['task']
            run = row['run']
            subject = row['subject']
            filestr = '*task-' + task + '_run-*' + str(run) + '_desc-confounds*.tsv'
            f = glob.glob(op.join(derivDir, sub, sub, 'ses-01', 'func', filestr))
            confound_file = f[0]

        # read in confounds file
        dfConfounds = pd.read_csv(confound_file, sep='\t')

        # extract standarized dvars and calculate TRs over 1.5 DVARS limit
        DVARS=dfConfounds.std_dvars[1:]
        meanDVARS = np.mean(DVARS)
        DVARSoverlim = DVARS > 1.5
        DVARSartifacts = DVARSoverlim.sum()
        
        # extract FD and calculate TRs over 1 FD limit
        FD = dfConfounds.framewise_displacement[1:]
        meanFD = np.mean(FD)
        FDoverlim = FD > 1
        FDartifacts = FDoverlim.sum()
        
        # add values to dataframe
        df_merge.loc[index, 'MeanFD'] = meanFD
        df_merge.loc[index, '#Artifacts_FD'] = FDartifacts
        df_merge.loc[index, 'MeanDVARS'] = meanDVARS
        df_merge.loc[index, '#Artifacts_DVARS'] = DVARSartifacts

        # sum of bools is number of true values. count of bool array is length
        # mark run for exclusion if more than 1/3rd of vols are identified as motion
        if (FDoverlim.sum() / FDoverlim.count() >= 0.33) or (DVARSoverlim.sum() / DVARSoverlim.count() >= 0.33):
            df_merge.loc[index, 'MotionExclusion'] = True
            print('Motion Exclusion: ' + row['filename'])
    
    print('saving updated scans.tsv file with motion information for ' + sub)
    df_merge.to_csv(scansfile, sep = '\t', 
                    index = False, 
                    columns=['filename', 'task', 'run', 'subject', 'MotionExclusion', 'MeanFD',
                             '#Artifacts_FD', 'MeanDVARS', '#Artifacts_DVARS', 'OtherExclusion', 'OtherExclusionReason'])

# define function which takes information from singularity call, prints it to terminal, and then runs the function defined above
def main():
    sub = sys.argv[1] # first argument passed to script (in singularity call)
    derivDir = sys.argv[2] # second argument passed to script (derivatives folder)
    print('Marking motion exclusions in scans.tsv file for ' + sub + ' in derivatives folder: ' + derivDir)
    mark_motion_exclusions(sub, derivDir)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()