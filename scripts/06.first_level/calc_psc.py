"""
Calculate percent signal change using the outputs from the firstlevel model.

This script will:
(1) calculate the voxelwise mean signal value of the scaled, filtered, artifact nan'd data
(2) calculate percent signal change for requested conditions (from config file) using the following approach:
PSC = (cope map * PP Height [peak to peak height] * 100)/ voxelwise mean

The script assumes that cope file (rather than parameter estimate files are being used, 
so the design.con file rather than the design.mat file is used to extract the PP Height.

In order to analyse a single condition beta/parameter estimate, it is assumed that users will greater a 'contrast'
that is weights the single condition by 1 (e.g., [1 0 0]), so a labelled contrast file is generated but no contrast is actually done.

The outputs are saved in the *psc* folder for each run for each subject. 

This script should be run prior to the extract stats script is the user wants to extract mean PSC values.

"""
import sys
from nipype.interfaces.fsl import MeanImage, BinaryMaths, ImageMaths
import nipype.interfaces.io as nio
from nipype import Workflow, Node
import nibabel as nib
from nibabel import load
import nilearn
from nilearn import image
from bids.layout import BIDSLayout
import re
import os
import os.path as op
import glob
import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError
import argparse
import glob
import shutil

# define calc psc workflow function
def calc_psc_workflow(projDir, derivDir, resultsDir, workDir, sub, ses, task, sub_runs, contrast_opts, splithalf_id, hpf, filter_opt, TR, space_name, name='{}_task-{}_calcpsc'):

    # define subject output directory
    subDir = op.join(resultsDir, '{}'.format(sub))

    # raise an error if the firstlevel output directory doesn't exist
    if not subDir:
        raise FileNotFoundError('No firstlevel outputs found for {}'.format(sub))
    
    # delete prior processing directories because cache files can interfere with workflow
    subworkDir = op.join(workDir, '{}_task-{}_calcpsc'.format(sub, task))
    if os.path.exists(subworkDir):
        shutil.rmtree(subworkDir)
        
    # initialize workflow
    wf = Workflow(name=name.format(sub, task),
                  base_dir=workDir)
    
    # grab MNI mask
    if ses != 'no': # if session was provided
        # define path to preprocessed functional and mask data (subject derivatives func folder)
        funcDir = op.join(derivDir, '{}'.format(sub), 'ses-{}'.format(ses), 'func')
        mni_mask = glob.glob(op.join(funcDir, '{}_ses-{}_space-{}*_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub, ses, space_name)))[0]
        
    else: # if session was 'no'
        # define path to preprocessed functional and mask data (subject derivatives func folder)
        funcDir = op.join(derivDir, '{}'.format(sub), 'func')
        mni_mask = glob.glob(op.join(funcDir, '{}_space-{}*_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub, space_name)))[0]
                  
    # for each run
    for r in sub_runs:
        # define directories based on run and splithalf info
        if splithalf_id == 0:
            pscDir = op.join(subDir, 'psc', 'run{}'.format(r))
            designDir = op.join(subDir, 'design', 'run{}'.format(r))
            modelDir = op.join(subDir, 'model', 'run{}'.format(r))
            preprocDir = op.join(subDir, 'preproc', 'run{}'.format(r))
            
            # grab rapidart outlier file
            art_file = glob.glob(op.join(subDir, 'art_files', 'run{}'.format(r), '*out-vols.txt'))[0]
            
            # save intermediate file - optional output for data checking
            denoised_file = op.join(pscDir, '{}_task-{}_run-{:03d}_denoised.nii.gz'.format(sub, task, r))
            
            # define output run mean file - optional output for data checking
            mean_file = op.join(pscDir, '{}_task-{}_run-{:03d}_voxelwise_mean.nii.gz'.format(sub, task, r))
            
        else:
            pscDir = op.join(subDir, 'psc', 'run{}_splithalf{}'.format(r, splithalf_id))
            designDir = op.join(subDir, 'design', 'run{}_splithalf{}'.format(r, splithalf_id))
            modelDir = op.join(subDir, 'model', 'run{}_splithalf{}'.format(r, splithalf_id))
            preprocDir = op.join(subDir, 'preproc', 'run{}_splithalf{}'.format(r, splithalf_id))
            
            # grab rapidart outlier file
            art_file = glob.glob(op.join(subDir, 'art_files', 'run{}_splithalf{}'.format(r, splithalf_id), '*out-vols.txt'))[0]
            
            # save intermediate file - optional output for data checking
            denoised_file = op.join(pscDir, '{}_task-{}_run-{:03d}_splithalf-{:03d}_denoised.nii.gz'.format(sub, task, r, splithalf_id))
            
            # define output run mean file - optional output for data checking
            mean_file = op.join(pscDir, '{}_task-{}_run-{:03d}_splithalf-{:03d}_voxelwise_mean.nii.gz'.format(sub, task, r, splithalf_id))
        
        # grab design file (has PP heights)
        design_file = op.join(designDir, 'run{}.con'.format(r))
            
        # make psc directory
        os.makedirs(pscDir, exist_ok=True)
        
        # grab scaled preproc file
        scaled_file = glob.glob(op.join(preprocDir, '*_scaled.nii.gz'))[0]
        
        if not scaled_file:
            raise FileNotFoundError('No scaled firstlevel outputs found for {}'.format(sub))
        
        print('Will denoise the following file to calculate voxelwise mean in run {}: {}'.format(r, scaled_file))
        
        # get number of volumes in scaled data (accounts for dropped/split data already)
        nVols = (load(scaled_file).shape[3])
        
        print('Number of volumes in run {}: {}'.format(r, nVols))
        
        # generate vector of volume indices (where inclusion means to retain volume) to use for scrubbing
        vol_indx = np.arange(nVols, dtype=np.int64)
        
        # read in art file, creating an empty dataframe if no outlier volumes (i.e., empty text file)
        try:
            outliers = pd.read_csv(art_file, header=None)[0].astype(int)
        except EmptyDataError:
            outliers = pd.DataFrame()
        
        print('ART identified motion spikes will be scrubbed from data')             
        if np.shape(outliers)[0] != 0: # if there are outlier volumes
            # remove excluded volumes from vec
            vol_indx = np.delete(vol_indx, [outliers])
            print('{} outlier volumes will be scrubbed in run {}'.format(len(outliers), r))
        else:
            print('No outlier volumes in run {}'.format(r))
        
        # convert filter from seconds to Hz
        hpf_hz = 1/hpf
        print('Will apply a {} filter using a high pass filter cutoff of {}Hz for run {}.'.format(filter_opt, hpf_hz, r))
        
        # define kwargs input to signal.clean function
        if filter_opt == 'butterworth':
            kwargs_opts={'clean__sample_mask':vol_indx, 
                         'clean__butterworth__t_r':TR,
                         'clean__butterworth__high_pass':hpf_hz}
        elif filter_opt == 'cosine':
            kwargs_opts={'clean__sample_mask':vol_indx, 
                         'clean__cosine__t_r':TR,
                         'clean__cosine__high_pass':hpf_hz}
        else:
            kwargs_opts={'clean__sample_mask':vol_indx,
                         'clean__t_r':TR}
        
        # filter and remove artifact timepoints in scaled data file
        denoised_data = image.clean_img(scaled_file, mask_img=mni_mask, detrend=False, standardize=False, **kwargs_opts)
        
        # save denoised data
        nib.save(denoised_data, denoised_file)
        
        # step 1: calculate voxelwise mean across this run
        meanfunc = Node(MeanImage(), name='meanfunc_run{}_splithalf{}'.format(r, splithalf_id))
        meanfunc.inputs.dimension = 'T' # returns the mean across time
        meanfunc.inputs.in_file = denoised_file
        #meanfunc.inputs.out_file = mean_file # can return this file as a data checking step
        
        # add the meanfunc node to the workflow
        wf.add_nodes([meanfunc])
        meanfunc.run()
        
        # remove intermediate file
        os.remove(denoised_file)
        
        # loop over cope maps
        for cope in contrast_opts:
            print('Calculating percent signal change for {} condition'.format(cope))
            
            # grab copes file corresponding to cope map
            cope_file = glob.glob(op.join(modelDir, 'con*_{}_cope.nii.gz'.format(cope)))[0]
            
            # extract contrast number
            con_num = int(re.search(r'con_(\d+)', cope_file).group(1))
            
            print('Using cope file: {}'.format(cope_file))
            
            # read in ppheights from design file
            with open(design_file, 'r') as d:
                for line in d:
                    if line.startswith('/PPheights'):
                        ppheights = [float(x) for x in line.split()[1:]]
                        
            # use contrast number to select correct pp height
            pp_value = ppheights[con_num - 1] # subtract 1 because of 0 indexing in python
            
            print('Using contrast peak-to-peak height {} in the PSC calculation: {}'.format(con_num, pp_value))
            
            # define psc output files
            mul_file = op.join(pscDir, '{}_multiplied.nii.gz'.format(cope))
            psc_file = op.join(pscDir, '{}_psc.nii.gz'.format(cope))
            
            # step 2: multiply cope file by PP height * 100
            pp_scale_factor = pp_value * 100
            multiplycope = Node(ImageMaths(), name='multiplycope_run{}_splithalf{}_{}'.format(r, splithalf_id, cope))
            multiplycope.inputs.in_file = cope_file
            multiplycope.inputs.args = '-mul {}'.format(pp_scale_factor)
            #multiplycope.inputs.out_file = mul_file # can return this file as a data checking step

            # step 3: divide cope map by the voxelwise mean_file
            dividecope = Node(BinaryMaths(), name='dividecope_run{}_splithalf{}_{}'.format(r, splithalf_id, cope))
            dividecope.inputs.operation = 'div' # divide
            dividecope.inputs.out_file = psc_file
            
            # add nodes to workflow and connect inputs
            wf.add_nodes([multiplycope, dividecope])
            wf.connect(multiplycope, 'out_file', dividecope, 'in_file')
            wf.connect(meanfunc, 'out_file', dividecope, 'operand_file')
            
    return wf

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
    bidsDir=config_file.loc['bidsDir',1]
    derivDir=config_file.loc['derivDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    task=config_file.loc['task',1]
    ses=config_file.loc['sessions',1]
    contrast_opts=config_file.loc['contrast',1].replace(' ','').split(',')
    splithalf=config_file.loc['splithalf',1]
    hpf=int(config_file.loc['hpf',1])
    filter_opt=config_file.loc['filter',1]
    space=config_file.loc['space',1]
    
    # define working directory
    workDir = op.join(resultsDir, 'processing')
    
    # lowercase contrast_opts and events to avoid case errors - allows flexibility in how users specify events in config and contrasts files
    contrast_opts = [c.lower() for c in contrast_opts]
    
    if splithalf == 'yes':
        splithalves = [1,2]
    else:
        splithalves = [0]
    
    # define space name
    if space == 'MNI':
        space_name = 'MNI152NLin2009cAsym'
        print('Pipeline will be run using outputs in {} space'.format(space_name))
    if space == 'native':
        space_name = 'T1w'
        print('Pipeline will be run using outputs in {} space'.format(space_name))
        
    # identify analysis README file
    readme_file=op.join(resultsDir, 'README.txt')
    
    # add config details to project README file
    with open(readme_file, 'a') as file_1:
        file_1.write('\n')
        file_1.write('Percent signal change was calculated using the calc_psc.py script and options specified in the config file: {} \n'.format(args.config))

    # get layout of BIDS directory
    # this is necessary because the pipeline reads the functional json files that have TR info
    # the derivDir (where fMRIPrep outputs are) doesn't have json files with this information, so getting the layout of that directory will result in an error
    layout = BIDSLayout(bidsDir)
    
    # extract TR info from bidsDir bold json files (assumes TR is same across runs)
    epi = layout.get(suffix='bold', task=task, return_type='file')[0] # take first file
    TR = layout.get_metadata(epi)['RepetitionTime'] # extract TR field  
    
    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        for splithalf_id in splithalves:
            # check that run info was provided in subject list, otherwise throw an error
            if not args.runs:
                raise IOError('Run information missing. Make sure you are passing a subject-run list to the pipeline!')
            
            # pass runs for this sub
            sub_runs=args.runs[index]
            sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
            if sub_runs == ['NA']: # if run info isn't used in file names
                sub_runs = [1] # because outputs saved in run1 folders even if run info isn't specified in file name
            else:
                sub_runs=list(map(int, sub_runs)) # convert to integers
                  
            # create calc psc workflow with the inputs defined above
            wf = calc_psc_workflow(args.projDir, derivDir, resultsDir, workDir, sub, ses, task, sub_runs, contrast_opts, splithalf_id, hpf, filter_opt, TR, space_name)
       
            # configure workflow options
            wf.config['execution'] = {'crashfile_format': 'txt',
                                      'remove_unnecessary_outputs': False,
                                      'keep_inputs': True}

            # run multiproc
            args_dict = {'n_procs' : 4}
            wf.run(plugin='MultiProc', plugin_args = args_dict)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()