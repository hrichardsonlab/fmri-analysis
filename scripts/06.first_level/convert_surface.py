"""
Convert either fMRIPrep preprocessed or additionally denoised volumes to surfaces 
based on option provided to convert_surf field in the config file

"""
import sys
import os
import os.path as op
import numpy as np
import pandas as pd
import argparse
import glob
import shutil
from datetime import datetime
import nipype.interfaces.freesurfer as fs

# define project surface function
def project_surface(sub, runs, projDir, derivDir, resultsDir, task, ses, smoothing_kernel_size, convert_surf):
    
    # create subject surf output directory
    surfDir =  op.join(resultsDir, 'sub-{}'.format(sub), 'surf')
    os.makedirs(surfDir, exist_ok=True)
    
    # define freesurfer directory
    fsDir = op.join(derivDir, 'sourcedata', 'freesurfer')
    
    # loop through specified runs
    for r, run in enumerate(runs):
        # define file prefix and add run info to file prefix if necessary
        prefix = '{}*task-{}'.format(sub, task)
        if run != 0:
            prefix = '{}_run-{:03d}'.format(prefix, run)
            runDir = 'run{}'.format(run)
        else:
            runDir = 'run1'
            
        # grab volume data file to convert to surface based on option provided to convert_surf
        if convert_surf == 'fmriprep':
            if ses != 'no': # if session was provided
                vol_file = glob.glob(op.join(derivDir, '{}'.format(sub), 'ses-{}'.format(ses), 'func', '{}_space-T1w_desc-preproc_bold.nii.gz'.format(prefix)))[0]
                
            else: # if session was 'no'
                vol_file = glob.glob(op.join(derivDir, '{}'.format(sub), 'func', '{}_space-T1w_desc-preproc_bold.nii.gz'.format(prefix)))[0]
            
            print('Will convert fMRIprep preprocessed data to surface: {}'. format(vol_file))
            
        elif convert_surf == 'denoised':
            vol_file = glob.glob(op.join(resultsDir, '{}'.format(sub), 'denoised', '{}/{}_denoised_padded_bold.nii.gz'.format(runDir, prefix, run)))[0]
            
            print('Will convert denoised data to surface: {}'. format(vol_file))
        
        # define output files depending on if run info is in file name
        if run != 0:
            # registration file
            reg_file = op.join(surfDir, '{}_task-{}_run-{:03d}_vol2surf.dat'.format(sub, task, run))
            
            # surface file
            surf_file = op.join(surfDir, '{}_task-{}_run-{:03d}_surf.mgh'.format(sub, task, run))
            
        else:
            # registration file
            reg_file = op.join(surfDir, '{}_task-{}_vol2surf.dat'.format(sub, task))
            
            # surface file
            surf_file = op.join(surfDir, '{}_task-{}_surf.mgh'.format(sub, task))
            
        ## GENERATE REGISTRATION
        # check if registration file already exists and generate if it does not
        if op.exists(reg_file):
            print('Found and will use already existing registration file: {}'.format(reg_file))
        
        else:
            print('Calculating registration file and saving to: {}'.format(reg_file))
            # register functional data to surface
            bbreg = fs.BBRegister()
            bbreg.inputs.subject_id = '{}'.format(sub)
            bbreg.inputs.source_file = vol_file
            bbreg.inputs.init = 'header'
            bbreg.inputs.contrast_type = 'bold'
            bbreg.inputs.subjects_dir = fsDir
            bbreg.inputs.out_reg_file = reg_file
            bbreg.run()
        
        # loop over hemispheres
        for hem in ['lh', 'rh']:
           # define prefix for surface files depending on if run info is in file name
            if run != 0:
                surf_prefix = op.join(surfDir, '{}_task-{}_run-{:03d}_hem-{}'.format(sub, task, run, hem))
            else:
                surf_prefix = op.join(surfDir, '{}_task-{}_hem-{}'.format(sub, task, hem))
            
            ## PROJECT TO SURFACE (uses mri_vol2surf)
            # also resamples outputs to fsaverage space for comparison across subjects
            vol2surf = fs.SampleToSurface()
            vol2surf.inputs.subjects_dir = fsDir
            vol2surf.inputs.source_file = vol_file
            vol2surf.inputs.reg_file = reg_file
            #vol2surf.inputs.reg_header = True # this works fine with BOLD data already in T1w space, but passing a reg file is slightly better for aligning the BOLD and surface data. Can skip the bbregister step if this is uncommented and reg_file is commented (the commands are mutually exclusive)
            vol2surf.inputs.subject_id = '{}'.format(sub)
            vol2surf.inputs.hemi = hem
            vol2surf.inputs.reshape = True
            vol2surf.inputs.smooth_surf = smoothing_kernel_size
            vol2surf.inputs.out_type = 'niigz'
            vol2surf.inputs.out_file = op.join('{}_surf.nii.gz'.format(surf_prefix))           
            vol2surf.inputs.cortex_mask = True
            vol2surf.inputs.sampling_method = 'point'
            vol2surf.inputs.sampling_range = 0.5
            vol2surf.inputs.sampling_units = 'frac' 
            vol2surf.inputs.interp_method = 'trilinear'
            vol2surf.inputs.target_subject = 'fsaverage6'
            vol2surf.run()
            
            import nibabel as nib
            img = nib.load(op.join('{}_surf.nii.gz'.format(surf_prefix)))
            data = img.get_fdata()
            print('Shape of output surface file:', data.shape)
                
# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-p', dest='projDir',
                        help='Project directory')
    parser.add_argument('-w', dest='workDir', default=os.getcwd(),
                        help='Working directory')
    parser.add_argument('-o', dest='outDir', default=os.getcwd(),
                        help='Output directory')
    parser.add_argument('-s', dest='subjects', nargs='*',
                        help='List of subjects to process (default: all)')
    parser.add_argument('-r', dest='runs', nargs='*',
                        help='List of runs for each subject')    
    parser.add_argument('-c', dest='config',
                        help='Configuration file')                                            
    parser.add_argument('-sparse', action='store_true',
                        help='Specify a sparse model')
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
    derivDir=config_file.loc['derivDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    space=config_file.loc['space',1]
    task=config_file.loc['task',1]
    ses=config_file.loc['sessions',1]
    smoothing_kernel_size=int(config_file.loc['smoothing',1])
    convert_surf=config_file.loc['convert_surf',1]
    
    # print if the fMRIPrep directory is not found
    if not op.exists(derivDir):
        raise IOError('Derivatives directory {} not found.'.format(derivDir))
    
    if space == 'MNI':
        print('WARNING: The config file indicates that MNI space is requested, but this is not compatible with surface based analyses. This script will assume any processed data are in native space. Make sure that this is true!')
    if space == 'native':
        print('Registration and projection to the surface will be done in native space as anticipated.')
    
    # define output and working directories
    if resultsDir: # if resultsDir was specified
        # save outputs to established resultsDir
        print('Saving results to existing results directory: {}'.format(resultsDir))
        outDir = resultsDir
        
        # identify analysis README file
        readme_file=op.join(outDir, 'README.txt')
        
        # add config details to project README file
        with open(readme_file, 'a') as file_1:
            file_1.write('\n')
            file_1.write('Volumes were projected to surfaces using convert_surface.py \n')
    
    else: # if no resultsDir was specified        
        outDir = op.realpath(args.outDir)
        
        # if user requested overwrite, delete previous directories
        if (overwrite == 'yes') & (len(os.listdir(outDir)) != 0):
            print('Overwriting existing outputs.')
            # remove directories
            shutil.rmtree(outDir)
            # create new directories
            os.mkdir(outDir)
            
        # if user requested no overwrite, create new working directory with date and time stamp
        if (overwrite == 'no') & (len(os.listdir(outDir)) != 0):
            print('Creating new output directories to avoid overwriting existing outputs.')
            today = datetime.now() # get date
            datestring = today.strftime('%Y-%m-%d_%H-%M-%S')
            outDir = (outDir + '_' + datestring) # new directory path
            # create new directories
            os.mkdir(outDir)

        # identify analysis README file
        readme_file=op.join(outDir, 'README.txt')
        
        # add config details to project README file
        with open(args.config, 'r') as file_1, open(readme_file, 'a') as file_2:
            file_2.write('Volumes were projected to surfaces using convert_surface.py \n')
            file_2.write('Pipeline parameters were defined by the {} file \n'.format(args.config))
            for line in file_1:
                file_2.write(line)
     
    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        # check that run info was provided in subject list, otherwise throw an error
        if not args.runs:
            raise IOError('Run information missing. Make sure you are passing a subject-run list to the pipeline!')
            
        # pass runs for this sub
        sub_runs=args.runs[index]
        sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
        sub_runs=[0 if x == 'NA' else x for x in sub_runs]
        sub_runs=list(map(int, sub_runs)) # convert to integers
               
        # run project surface function with the inputs defined above
        project_surface(sub, sub_runs, args.projDir, derivDir, resultsDir, task, ses, smoothing_kernel_size, convert_surf)
        
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()