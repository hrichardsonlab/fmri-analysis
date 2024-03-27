# import modules
from bids.layout import BIDSLayout
from nipype.algorithms import rapidart
import pandas as pd
import numpy as np
from collections import defaultdict
from nipype import Workflow, Node
import os
import os.path as op
import sys
import glob

# define function that will tag motion outlier volumes/runs based on defined threshold
def mark_motion_exclusions(sub, derivDir):
    # print current subject
    print('running motion exclusion script for ', sub)
    
    layout = BIDSLayout(derivDir)
    
    # find the BIDS scans file
    scansfiles = glob.glob(op.join(derivDir, sub, 'ses-01', 'func', '*_scans.tsv'))
    scansfile = scansfiles[0]
    
    # read the scans.tsv file into a dataframe, then create one useful dataframe
    df_tsv = pd.read_csv(scansfile, sep='\t')
    
    # extract subject, task, and run information from filenames in scans.tsv file
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
    df_merge.loc[:,'#Artifacts_ART'] = None
    
    # extract motion info from confounds file and merge with dataframe
    for index, row in df_merge.iterrows():
        if  not pd.isnull(row['task']): # if the row has a task listed
            task = row['task']
            run = row['run']
            subject = row['subject']
            
            # if there is only 1 run for this task (no run info specified: sesame data)
            if not run:
                # name of confound file (has FD/DVARS info)
                confounds_filestr = '*task-' + task + '_desc-confounds*.tsv'
                
                # name of preprocessed bold data
                preproc_filestr = '*task-' + task + '_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz'
                
                # name of motion parameters file (will be written out in next step)
                mp_filestr = sub + '_ses-01_task-' + task + '_mcparams.tsv'
                
                # name of motion parameters file (written out by rapidart)
                art_filestr = '*outliers.txt'
                af = op.join(derivDir, sub, 'ses-01', 'func', 'art', task, art_filestr)
                
                outname = task # create a different output directory name for each run
                
            # if there's multiple runs (pixar data)
            else: 
                # name of confound file (has FD/DVARS info)
                confounds_filestr = '*task-' + task + '_run-*' + str(run) + '_desc-confounds*.tsv'
                
                # name of preprocessed bold data
                preproc_filestr = '*task-' + task + '_run-*' + str(run) + '_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz'
                
                # name of motion parameters file (will be written out in next step)
                mp_filestr = sub + '_ses-01_task-' + task + '_run-' + str(run) + '_mcparams.tsv'
                
                # name of motion parameters file (written out by rapidart)
                art_filestr = '*outliers.txt'
                af = op.join(derivDir, sub, 'ses-01', 'func', 'art', task+str(run), art_filestr)
                
                outname = task + str(run) # create a different output directory name for each run

            # read in confound file (has FD/DVARS info)
            cf = glob.glob(op.join(derivDir, sub, 'ses-01', 'func', confounds_filestr))
            confound_file = cf[0]
            
            # read in preprocessed bold data
            pf = glob.glob(op.join(derivDir, sub, 'ses-01', 'func', preproc_filestr))
            preproc_file = pf[0]
            
            # identify and read in mask data (same across all runs)
            mask_filestr = '*_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'
            mf = glob.glob(op.join(derivDir, sub, 'ses-01', 'func', mask_filestr))
            mask_file = mf[0]
            

        # read in confounds file
        dfConfounds = pd.read_csv(confound_file, sep='\t')
        nVols = len(dfConfounds) # record number of volumes to calculate threshold for excluding data
        
        # extract and write realignment parameters in a format for art
        mp_name = op.join(derivDir, sub, 'ses-01', 'func', mp_filestr)
        pd.read_table(confound_file).to_csv(mp_name, sep='\t',
                                           header = False,
                                           index = False, 
                                           columns=['trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z'])
            
        # read in motion parameters file
        mp = glob.glob(op.join(derivDir, sub, 'ses-01', 'func', mp_filestr))
        motion_params = mp[0]
        
        # use rapidart to detect outliers in realigned files
        art = Node(rapidart.ArtifactDetect(mask_type = 'file',
                                           mask_file =  mask_file, # specifies a brain mask file (should be an image consisting of 0s and 1s)
                                           realigned_files = preproc_file,
                                           realignment_parameters = motion_params,
                                           use_norm = True, # use a composite of the motion parameters in order to determine outliers
                                           norm_threshold = 1, # threshold to use to detect motion-related outliers when composite motion is being used
                                           zintensity_threshold = 3, # intensity Z-threshold used to detect images that deviate from the mean
                                           parameter_source = 'SPM',
                                           use_differences = [True, False]), # use differences between successive motion (first element) and intensity parameter (second element) estimates in order to determine outliers
                    name=op.join(outname)) # create a different output directory name for each run
        
        # define path to subj directory
        subDir = op.join(derivDir, sub, 'ses-01', 'func')
        
        # create a rapidart workflow
        wf = Workflow(name = 'art',
                      base_dir = subDir)
        
        # add node to workflow
        wf.add_nodes([art])
                          
        wf.run()
        
        # read in art output to count number of artefact timepoints
        art_file = glob.glob(af)[0]
        
        if op.getsize(art_file) == 0: # if no timepoints tagged as artifact
            nArt=0
        else:
            nArt=len(pd.read_csv(art_file, header=None))
        
        # print number of artifact timepoints
        print('identified ' + str(nArt) + ' artifacts saved in ' + art_file)
        
        # extract standarized dvars and calculate TRs over 1.5 DVARS limit
        DVARS = dfConfounds.std_dvars[1:]
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
        df_merge.loc[index, '#Artifacts_ART'] = nArt

        # sum of bools is number of true values. count of bool array is length
        # mark run for exclusion if more than 1/3rd of vols are identified as motion using FD, DVARS, or ART timepoints
        if (FDoverlim.sum() / FDoverlim.count() >= 0.33) or (DVARSoverlim.sum() / DVARSoverlim.count() >= 0.33) or (nArt / nVols >= 0.33):
            df_merge.loc[index, 'MotionExclusion'] = True
            print('Motion Exclusion: ' + row['filename'])
    
    print('saving updated scans.tsv file with motion information for ' + sub)
    df_merge.to_csv(scansfile, sep = '\t', 
                    index = False, 
                    columns=['filename', 'task', 'run', 'subject', 'MotionExclusion', 'MeanFD',
                             '#Artifacts_FD', 'MeanDVARS', '#Artifacts_DVARS', '#Artifacts_ART'])

# define function which takes information from singularity call, prints it to terminal, and then runs the function defined above
def main():
    sub = sys.argv[1] # first argument passed to script (in singularity call)
    derivDir = sys.argv[2] # second argument passed to script (derivatives folder)
    mark_motion_exclusions(sub, derivDir)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()