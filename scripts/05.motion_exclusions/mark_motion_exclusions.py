# import modules
from bids.layout import BIDSLayout
from nipype.algorithms import rapidart
import pandas as pd
import numpy as np
from collections import defaultdict
from nipype import Workflow, Node
import argparse
import os
import os.path as op
import sys
import glob
import shutil

# define function that will tag motion outlier volumes/runs based on defined threshold
def mark_motion_exclusions(sub, derivDir, qcDir, ses, multiecho, fd_thresh, dvars_thresh, art_norm_thresh, art_z_thresh, ntmpts_exclude):
    # print current subject
    print('running motion exclusion script for {}'.format(sub))
    
    # find the BIDS scans file, depending on whether session information is in BIDS directory/file names
    if ses != 'no':
        funcDir = op.join(derivDir, '{}'.format(sub), 'ses-{}'.format(ses), 'func')
        prefix = '{}_ses-{}'.format(sub, ses)
    else: # if session was 'no'
        funcDir = op.join(derivDir, '{}'.format(sub), 'func')
        prefix = '{}'.format(sub)   
    
    # copy fMRIPrep output images to data checking directory for QC
    # for T1_svg in glob.glob('{}/{}/figures/*_desc-reconall_T1w.svg'.format(derivDir, sub)):
        # shutil.copy(T1_svg, qcDir)
    # for MNI_svg in glob.glob('{}/{}/figures/*_space-MNI152NLin2009cAsym*T1w.svg'.format(derivDir, sub)):
        # shutil.copy(MNI_svg, qcDir)
    # for sdc_svg in glob.glob('{}/{}/figures/*_desc-sdc_bold.svg'.format(derivDir, sub)):
        # shutil.copy(sdc_svg, qcDir)
    # for coreg_svg in glob.glob('{}/{}/figures/*_desc-coreg_bold.svg'.format(derivDir, sub)):
        # shutil.copy(coreg_svg, qcDir)
            
    # read the scans.tsv file into a dataframe, then create one useful dataframe
    scansfiles = glob.glob(op.join(funcDir, '*_scans.tsv'))
    scansfile = scansfiles[0]
    df_tsv = pd.read_csv(scansfile, sep='\t')
    
    # extract subject, task, and run information from filenames in scans.tsv file
    df_tsv['subject'] = df_tsv['filename'].str.split('func/', expand=True).loc[:,1]
    df_tsv['subject'] = df_tsv['subject'].str.split('_', expand=True).loc[:,0]
    df_tsv['task'] = df_tsv['filename'].str.split('task-', expand=True).loc[:,1]
    df_tsv['task'] = df_tsv['task'].str.split('_', expand=True)[0]
    df_tsv['run'] = df_tsv['filename'].apply(lambda x: x.split('run-')[1].split('_')[0] if 'run-' in x else None)

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
            
            # if there is no run info specified for this task
            if run == None:
                # name of confound file (has FD/DVARS info)
                confounds_filestr = '*task-' + task + '_desc-confounds*.tsv'
                
                # name of preprocessed bold data
                if multiecho == 'yes':
                    print('Data are multi-echo...')
                    print('Using denoised bold file')
                    preproc_filestr = '*task-' + task + '_space-MNI152NLin2009cAsym_desc-denoised_bold.nii.gz'
                else:
                    print('Data are not multi-echo...')
                    print('Using standard fMRIPrep bold file')
                    preproc_filestr = '*task-' + task + '_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz'
                
                # name of motion parameters file (will be written out in next step)
                mp_filestr = prefix + '_task-' + task + '_mcparams.tsv'
                
                # name of motion parameters file (written out by rapidart)
                art_filestr = '*outliers.txt'
                af = op.join(funcDir, 'art', task, art_filestr)
                
                outname = task # create a different output directory name for each run
                
            # if there's multiple runs specified
            else: 
                # name of confound file (has FD/DVARS info)
                confounds_filestr = '*task-' + task + '_run-' + str(run) + '_desc-confounds*.tsv'
                
                # name of preprocessed bold data
                if multiecho == 'yes':
                    print('Data are multi-echo...')
                    print('Using denoised bold file')
                    preproc_filestr = '*task-' + task + '_run-' + str(run) + '_space-MNI152NLin2009cAsym_desc-denoised_bold.nii.gz'
                else:
                    print('Data are not multi-echo...')
                    print('Using standard fMRIPrep bold file')
                    preproc_filestr = '*task-' + task + '_run-' + str(run) + '_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz'
                    
                # name of motion parameters file (will be written out in next step)
                mp_filestr = prefix + '_task-' + task + '_run-' + str(run) + '_mcparams.tsv'
                
                # name of motion parameters file (written out by rapidart)
                art_filestr = '*outliers.txt'
                af = op.join(funcDir, 'art', task+str(run), art_filestr)
                
                outname = task + str(run) # create a different output directory name for each run

            # read in confound file (has FD/DVARS info)
            cf = glob.glob(op.join(funcDir, confounds_filestr))
            
            # read in preprocessed bold data
            pf = glob.glob(op.join(funcDir, preproc_filestr))
            
            # identify and read in mask data (same across all runs) - the name of this mask file is the same for multiecho data
            mask_filestr = '*_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'
            mf = glob.glob(op.join(funcDir, mask_filestr))

        # check whether data have been preprocessed
        if pf: # if file exists
            confound_file = cf[0]
            preproc_file = pf[0]
            mask_file = mf[0]
            
            print(preproc_file)
            
            # read in confounds file
            dfConfounds = pd.read_csv(confound_file, sep='\t')
            nVols = len(dfConfounds) # record number of volumes to calculate threshold for excluding data
            
            # extract and write realignment parameters in a format for art
            mp_name = op.join(funcDir, mp_filestr)
            pd.read_table(confound_file).to_csv(mp_name, sep='\t',
                                                header = False,
                                                index = False, 
                                                columns=['trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z'])
                
            # read in motion parameters file
            mp = glob.glob(op.join(funcDir, mp_filestr))
            motion_params = mp[0]
            
            # use rapidart to detect outliers in realigned files
            art = Node(rapidart.ArtifactDetect(mask_type = 'file',
                                               mask_file =  mask_file, # specifies a brain mask file (should be an image consisting of 0s and 1s)
                                               realigned_files = preproc_file,
                                               realignment_parameters = [motion_params],
                                               use_norm = True, # use a composite of the motion parameters in order to determine outliers
                                               norm_threshold = art_norm_thresh, # threshold to use to detect motion-related outliers when composite motion is being used
                                               zintensity_threshold = art_z_thresh, # intensity Z-threshold used to detect images that deviate from the mean
                                               parameter_source = 'SPM',
                                               use_differences = [True, False]), # use differences between successive motion (first element) and intensity parameter (second element) estimates in order to determine outliers
                        name=op.join(outname)) # create a different output directory name for each run
            
            # create a rapidart workflow
            wf = Workflow(name = 'art',
                          base_dir = funcDir)
            
            # add node to workflow and run
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
                    
            # extract standarized dvars and calculate TRs over FD and DVARS limits
            FD = dfConfounds.framewise_displacement[1:]
            meanFD = np.mean(FD)
            FDoverlim = FD > fd_thresh
            FDartifacts = FDoverlim.sum()
            
            DVARS = dfConfounds.std_dvars[1:]
            meanDVARS = np.mean(DVARS)
            DVARSoverlim = DVARS > dvars_thresh
            DVARSartifacts = DVARSoverlim.sum()
            
            # add values to dataframe
            df_merge.loc[index, 'MeanFD'] = meanFD
            df_merge.loc[index, '#Artifacts_FD'] = FDartifacts
            df_merge.loc[index, 'MeanDVARS'] = meanDVARS
            df_merge.loc[index, '#Artifacts_DVARS'] = DVARSartifacts
            df_merge.loc[index, '#Artifacts_ART'] = nArt

            # sum of bools is number of true values. count of bool array is length
            # mark run for exclusion if more than specified number of vols are identified as motion using FD, DVARS, or ART timepoints
            # or (DVARSoverlim.sum() / DVARSoverlim.count() >= ntmpts_exclude)
            if (FDoverlim.sum() / FDoverlim.count() >= ntmpts_exclude) or (nArt / nVols >= ntmpts_exclude):
                df_merge.loc[index, 'MotionExclusion'] = True
                print('Motion Exclusion: ' + row['filename'])
        
            print('saving updated scans.tsv file with motion information for {}'.format(sub))
            df_merge.to_csv(scansfile, sep = '\t', 
                            index = False, 
                            columns=['filename', 'task', 'run', 'subject', 'MotionExclusion', 'MeanFD',
                                     '#Artifacts_FD', 'MeanDVARS', '#Artifacts_DVARS', '#Artifacts_ART'])
        
        else: # skip if preprocessed file doesn't exist
            print('No preprocessed data was found for {}'.format(preproc_filestr))
            print('Motion exclusion checking will be skipped for this run')

# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-s', dest='sub',
                        help='subject ID')
    parser.add_argument('-c', dest='config',
                        help='Configuration file')   
    parser.add_argument('-w', dest='workDir', default=os.getcwd(),
                        help='Working directory')                         
    return parser

# define function that checks inputs against parser function
def main(argv=None):
    # call argparser function that defines command line inputs
    parser = argparser()
    args = parser.parse_args(argv)
    
    # read in configuration file and parse inputs
    config_file=pd.read_csv(args.config, sep='\t', header=None, index_col=0)
    derivDir=config_file.loc['derivDir',1]
    ses=config_file.loc['sessions',1]
    multiecho=config_file.loc['multiecho',1]
    fd_thresh=float(config_file.loc['FD_thresh',1])
    dvars_thresh=float(config_file.loc['DVARS_thresh',1])
    art_norm_thresh=float(config_file.loc['art_norm_thresh',1])
    art_z_thresh=int(config_file.loc['art_z_thresh',1])
    ntmpts_exclude=float(config_file.loc['ntmpts_exclude',1])
    
    # print if the derivatives directory is not found
    if not op.exists(derivDir):
        raise IOError('Derivatives directory {} not found.'.format(derivDir))
    
    # make QC directory
    qcDir = op.join(derivDir, 'data_checking', '{}'.format(args.sub))
    # os.makedirs(qcDir, exist_ok=True) # uncommented because reports can be viewed on datastore instead

    # run mark_motion_exclusions function with different inputs depending on config options
    mark_motion_exclusions(args.sub, derivDir, qcDir, ses, multiecho, fd_thresh, dvars_thresh, art_norm_thresh, art_z_thresh, ntmpts_exclude)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()