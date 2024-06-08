"""
Individual run analysis using outputs from fMRIPrep

Adapted script from original notebook:
https://github.com/poldrack/fmri-analysis-vm/blob/master/analysis/postFMRIPREPmodelling/First%20and%20Second%20Level%20Modeling%20(FSL).ipynb

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page
Nesting of functions: main > argparser > process_subject > create_timecourse_workflow > data_grabber > process_data_files > denoise_data > extract_timecourse

Requirement: BIDS dataset (including events.tsv), derivatives directory with fMRIPrep outputs, and modeling files

"""
import pandas as pd
import numpy as np
import argparse
import scipy.stats
from scipy.spatial import distance
import matplotlib.pyplot as plt
import os.path as op
import os
import glob
import shutil
import datetime
import math
from nilearn import plotting
from nilearn import image
from nilearn import masking
import nilearn
import shutil

def process_subject(projDir, resultsDir, sub, runs, task, events, splithalves, search_spaces, template, top_nvox):

    # define search spaces dictionary
    roi_dict = {'lEBA':'body', 'rEBA':'body',
                'lFFA':'face', 'lOFA':'face', 'lSTS':'face', 'rFFA':'face', 'rOFA':'face', 'rSTS':'face',
                'lLOC':'object', 'rLOC': 'object',
                'lPPA':'scene', 'lRSC':'scene', 'lTOS':'scene', 'rPPA':'scene', 'rRSC':'scene', 'rTOS':'scene',
                'DMPFC':'ToM', 'LTPJ':'ToM', 'MMPFC':'ToM', 'PC':'ToM', 'RSTS':'ToM', 'RTPJ':'ToM', 'VMPFC':'ToM',
                'lvwfa':'vwfa'}
   
    # grab ROI search space files
    roi_masks = list()
    for m in search_spaces:
        # define network
        network = roi_dict[m]
        print('Will define functional ROI using {} search space within {} network'.format(m, network))
        
        # grab files
        if template != None: # if a template was specified (ie resampled search spaces are requested)
            # extract main part of  template name
            template_name = template.split('_')[0]
            roi_file = glob.glob(op.join(projDir, 'data', 'search_spaces', '{}/{}/{}*.nii.gz'.format(network, template_name, m)))
        else:
            roi_file = glob.glob(op.join(projDir, 'data', 'search_spaces', '{}/{}*.nii.gz'.format(network, m)))
        
        roi_masks.append(roi_file)
        
    # for each run
    for r in runs:
        # for each splithalf
        for s in splithalves:
            if s == 0:
                statsDir = op.join(resultsDir, 'sub-{}'.format(sub), 'model', 'run{}'.format(r))
                froiDir = op.join(resultsDir, 'sub-{}'.format(sub), 'frois', 'run{}'.format(r))
                # grab functional file for resampling
                mni_file = glob.glob(op.join(resultsDir, 'sub-{}'.format(sub), 'preproc', 'run{}'.format(r), '*preproc_bold.nii.gz'))
            else:
                statsDir = op.join(resultsDir, 'sub-{}'.format(sub), 'model', 'run{}_splithalf{}'.format(r,s))
                froiDir = op.join(resultsDir, 'sub-{}'.format(sub), 'frois', 'run{}_splithalf{}'.format(r,s))
                # grab functional file for resampling
                mni_file = glob.glob(op.join(resultsDir, 'sub-{}'.format(sub), 'preproc', 'run{}_splithalf{}'.format(r,s), '*preproc_bold.nii.gz'))
            
            # make frois directory
            os.makedirs(froiDir, exist_ok=True)
              
            # load and binarize mni file
            mni_img = image.load_img(mni_file)
            mni_bin = mni_img.get_fdata() # get image data (as floating point data)
            # ensure that mni img is binarized
            mni_bin[mni_bin >= 1] = 1 # for values equal to or greater than 1, make 1 (values less than 1 are already 0)
            mni_bin = image.new_img_like(mni_img, mni_bin) # create a new image of the same class as the initial image

            # for each ROI search space
            for m, roi in enumerate(roi_masks):
                # load roi mask
                mask_img = image.load_img(roi)
                mask_bin = mask_img.get_fdata()
                
                # ensure that mask/ROI is binarized
                mask_bin[mask_bin >= 1] = 1 # for values equal to or greater than 1, make 1 (values less than 1 are already 0)
                mask_bin = image.new_img_like(mask_img, mask_bin) # create a new image of the same class as the initial image
                
                # the masks should already be resampled, but check if this is true and resample if not
                if mni_img.shape[0:3] != mask_bin.shape[0:3]:
                    print('WARNING: the search space provided has different dimensions than the functional data!')
                    
                    # make directory to save resampled rois
                    roiDir = op.join(resultsDir, 'sub-{}'.format(sub), 'resampled_rois')
                    os.makedirs(roiDir, exist_ok=True)
                    
                    # extract file name
                    roi_name = str(roi).replace('/','-').split('-')[-1]                    
                    
                    roi_name = roi_name.split('.nii')[0]
                    resampled_file = op.join(roiDir, '{}_resampled.nii.gz'.format(roi_name))
                    
                    # check if file already exists
                    if os.path.isfile(resampled_file):
                        print('Found previously resampled {} ROI in output directory'.format(search_spaces[m]))
                        mask_bin = image.load_img(resampled_file)
                    else:
                        # resample image
                        print('Resampling {} search space to match functional data'.format(search_spaces[m]))
                        mask_bin = image.resample_to_img(mask_bin, mni_img, interpolation='nearest')
                        mask_bin.to_filename(resampled_file)
                
                # for each contrast
                for c in events:
                    print('Defining fROI using top {} voxels within {} contrast'.format(top_nvox, c))
                    z_file = glob.glob(op.join(statsDir, '*{}_zstat.nii.gz'.format(c)))
                    z_img = image.load_img(z_file)
                    #t_file = glob.glob(op.join(statsDir, '*{}_tstat.nii.gz'.format(c)))
                    #t_img = image.load_img(t_file)
                    
                    # mask contrast image with roi image
                    masked_img = image.math_img('img1 * img2', img1 = z_img, img2 = mask_bin)
                    masked_data = masked_img.get_fdata()
                    
                    # set negative and 0 values to nan before grabbing top voxels to ensure only positive values are included
                    masked_data[masked_data <= 0] = np.nan

                    # save masked file (optional data checking step)
                    #masked_img_file = op.join(froiDir, 'sub-{}_run-{:02d}_splithalf-{:02d}_{}_{}-masked.nii.gz'.format(sub, r, s, search_spaces[m], c))
                    #masked_img.to_filename(masked_img_file)
                    
                    # get top voxels
                    masked_data_inds = (-masked_data).argsort(axis = None) # the negative ensures that values are returned in decending order
                    masked_data[np.unravel_index(masked_data_inds[top_nvox:], masked_data.shape)] = np.nan
                    
                    # binarize top voxel mask
                    sub_froi = masked_data.copy()
                    sub_froi[~np.isnan(sub_froi)] = 1
                    sub_froi[np.isnan(sub_froi)] = 0
                    
                    # save froi file
                    sub_froi = image.new_img_like(mask_bin, sub_froi) # create a new image of the same class as the initial image
                    sub_roi_file = op.join(froiDir, 'sub-{}_run-{:02d}_splithalf-{:02d}_{}_{}.nii.gz'.format(sub, r, s, search_spaces[m], c))
                    sub_froi.to_filename(sub_roi_file)

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
    # call argparser function that defines command line inputs
    parser = argparser()
    args = parser.parse_args(argv) 

    # print if the project directory is not found
    if not op.exists(args.projDir):
        raise IOError('Project directory {} not found.'.format(args.projDir))    
        
    # print if the project directory is not found
    if not op.exists(args.projDir):
        raise IOError('Project directory {} not found.'.format(args.projDir))
    
    # print if config file is not found
    if not op.exists(args.config):
        raise IOError('Configuration file {} not found. Make sure it is saved in your project directory!'.format(args.config))
    
    # read in configuration file and parse inputs
    config_file=pd.read_csv(args.config, sep='\t', header=None, index_col=0).replace({np.nan: None})
    resultsDir=config_file.loc['resultsDir',1]
    task=config_file.loc['task',1]
    events=config_file.loc['events',1].replace(' ','').split(',')
    search_spaces=config_file.loc['search_spaces',1].replace(' ','').split(',')
    splithalf=config_file.loc['splithalf',1]
    template=config_file.loc['template',1]
    top_nvox=int(config_file.loc['top_nvox',1])
    
    if splithalf == 'yes':
        splithalves = [1,2]
    else:
        splithalves = [0]

    # print if results directory is not found
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))

    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        # pass runs for this sub
        sub_runs=args.runs[index]
        sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
        sub_runs=list(map(int, sub_runs)) # convert to integers
              
        # create a process_subject workflow with the inputs defined above
        process_subject(args.projDir, resultsDir, sub, sub_runs, task, events, splithalves, search_spaces, template, top_nvox)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()