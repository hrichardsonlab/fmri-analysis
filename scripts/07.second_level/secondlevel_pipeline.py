"""
Group level analysis using FSL's FLAME or RANDOMISE

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page

"""
from nipype.interfaces import fsl
from nipype import Workflow, Node, IdentityInterface, Function, DataSink, JoinNode, MapNode
import scipy.stats
import argparse
import os
import os.path as op
import numpy as np
import pandas as pd
import glob
import shutil
from datetime import datetime
import subprocess

# define first level workflow function
def generate_model_files(projDir, derivDir, resultsDir, outDir, workDir, subs, runs, sub_df, task, ses, splithalf_id, contrast_id, nonparametric, group_opts, group_vars, est_group_variances, tfce, nperm):

    # merge cope and varcope files for specified participants and contrast
    copes_list = []
    varcopes_list = []
    mask_list = []
    for s, sub in enumerate(subs):
        print('Concatenating copes and varcopes files for {} analysis for {}'.format(contrast_id, sub))

        # grab mask file
        if ses != 'no': # if session was provided
            mask_file = glob.glob(op.join(derivDir, 'sub-{}'.format(sub), 'ses-{}'.format(ses), 'func', '{}_ses-{}_space-MNI152NLin2009cAsym*_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub, ses)))[0]
        else: # if session was 'no'
            mask_file = glob.glob(op.join(derivDir, 'sub-{}'.format(sub), 'func', 'sub-{}_space-MNI152NLin2009cAsym*_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub)))[0]
        
        if runs[s] != 'NA' or len(runs[s]) > 3: # if more than 1 run (tested by checking length of characters: greater than 2, e.g., NA or 1,)
            # pull outputs from combinedDir
            modelDir = op.join(resultsDir, 'sub-{}'.format(sub), 'model', 'combined_runs')
            
            # check that runs have been combined
            if not op.exists(modelDir):
                raise IOError('Combined run directory not found for sub-{}. Have runs been combined?'.format(sub))

            # grab files
            if splithalf_id != 0:
                cope_file = glob.glob(op.join(modelDir, 'splithalf{}'.format(splithalf_id), 'con_*_{}_cope.nii.gz'.format(contrast_id)))
                varcope_file = glob.glob(op.join(modelDir, 'splithalf{}'.format(splithalf_id), 'con_*_{}_varcope.nii.gz'.format(contrast_id)))
            else:
                cope_file = glob.glob(op.join(modelDir, 'con_*_{}_cope.nii.gz'.format(contrast_id)))
                varcope_file = glob.glob(op.join(modelDir, 'con_*_{}_varcope.nii.gz'.format(contrast_id)))
                            
        else: # if only 1 run
            # pull outputs from run directory
            modelDir = op.join(resultsDir, 'sub-{}'.format(sub), 'model')
            
            # ensure that correct run name is used to grab files
            if runs[s] == 'NA': # if no run info, then look for outputs in run1
                sub_run = 1
            else:
                sub_run = runs[s]

            # grab files
            if splithalf_id != 0:
                cope_file = glob.glob(op.join(modelDir, 'run{}_splithalf{}'.format(sub_run, splithalf_id), 'con_*_{}_cope.nii.gz'.format(contrast_id)))
                varcope_file = glob.glob(op.join(modelDir, 'run{}_splithalf{}'.format(sub_run, splithalf_id), 'con_*_{}_varcope.nii.gz'.format(contrast_id)))
            else:
                cope_file = glob.glob(op.join(modelDir, 'run{}'.format(sub_run),'con_*_{}_cope.nii.gz'.format(contrast_id)))
                varcope_file = glob.glob(op.join(modelDir, 'run{}'.format(sub_run),'con_*_{}_varcope.nii.gz'.format(contrast_id)))
        
        print(cope_file)
        print(varcope_file)
        if not op.isfile(cope_file[0]):
            print(cope_file, 'is missing!')
        else:
            copes_list.append(cope_file)
            varcopes_list.append(varcope_file)
            mask_list.append(mask_file)          
    
    # define output directory for this contrast depending on config options
    if nonparametric == 'yes':
        prefix = 'randomise'
    else:
        prefix = 'flame'

    if splithalf_id != 0:
        conDir = op.join(outDir, '{}_{}_{}_splithalf{}'.format(prefix, task, contrast_id, splithalf_id))
    else:
        conDir = op.join(outDir, '{}_{}_{}'.format(prefix, task, contrast_id))
    
    # make output directory for this contrast
    os.makedirs(conDir, exist_ok = True)
    
    # name of merged cope and varcope files
    merged_cope_file = op.join(conDir, 'all_copes.nii.gz')
    merged_varcope_file = op.join(conDir, 'all_varcopes.nii.gz')
    merged_mask_file = op.join(outDir, 'merged_mask.nii.gz')
    dilated_mask_file = op.join(outDir, 'dilated_mask.nii.gz')
    
    # unnest lists
    copes_list = [c for sublist in copes_list for c in sublist]
    varcopes_list = [v for sublist in varcopes_list for v in sublist]
    #mask_list = [m for sublist in mask_list for m in sublist] # needed if masks are read in as lists
    
    # concatenate copes images
    cmd = 'fslmerge -t ' + merged_cope_file + ' ' 
    cmd = cmd + ' '.join(copes_list)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, shell = True)
    print('Merged all copes')

    # concatenate varcopes images
    cmd = 'fslmerge -t ' + merged_varcope_file + ' ' 
    cmd = cmd + ' '.join(varcopes_list)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, shell = True)
    print('Merged all varcopes')
    
    # if averaged mask file doesn't already exist in output directory
    if not op.exists(dilated_mask_file):
        # first concatenate mask images
        cmd = 'fslmerge -t ' + merged_mask_file + ' ' 
        cmd = cmd + ' '.join(mask_list)
        #print(cmd)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, shell = True)
        print('Merged all masks') # , result.stdout
        
        # then dilate the mask
        cmd = 'fslmaths ' + merged_mask_file + ' '
        cmd = cmd + '-dilM -bin ' + dilated_mask_file
        #print(cmd)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, shell = True)
        print('Dilated mask')
        
    # generate design file needed for models
    if group_opts == 'between':
        print('Creating design matrix file for between group analysis')
        
        # set one sample flag to false
        one_sample = False
        
        # list all unique groups
        groups = sorted(set(sub_df.group))
        
        # for each group, create a column indexing group assignment
        for g, grp in enumerate(groups):
            sub_df[grp] = np.where(sub_df['group'] == grp , '1', '0')
            sub_df['group'].mask(sub_df['group'] == grp, g+1, inplace=True)
        
        if est_group_variances == 'no':
            sub_df['group'] = 1 # overwrite the separate group assigments to estimate variance across all groups
            
        # put group columns first (will be in alphabetical order)
        sub_df = sub_df.loc[:, list(groups) + np.sort(sub_df.columns.difference(groups)).tolist()]
             
    else:
        print('Creating design matrix file for within group analysis')
        
        # set one sample flag to true
        one_sample = True
        
        # list group
        groups = sorted(set(sub_df.group))
        
        # assign all subs to same group
        sub_df['group'] = 1
    
    # extract and save group column
    grp_txt = op.join(conDir, '{}_grp.txt'.format(contrast_id))
    grp_cov = op.join(conDir, '{}_grp.grp'.format(contrast_id))
    sub_df['group'].to_csv(grp_txt, header=None, index=None, sep=' ', mode='a')
    
    # drop colums that aren't needed in design matrix
    sub_df = sub_df.drop(['sub', 'group'], axis=1)
    
    # lowercase column names
    sub_df.columns = sub_df.columns.str.lower()
        
    # define output files and save text file
    design_txt = op.join(conDir, '{}_design.txt'.format(contrast_id))
    design_mat = op.join(conDir, '{}_design.mat'.format(contrast_id))
    sub_df.to_csv(design_txt, header=None, index=None, sep=' ', mode='a')
    
    # convert design.txt to design.mat
    print('Converting design matrix to mat file format for FSL')
    cmd = 'Text2Vest ' + design_txt + ' '
    cmd = cmd + design_mat
    result = subprocess.run(cmd, stdout=subprocess.PIPE, shell = True)
    
    # convert grp.txt to .grp file
    print('Converting group file to format for FSL')
    cmd = 'Text2Vest ' + grp_txt + ' '
    cmd = cmd + grp_cov
    result = subprocess.run(cmd, stdout=subprocess.PIPE, shell = True)

    # generate contrast file needed for models
    print('Creating group contrast file for analysis')
    contrasts_file=op.join(projDir, 'files', 'contrast_files', 'group_contrasts.tsv')
    contrasts=pd.read_csv(contrasts_file, sep='\t')
    
    # lowercase column names
    contrasts.columns=contrasts.columns.str.lower()
    
    # remove contrasts based on contrast column (either all or a specific contrast is specified)
    contrasts = contrasts[(contrasts.contrast == 'all') | (contrasts.contrast == contrast_id)].drop('contrast', axis=1)
    
    # filter contrasts
    if sub_df.shape[1] != 0:
        retain_vars = set(groups + sub_df)
    else:
        retain_vars = groups
    
    retain_vars = [var.lower() for var in retain_vars]
    contrasts = contrasts.loc[:, contrasts.columns.isin(retain_vars)]
    
    print(contrasts)
    
    # define output files and save text file
    contrast_txt = op.join(conDir, '{}_contrasts.txt'.format(contrast_id))
    design_con = op.join(conDir, '{}_design.con'.format(contrast_id))
    contrasts.to_csv(contrast_txt, header=None, index=None, sep=' ', mode='a')
    
    # convert contrasts.txt to contrasts.mat
    print('Converting contrast matrix to con file format for FSL')
    cmd = 'Text2Vest ' + contrast_txt + ' '
    cmd = cmd + design_con
    result = subprocess.run(cmd, stdout=subprocess.PIPE, shell = True)
    
    # submit generated files to model function
    run_model(conDir, nonparametric, tfce, nperm, one_sample, merged_cope_file, merged_varcope_file, design_mat, grp_cov, design_con, dilated_mask_file)

# define function to run model
def run_model(conDir, nonparametric, tfce, nperm, one_sample, merged_cope_file, merged_varcope_file, design_mat, grp_cov, design_con, dilated_mask_file):
    # move to contrasts directory so output files are saved correctly
    os.chdir(conDir)
    
    if nonparametric == 'no':
        print('Running parametric group analysis using FLAME')
        
        # set up flameo call
        flameo = fsl.FLAMEO(cope_file=merged_cope_file, 
                            var_cope_file=merged_varcope_file,
                            design_file=design_mat,
                            cov_split_file=grp_cov,
                            t_con_file=design_con,
                            mask_file=dilated_mask_file,
                            run_mode='flame1')
        flameo.run()
    
    else:
        print('Running nonparametric group analysis using RANDOMISE')
        print('Will run {} permutations'.format(nperm))
        
        # apply TFCE if specified in config file, otherwise do voxelwise correction
        if tfce == 'yes':
            print('Using Threshold-Free Cluster Enhancement')
            # set up randomise call
            rand = fsl.Randomise(in_file=merged_cope_file, 
                                 demean=True, # demean the EVs in the design matrix, providing a warning if they initially had non-zero mean
                                 num_perm=nperm,
                                 mask=dilated_mask_file, 
                                 tcon=design_con,
                                 one_sample_group_mean=one_sample,
                                 design_mat=design_mat,
                                 tfce=True)
        
        else:
            # set up randomise call
            rand = fsl.Randomise(in_file=merged_cope_file, 
                                 demean=True, # demean the EVs in the design matrix, providing a warning if they initially had non-zero mean
                                 num_perm=nperm,
                                 mask=dilated_mask_file, 
                                 tcon=design_con, 
                                 one_sample_group_mean=one_sample,
                                 design_mat=design_mat,
                                 #c_threshold=2.96,# carry out cluster-based thresholding (requires T threshold)
                                 vox_p_values=True) # output voxelwise (corrected and uncorrected) p-value image

        rand.run()

# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-p', dest='projDir',
                        help='Project directory')
    parser.add_argument('-s', dest='subjects', nargs='*',
                        help='Subjects to process')
    parser.add_argument('-f', dest='file', nargs='*',
                        help='Subject file to process')  
    parser.add_argument('-r', dest='runs', nargs='*',
                        help='List of runs for each subject')                         
    parser.add_argument('-c', dest='config',
                        help='Configuration file')                                            
    parser.add_argument('-m', dest='plugin',
                        help='Nipype plugin to use (default: MultiProc)')
    return parser

# define main function that parses the config file and runs the functions defined above
def main(argv=None):
    import pandas as pd

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
    derivDir=config_file.loc['derivDir',1]
    task=config_file.loc['task',1]
    ses=config_file.loc['sessions',1]
    contrast_opts=config_file.loc['contrast',1].replace(' ','').split(',')
    splithalf=config_file.loc['splithalf',1]
    nonparametric=config_file.loc['nonparametric',1]
    group_opts=config_file.loc['group_comparison',1]
    group_vars=config_file.loc['group_variables',1].replace(' ','').split(',')
    est_group_variances=config_file.loc['est_group_variances',1]
    tfce=config_file.loc['tfce',1]
    nperm=int(config_file.loc['npermutations',1])
    overwrite=config_file.loc['overwrite',1]
    
    # print if the fMRIPrep directory is not found
    if not op.exists(derivDir):
        raise IOError('Derivatives directory {} not found.'.format(derivDir))
        
    # print if the project directory is not found
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
    
    # lowercase contrast_opts and group_vars to avoid case errors
    contrast_opts = [c.lower() for c in contrast_opts]
    
    # create new group_vars list if no variables were specified in config file
    if group_vars == ['no']:
        group_vars = []
    else:
        group_vars = [g.lower() for g in group_vars]

    # add sub to group_vars list
    group_vars.insert(0, 'group')
    group_vars.insert(0, 'sub')
    
    # make output and working directories
    outDir = op.join(resultsDir, 'group_analysis')
    workDir = op.join(resultsDir,'processing')
    os.makedirs(outDir, exist_ok=True)
    os.makedirs(workDir, exist_ok=True)
    
    # if user requested overwrite, delete previous directories
    if (overwrite == 'yes') & (len(os.listdir(outDir)) != 0):
        print('Overwriting existing outputs.')
        # remove directories
        shutil.rmtree(outDir)
        # create new directories
        os.mkdir(outDir)

    # if user requested no overwrite, create new output directory with date and time stamp
    if (overwrite == 'no') & (len(os.listdir(outDir)) != 0):
        print('Creating new output directories to avoid overwriting existing outputs.')
        today = datetime.now() # get date
        datestring = today.strftime('%Y-%m-%d_%H-%M-%S')
        outDir = (outDir + '_' + datestring) # new directory path
        # create new directories
        os.mkdir(outDir)

    # identify analysis README file
    readme_file=op.join(resultsDir, 'README.txt')
    
    # add config details to project README file
    with open(args.config, 'r') as file_1, open(readme_file, 'a') as file_2:
        file_2.write('Second level outputs were generated by running the secondlevel_pipeline.py \n')
        file_2.write('Pipeline parameters were defined by the {} file \n'.format(args.config))
        for line in file_1:
            file_2.write(line)
    
    # if split half requested
    if splithalf == 'yes':
        splithalves=[1,2]
    else:
        splithalves=[0]

    # for each contrast
    for c, contrast_id in enumerate(contrast_opts):
        for s, splithalf_id in enumerate(splithalves):
            # extract details from subject file
            sub_df=pd.read_csv(args.file[0], sep=' ', converters={'sub': str})
            sub_df.columns = sub_df.columns.str.lower() # lowercase column names
            sub_df=sub_df[group_vars]
            
            # run secondlevel workflow with the inputs defined above
            generate_model_files(args.projDir, derivDir, resultsDir, outDir, workDir, args.subjects, args.runs, sub_df, task, ses, splithalf_id, contrast_id, nonparametric, group_opts, group_vars, est_group_variances, tfce, nperm)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()