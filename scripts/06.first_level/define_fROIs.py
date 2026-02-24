"""
Script to define subject functional ROIs using contrast maps generated in firstlevel pipeline

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page

"""
import sys
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

def process_subject(projDir, sharedDir, resultsDir, sub, runs, task, contrast_opts, splithalves, search_spaces, match_events, template, top_nvox, percent):

    # define search spaces dictionary
    roi_dict = {'lEBA':'body', 'rEBA':'body',
                'lFFA':'face', 'lOFA':'face', 'lSTS':'face', 'rFFA':'face', 'rOFA':'face', 'rSTS':'face',
                'lLOC':'object', 'rLOC': 'object',
                'lPPA':'scene', 'lRSC':'scene', 'lTOS':'scene', 'rPPA':'scene', 'rRSC':'scene', 'rTOS':'scene',
                'DMPFC':'tom', 'LTPJ':'tom', 'MMPFC':'tom', 'rMMPFC':'tom', 'lMMPFC':'tom', 'PC':'tom', 'RSTS':'tom', 'RTPJ':'tom', 'VMPFC':'tom',
                'DMPFC_9mm':'kmvpa_adults_tomloc', 'LASTS_9mm':'kmvpa_adults_tomloc', 'LTPJ_9mm':'kmvpa_adults_tomloc', 'MMPFC_9mm':'kmvpa_adults_tomloc', 'PC_9mm':'kmvpa_adults_tomloc', 'RASTS_9mm':'kmvpa_adults_tomloc', 'RMSTS_9mm':'kmvpa_adults_tomloc', 'RTPJ_9mm':'kmvpa_adults_tomloc', 'VMPFC_9mm':'kmvpa_adults_tomloc',
                'lvwfa':'vwfa','vwfa1':'vwfa','vwfa2':'vwfa',
                'language':'language', 'LIFGorb':'language', 'LIFG':'language', 'LMidFG':'language', 'LAntTemp':'language', 'LPostTemp':'language', 'LAngG':'language', 'RIFGorb':'language', 'RIFG':'language', 'RMidFG':'language', 'RAntTemp':'language', 'RPostTemp':'language', 'RAngG':'language',
                'multiple_demand':'multiple_demand', 'LpostParietal':'multiple_demand', 'LmidParietal':'multiple_demand', 'LantParietal':'multiple_demand', 'LsupFrontal':'multiple_demand', 'LprecG':'multiple_demand', 'LIFGop':'multiple_demand', 'LmidFrontal':'multiple_demand', 'LmidFrontalOrb':'multiple_demand', 'Linsula':'multiple_demand', 'LmedialFrontal':'multiple_demand', 'RpostParietal':'multiple_demand', 'RmidParietal':'multiple_demand', 'RantParietal':'multiple_demand', 'RsupFrontal':'multiple_demand', 'RprecG':'multiple_demand', 'RIFGop':'multiple_demand', 'RmidFrontal':'multiple_demand', 'RmidFrontalOrb':'multiple_demand', 'Rinsula':'multiple_demand', 'RmedialFrontal':'multiple_demand'}
    
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
            roi_file = glob.glob(op.join(sharedDir, 'search_spaces', '{}/{}/{}_*.nii.gz'.format(network, template_name, m)))
            
            if not roi_file: # check projDir directory for search spaces if not in shared directory
                roi_file = glob.glob(op.join(projDir, 'files', 'search_spaces', '{}/{}/{}_*.nii.gz'.format(network, template_name, m)))
        else:
            roi_file = glob.glob(op.join(sharedDir, 'search_spaces', '{}/{}_*.nii.gz'.format(network, m)))
            
            if not roi_file: # check projDir directory for search spaces if not in shared directory
                roi_file = glob.glob(op.join(projDir, 'files', 'search_spaces', '{}/{}_*.nii.gz'.format(network, m)))
        
        roi_masks.append(roi_file)
        
    # define combined run directory for this subject
    combinedDir = op.join(resultsDir, '{}'.format(sub), 'model', 'combined_runs')
    
    # check if combinedDir exists
    if op.exists(combinedDir): # if yes, generate fROIs for the combined runs
        print('Found combined runs directory. fROIs will be defined based on the combined data.')
        runs=[0]
    
    # for each run
    for r in runs:
        # for each splithalf
        for s in splithalves:
            if s == 0 and r != 0:
                modelDir = op.join(resultsDir, '{}'.format(sub), 'model', 'run{}'.format(r))
                froiDir = op.join(resultsDir, '{}'.format(sub), 'frois', 'run{}'.format(r))
                # grab functional file for resampling
                mni_file = glob.glob(op.join(resultsDir, '{}'.format(sub), 'preproc', 'run{}'.format(r), '*_bold.nii.gz'))[0]
            elif s == 0 and r == 0:
                modelDir = combinedDir
                froiDir = op.join(resultsDir, '{}'.format(sub), 'frois', 'combined_runs')
                # grab functional file for resampling (doesn't matter which one)
                mni_file = glob.glob(op.join(resultsDir, '{}'.format(sub), 'preproc', 'run1', '*_bold.nii.gz'))[0]
            elif s != 0 and r != 0:
                modelDir = op.join(resultsDir, '{}'.format(sub), 'model', 'run{}_splithalf{}'.format(r,s))
                froiDir = op.join(resultsDir, '{}'.format(sub), 'frois', 'run{}_splithalf{}'.format(r,s))
                # grab functional file for resampling
                mni_file = glob.glob(op.join(resultsDir, '{}'.format(sub), 'preproc', 'run{}_splithalf{}'.format(r,s), '*_bold.nii.gz'))[0]
            elif s != 0 and r == 0:
                modelDir = op.join(combinedDir, 'splithalf{}'.format(s))
                froiDir = op.join(resultsDir, '{}'.format(sub), 'frois', 'combined_runs', 'splithalf{}'.format(s))
                # grab functional file for resampling (doesn't matter which one)
                mni_file = glob.glob(op.join(resultsDir, '{}'.format(sub), 'preproc', 'run1_splithalf{}'.format(s), '*_bold.nii.gz'))[0]       
            # make frois directory
            os.makedirs(froiDir, exist_ok=True)
              
            # load and binarize mni file
            mni_img = image.load_img(mni_file)
            mni_bin = mni_img.get_fdata() # get image data (as floating point data)
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
                    roiDir = op.join(resultsDir, 'resampled_rois')
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
                for c in contrast_opts:
                    if match_events == 'yes' and search_spaces[m].lower() not in c: # if the search space (lowercase) is contained within the contrast_opts specified
                        print('Skipping {} search space for the {} contrast'.format(search_spaces[m], c))
                    else: 
                        z_file = glob.glob(op.join(modelDir, '*_{}_zstat.nii.gz'.format(c)))
                        z_img = image.load_img(z_file)
                                                
                        # mask contrast image with roi image
                        masked_img = image.math_img('img1 * img2', img1 = z_img, img2 = mask_bin)
                        masked_data = masked_img.get_fdata()
                        
                        if percent == 'yes':
                            # calculate number of voxels within the search space - do this before removing nan voxels so all participants have the same number of voxels extracted
                            search_space = mask_bin.get_fdata()
                            nvox_mask = np.sum(search_space != 0)
                            
                            # calculate nvox as percent of mask size
                            nvox = int(np.ceil(nvox_mask * top_nvox / 100))
                            
                            print('Defining fROI using top {} percent of voxels within {} contrast. Number of voxels in fROI: {}'.format(top_nvox, c, nvox))
                            
                        else:
                            # nvox is set as the provided top_nvox value
                            nvox = top_nvox
                            print('Defining fROI using top {} voxels within {} contrast'.format(nvox, c))
                        
                        # get index of non-zero voxels within search space
                        #zero_vox_inds = (search_space == 0)
                        
                        # set all voxels that fall outside the search space to nan
                        # this is done because the voxels will be ranked in descending order so negative values will be ranked after 0 values meaning that voxels outside the search space 
                        # would be included in the fROI definition if the number of voxels with positive values is fewer than the requested nvox threshold
                        # the problem with this approach is that if the search space doesn't overlap with the contrast data/acquired data, then 0s will remain in the search space that should be removed
                        #masked_data[zero_vox_inds] = np.nan
                        
                        # an alternative approach is to set 0 values to nan before grabbing top voxels
                        # this *could* set voxels in the search space that are within the contrast map to 0 but safer than the prior approach and an unlikely outcome
                        masked_data[masked_data == 0.00000000] = np.nan

                        # save masked file (optional data checking step)
                        #masked_img_file = op.join(froiDir, '{}_run-{:02d}_splithalf-{:02d}_{}_{}-masked.nii.gz'.format(sub, r, s, search_spaces[m], c))
                        #masked_img.to_filename(masked_img_file)
                        
                        # get top voxels
                        masked_data_inds = (-masked_data).argsort(axis = None) # the negative ensures that values are returned in descending order
                        masked_data[np.unravel_index(masked_data_inds[nvox:], masked_data.shape)] = np.nan # set voxels not in nvox to nan
                        
                        # binarize top voxel mask
                        sub_froi = masked_data.copy()
                        sub_froi[~np.isnan(sub_froi)] = 1
                        sub_froi[np.isnan(sub_froi)] = 0
                        
                        # roi_name_lower = search_spaces[m].lower()
                        
                        # save froi file
                        # could use roi_name_lower instead of search_spaces[m] to get all lowercase names
                        sub_froi = image.new_img_like(mask_bin, sub_froi) # create a new image of the same class as the initial image
                        # sub_roi_file = op.join(froiDir, '{}_run-{:02d}_splithalf-{:02d}_{}-{}_{}_top{}.nii.gz'.format(sub, r, s, network, search_spaces[m], c, nvox)) # include network in file output name
                        sub_roi_file = op.join(froiDir, '{}_task-{}_run-{:02d}_splithalf-{:02d}_{}_{}_top{}.nii.gz'.format(sub, task, r, s, search_spaces[m], c, nvox))
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
    sharedDir=config_file.loc['sharedDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    task=config_file.loc['task',1]
    splithalf=config_file.loc['splithalf',1]
    contrast_opts=config_file.loc['contrast',1].replace(' ','').split(',')
    search_spaces=config_file.loc['search_spaces',1].replace(' ','').split(',')
    match_events=config_file.loc['match_events',1]
    template=config_file.loc['template',1]
    top_nvox=config_file.loc['top_nvox',1]
    
    # lowercase contrast option to avoid case errors - allows flexibility in how users specify events in config and contrasts files
    contrast_opts = [c.lower() for c in contrast_opts]
    
    if splithalf == 'yes':
        splithalves = [1,2]
    else:
        splithalves = [0]

    # print if results directory is not specified or found
    if resultsDir == None:
        raise IOError('No resultsDir was specified in config file but is required to define fROIs!')
    
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
        
    # identify analysis README file
    readme_file=op.join(resultsDir, 'README.txt')
    
    # add config details to project README file
    with open(readme_file, 'a') as file_1:
        file_1.write('\n')
        file_1.write('fROIs were defined using the define_ROIs.py script \n')
        file_1.write('The following search spaces were specified in the config file: {} \n'.format(search_spaces))
        file_1.write('The top {} voxels were selected for each search space within the contrast: {} \n'.format(top_nvox, contrast_opts))
    
    # flag whether top n or top n % of voxels should be extracted and set value to integer
    if top_nvox.endswith('-percent'):
        percent = 'yes'
        top_nvox = int(top_nvox.replace('-percent', ''))
    else:
        percent = 'no'
        top_nvox = int(top_nvox)
        
    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        print('Defining fROIs for {}'.format(sub))
        
        # check that run info was provided in subject list, otherwise throw an error
        if not args.runs:
            raise IOError('Run information missing. Make sure you are passing a subject-run list to the pipeline!')
            
        # pass runs for this sub
        sub_runs=args.runs[index]
        sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
        if sub_runs == ['NA']: # if run info isn't used in file names
            sub_runs = [1]
        else:
            sub_runs=list(map(int, sub_runs)) # convert to integers     
        
        # create a process_subject workflow with the inputs defined above
        process_subject(args.projDir, sharedDir, resultsDir, sub, sub_runs, task, contrast_opts, splithalves, search_spaces, match_events, template, top_nvox, percent)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()