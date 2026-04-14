"""
Representational Similarity Analysis (RSA) Script

This script computes the neural representational dissimilarity matrices (RDMs) for a set of ROIs. 
The RDMs could be computed over runs, folds, or splithalves depending on the options provided in the subject-run file passed to the script.

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page

"""
import sys
import pandas as pd
import numpy as np
import argparse
import scipy.stats
from scipy.spatial import distance
from scipy.spatial.distance import cdist, pdist, squareform
from scipy.spatial.distance import correlation
import os.path as op
import os
import glob
import shutil
import datetime
import math
from nilearn import image
from nilearn.maskers import NiftiMasker
import nilearn

def generate_rdm(projDir, sharedDir, resultsDir, froiDir, sub, task, runs, folds, splithalves, conditions, mask_opts, template, normalise):
    
    # make output rsa directories
    rsaDir = op.join(resultsDir, '{}'.format(sub), 'rsa')
    vectorsDir = op.join(rsaDir, 'condition_vectors')
    rdmDir = op.join(rsaDir, 'neural_rdms')
    os.makedirs(rsaDir, exist_ok=True)
    os.makedirs(vectorsDir, exist_ok=True)
    os.makedirs(rdmDir, exist_ok=True)
    
    # initalise list of condition vectors to calculate RDMs across runs/folds
    patterns = {}
    
    # for each run
    for run_id in runs:
        
        # for each splithalf
        for splithalf_id in splithalves:
            
            # should runs be treated like folds
            if folds == 'yes':
                print('Computing neural RDMs for fold {}'.format(run_id))
                combined = 'yes'
                if splithalf_id != 0:
                    modelDir = op.join(resultsDir, '{}'.format(sub), 'model', 'combined_runs', 'splithalf{}'.format(splithalf_id), 'fold{}'.format(run_id))
                if splithalf_id == 0:
                    modelDir = op.join(resultsDir, '{}'.format(sub), 'model', 'combined_runs', 'fold{}'.format(run_id))

            # do not treat runs as folds
            else:
                if splithalf_id != 0:
                    print('Computing neural RDMs for run {} splithalf {}'.format(run_id, splithalf_id))
                    # check if combined runs directory exists and use splithalf folders there if so
                    combinedDir = op.join(resultsDir, '{}'.format(sub), 'model', 'combined_runs')
                    if op.exists(combinedDir):
                        combined = 'yes'
                        modelDir = op.join(combinedDir, 'splithalf{}'.format(splithalf_id))
                    else:
                        print('Computing neural RDMs for run {}'.format(run_id))
                        combined = 'no'
                        modelDir = op.join(combinedDir, 'run{}_splithalf{}'.format(run_id, splithalf_id))
                        
                if splithalf_id == 0:
                    # don't bother checking for a combined runs directory here because at least 2 runs, folds, or splithalves of data are needed
                    combined = 'no'
                    modelDir = op.join(resultsDir, '{}'.format(sub), 'model', 'run{}'.format(run_id))
                    
            # grab roi file for each mask requested
            roi_masks = list()
            for m in mask_opts:
                # define aroi prefix
                aroi_prefix = op.join(resultsDir, '{}'.format(sub), 'arois', '{}_'.format(sub))
                
                # if a functional ROI was specified
                if 'fROI' in m:
                
                    # check if an froiDir was provided, look in the resultsDir if not
                    if froiDir == None:
                        print('No froiDir was specified in config file. Will look for fROIs in resultsDir.')
                        
                        # define fROI prefix depending on whether data were splithalf and/or combined
                        if splithalf_id != 0 and combined == 'no':
                            # ensure that the fROI from the *opposite* splithalf is picked up
                            if splithalf_id == 1:
                                print('Will skip stats extraction in splithalf{} for any fROIs defined in splithalf{}'.format(splithalf_id, splithalf_id))
                                froi_prefix = op.join(resultsDir, '{}'.format(sub), 'frois', 'run{}_splithalf2'.format(run_id))
                                
                            if splithalf_id == 2:
                                print('Will skip stats extraction in splithalf{} for any fROIs defined in splithalf{}'.format(splithalf_id, splithalf_id))
                                froi_prefix = op.join(resultsDir, '{}'.format(sub), 'frois', 'run{}_splithalf1'.format(run_id))
                        
                        elif splithalf_id != 0 and combined == 'yes':
                            # ensure that the fROI from the *opposite* splithalf is picked up
                            if splithalf_id == 1:
                                print('Will skip stats extraction in splithalf{} for any fROIs defined in splithalf{}'.format(splithalf_id, splithalf_id))
                                froi_prefix = op.join(resultsDir, '{}'.format(sub), 'frois', 'combined_runs', 'splithalf2')
                                
                            if splithalf_id == 2:
                                print('Will skip stats extraction in splithalf{} for any fROIs defined in splithalf{}'.format(splithalf_id, splithalf_id))
                                froi_prefix = op.join(resultsDir, '{}'.format(sub), 'frois', 'combined_runs', 'splithalf1')
                        
                        elif splithalf_id == 0 and combined == 'no':
                            froi_prefix = op.join(resultsDir, '{}'.format(sub), 'frois', 'run{}'.format(run_id))

                        elif splithalf_id == 0 and combined == 'yes':
                            froi_prefix = op.join(resultsDir, '{}'.format(sub), 'frois', 'combined_runs')
                    
                    # if an froiDir was provided - note that this option assumes (1) no splithalf fROIs and (2) fROIs defined by 1 run or combined across runs
                    else:
                        if not op.exists(froiDir):
                            raise IOError('fROI directory {} not found.'.format(froiDir))
                        
                        print('Will look for fROIs in froiDir: {}'.format(froiDir))

                        # define combined froiDir for this subject and check if it exists
                        combinedfroiDir = op.join(froiDir, '{}'.format(sub), 'frois', 'combined_runs')
                        
                       # define fROI prefix depending on whether fROIs were combined
                        if op.exists(combinedfroiDir):
                            froi_prefix = combinedfroiDir
                        
                        else: # if there is no combined_runs folder in the froiDir
                            # this presumes that if fROIs were not combined, then there was only 1 run of the localiser/task acquired
                            # this could be modified to track an fROI specific run_id variable but it can't use the current run_id variable because this is based off of runs of a separate task
                            #froi_prefix = op.join(froiDir, '{}'.format(sub), 'frois', 'run1')
                            froi_prefix = op.join(froiDir, '{}'.format(sub), 'frois', 'run2')
                        
                    # grab the mni file (used only if resampling is required)
                    mni_file = glob.glob(op.join(resultsDir, '{}'.format(sub), 'preproc', '*', '*_bold.nii.gz'))[0]

                    if not froi_prefix:
                        print('ERROR: unable to locate fROI file. Make sure a resultsDir or froiDir is provided in the config file!')
                    else:
                        roi_name = m.split('fROI-')[1]
                        roi_file = glob.glob(op.join('{}'.format(froi_prefix),'{}_*{}_*.nii.gz'.format(sub, roi_name)))
                        roi_masks.append(roi_file)
                        print('Using {} fROI file from {}'.format(roi_name, roi_file))
                
                # if any other ROI was specified
                else:
                    # grab the mni file (used only if resampling is required)
                    mni_file = glob.glob(op.join(resultsDir, '{}'.format(sub), 'preproc', '*', '*_bold.nii.gz'))[0]
                    
                    # if a freesurfer ROI was specified
                    if 'FS' in m:
                        roi_name = m.split('FS-')[1]
                        roi_file = glob.glob(op.join(projDir, 'files', 'ROIs' , '{}'.format(roi_name), '{}_*_{}.nii.gz'.format(sub, roi_name)))#[0]
                        roi_masks.append(roi_file)
                        print('Using {} FreeSurfer defined file from {}'.format(roi_name, roi_file))  
                    
                    # if an anatomical ROI was specified
                    elif 'aROI' in m:
                        if not aroi_prefix: # resultsDir:
                            print('ERROR: unable to locate aROI file. Make sure a resultsDir is provided in the config file!')
                        else:
                            roi_name = m.split('aROI-')[1].split('_')[0]
                            roi_file = glob.glob(op.join('{}*{}*.nii.gz'.format(aroi_prefix, roi_name)))#[0]
                            roi_masks.append(roi_file)
                            print('Using {} aROI file from {}'.format(roi_name, roi_file))  
                    
                    # if other ROI was specified
                    else:
                        if template is not None:
                            template_name = template.split('_')[0] # take full template name
                            roi_file = glob.glob(op.join(sharedDir, 'ROIs', '{}'.format(template_name), '{}_*.nii.gz'.format(m)))[0]
                        else:
                            roi_file = glob.glob(op.join(sharedDir, 'ROIs', '{}_*.nii.gz'.format(m)))[0]
                        
                        roi_masks.append(roi_file)
                        print('Using {} ROI file from {}'.format(m, roi_file)) 
            
            print('Model directory: {}'.format(modelDir))
            
            # for each ROI search space
            for r, roi in enumerate(roi_masks):
                
                # initialise the pattern variable for this ROI
                roi_patterns = []
                
                # load and binarize mni file
                mni_img = image.load_img(mni_file)
                mni_bin = mni_img.get_fdata() # get image data (as floating point data)
                mni_bin[mni_bin >= 1] = 1 # for values equal to or greater than 1, make 1 (values less than 1 are already 0)
                mni_bin = image.new_img_like(mni_img, mni_bin) # create a new image of the same class as the initial image
                
                # load roi mask
                mask_img = image.load_img(roi)
                mask_bin = mask_img.get_fdata()
                
                # ensure that mask/ROI is binarized
                mask_bin[mask_bin >= 1] = 1 # for values equal to or greater than 1, make 1 (values less than 1 are already 0)
                mask_bin = image.new_img_like(mask_img, mask_bin) # create a new image of the same class as the initial image
                
                # extract file name
                roi_name = str(roi).replace('/','-').split('-')[-1]                    
                roi_name = roi_name.split('.nii')[0]
                
                print('Extracting stats from {}'.format(roi_name))
                
                # the masks should already be resampled, but check if this is true and resample if not
                if mni_img.shape[0:3] != mask_bin.shape[0:3]:
                    print('WARNING: the search space provided has different dimensions than the functional data!')
                    
                    # make directory to save resampled rois
                    roiDir = op.join(resultsDir, 'resampled_rois')
                    os.makedirs(roiDir, exist_ok=True)
                    
                    resampled_file = op.join(roiDir, '{}_resampled.nii.gz'.format(roi_name))
                    
                    # check if file already exists
                    if os.path.isfile(resampled_file):
                        print('Found previously resampled {} ROI in output directory'.format(roi_name[r]))
                        mask_bin = image.load_img(resampled_file)
                    else:
                        # resample image
                        print('Resampling {} search space to match functional data'.format(roi_name[r]))
                        mask_bin = image.resample_to_img(mask_bin, mni_img, interpolation='nearest')
                        mask_bin.to_filename(resampled_file)
                
                masker = NiftiMasker(mask_img=mask_bin)
                
                # for each item/condition
                for c in conditions:
                    print('Extracting t-stats from {} condition'.format(c))
                
                    # extract mask name in a format that will match contrast naming
                    if 'fROI' in mask_opts[r]:
                        mask_name = mask_opts[r].split('-')[1].lower()
                    else:
                        mask_name = mask_opts[r]
                    
                    if 'aROI' in mask_opts[r]:
                        mask_name = mask_opts[r].split('-')[1].lower()
                    else:
                        mask_name = mask_opts[r]
                    
                    # t-stats copes file
                    tcope_file = glob.glob(op.join(modelDir, '*_{}_tstat.nii.gz'.format(c)))[0]
                    tcope_img = image.load_img(tcope_file)
                    
                    # squeeze the statistical map to remove the 4th singleton dimension if using anatomical/atlas ROI
                    # this dimension is not adding any information, so this is fine to do; the 3D map of stats values is preserved.
                    # this step isn't necessary for fROIs because they were defined using the functional data and also have a 4th singleton dimension
                    if not 'fROI' in mask_opts[r] and not 'FS' in mask_opts[r] and not 'aROI' in mask_opts[r]:
                        tcope_img = image.math_img('np.squeeze(img)', img=tcope_img)
                        
                    # extract t-stats vector of voxel values
                    # mask condition image with roi image and return 2D array
                    tvec = masker.fit_transform(tcope_img).squeeze()
                    
                    # add the pattern for this condition to the patterns variable for this roi
                    roi_patterns.append(tvec)
                
                # save condition vectors for this ROI
                save_patterns(sub, task, roi_patterns, mask_name, run_id, splithalf_id, conditions, vectorsDir)
                
                # store the condition vectors for this ROI and run/fold for RDM calculation
                patterns[(mask_name, run_id, splithalf_id)] = np.array(roi_patterns)
                
    # calculate dissimilarity across runs/folds (or within a run/fold)
    calc_dissimilarity(sub, task, patterns, conditions, rdmDir, normalise)
            
# define function to wrangle and save run/fold RDM data into a useable csv format
def save_patterns(sub, task, patterns, mask_name, run_id, splithalf_id, conditions, vectorsDir):
    patterns = np.array(patterns)
    print('Shape of extracted vector data (conditions x voxels): {}'.format(patterns.shape))
    
    rows = []
    for c, cond in enumerate(conditions):
        if splithalf_id !=0:
            row = {'sub': sub,
                   'fold': run_id,
                   'splithalf': splithalf_id,
                   'condition': cond,
                   'ROI': mask_name}
            vector_file = op.join(vectorsDir, '{}_task-{}_fold-{}_splithalf-{}_{}_condition_vectors.csv'.format(sub, task, run_id, splithalf_id, mask_name))
        else:
            row = {'sub': sub,
                   'fold': run_id,
                   'condition': cond,
                   'ROI': mask_name}
            vector_file = op.join(vectorsDir, '{}_task-{}_fold-{}_{}_condition_vectors.csv'.format(sub, task, run_id, mask_name))
            
        # add voxel values
        voxels = patterns[c]
        for v, vox in enumerate(voxels):
            row['vox_{}'.format(v)] = vox
        
        rows.append(row)
                
    df = pd.DataFrame(rows)
    df.to_csv(vector_file, sep=',', index=False)        
    print('Patterns saved to {}'.format(vectorsDir))  
    
# define function to calculate dissimilarity metrics
def calc_dissimilarity(sub, task, patterns, conditions, rdmDir, normalise):
    
    # extract info saved in patterns
    rois = sorted(set(r[0] for r in patterns))
    folds = sorted(set(f[1] for f in patterns))
    splits = sorted(set(s[2] for s in patterns))
    
    # STEP 1: calc RDM for each ROI
    # initalise output
    rdms = {}
    
    # loop over ROIs
    for roi in rois:
        
        # initalise output for this ROI
        rdms[roi] = {}
        
        # scenario 1: multiple runs/folds - compute RDMs across runs/folds 
        if len(folds) > 1: 
            for i, fold1 in enumerate(folds):
                for fold2 in folds[i+1:]:
                                    
                    A = patterns[(roi, fold1, splits[0])]
                    B = patterns[(roi, fold2, splits[0])]
                    
                    # compute the correlation distance (1-correlation) and euclidean distance 
                    rdms[roi][('fold', fold1, fold2)] = {'correlation': cdist(A, B, metric='correlation'),
                                                         'euclidean': cdist(A, B, metric='euclidean')}

                    rdms[roi][('fold', fold2, fold1)] = {'correlation': cdist(B, A, metric='correlation'),
                                                         'euclidean': cdist(B, A, metric='euclidean')}
                                                         
        # scenario 2: one run + splithalves - compute RDMs across splithalves
        elif len(splits) > 1:
            run = folds[0]
            
            # loop over splithalves
            for split1 in splits:
                for split2 in splits:

                    if split1 == split2:
                        continue

                    A = patterns((roi, run, split1))
                    B = patterns((roi, run, split2))
                    
                    # compute the correlation distance (1-correlation) and euclidean distance
                    rdms[roi][('split', split1, split2)] = {'correlation': cdist(A, B, metric='correlation'),
                                                            'euclidean': cdist(A, B, metric='euclidean')}
                    rdms[roi][('split', split2, split1)] = {'correlation': cdist(B, A, metric='correlation'),
                                                            'euclidean': cdist(B, A, metric='euclidean')}
                                                            
        # scenario 3: one run + no splithalves - compute RDMs within run (probably a bad idea!)
        else:
            run = folds[0]
            split = splits[0]
            
            A = patterns((roi, run, split))
            
            # compute the correlation distance (1-correlation) and euclidean distance
            # pdist is for pairwise comparisons which is why it's used in the within run case
            rdms[roi][('within_run', run)] = {'correlation': squareform(pdist(A, metric='correlation')),
                                              'euclidean': squareform(pdist(A, metric='euclidean'))}
    
    # STEP 2: normalise RDMs if requested
    # initalise output
    norm_rdms = {}
    if normalise == 'yes':
        # loop over ROIs
        for roi in rdms:
            # initalise output for this ROI
            norm_rdms[roi] = {}
            
            # for each comparison (e.g., fold: 1,2)
            for comp in rdms[roi]:
                norm_rdms[roi][comp] = {}
                
                # for each metric (correlation, euclidean)
                for metric in rdms[roi][comp]:
                    rdm = rdms[roi][comp][metric]
                    rdm_norm = normalise_rdm(rdm, roi, comp, metric)
                    norm_rdms[roi][comp][metric] = rdm_norm
                    
        # overwrite rdms with normalised rdms
        rdms = norm_rdms
        
    # STEP 3: average RDMs
    avg_rdms = average_rdms(rdms)
    
    # STEP 4: save RDMs
    save_rdms(sub, task, conditions, rdmDir, rdms, avg_rdms, normalise)

#define function to normalise RDMs
def normalise_rdm(rdm, roi, comp, metric):
    
    # calculate min, max, and range for normalisation
    rdm_min = np.min(rdm)
    rdm_max = np.max(rdm)
    rdm_range = (rdm_max - rdm_min)
    
    print('Normalising {} RDM for {} comparison {} by subtracting the minimum value, {}, and dividing by the range, {}'.format(metric, roi, comp, rdm_min, rdm_range))
    
    # normalise RDM
    norm_rdm = (rdm - rdm_min) / (rdm_range)
    
    return norm_rdm

#define function to average RDMs  
def average_rdms(rdms):
    
    # initalise output
    avg_rdms = {}

     # loop over ROIs
    for roi in rdms:
        # initalise output for this ROI
        avg_rdms[roi] = {}
        
        # get metrics for this ROI (should be 'correlation', 'euclidean')
        metrics = list(next(iter(rdms[roi].values())).keys())
        
        for metric in metrics:
            print('Averaging {} RDMs for {}'.format(metric, roi))
            
            # collect all RDMs for this metric
            all_rdms = []
            for comp in rdms[roi]:
                all_rdms.append(rdms[roi][comp][metric])
            
            # average elementwise
            avg_rdms[roi][metric] = np.mean(all_rdms, axis=0)
    
    return avg_rdms

# define function to save RDMs
def save_rdms(sub, task, conditions, rdmDir, rdms, avg_rdms, normalise):

    # loop over ROIs
    for roi in rdms:

        # save RDMs for each run/fold/splithalf
        for comp in rdms[roi]:
        
            # determine label
            if comp[0] == 'within_run':
                label = 'within_run-{}'.format(comp[1])
            elif comp[0] == 'fold':
                label = 'fold-{}vs{}'.format(comp[1], comp[2])
            elif comp[0] == 'split':
                label = 'split-{}vs{}'.format(comp[1], comp[2])

            for metric in rdms[roi][comp]:
                rdm = rdms[roi][comp][metric]
                df = pd.DataFrame(rdm, index=conditions, columns=conditions)
                if normalise == 'yes':
                    rdm_file = op.join(rdmDir, '{}_{}_{}_{}_normalised_rdm.csv'.format(sub, roi, label, metric))
                    print('Saved normalized RDM: {}'.format(rdm_file))
                else:
                    rdm_file = op.join(rdmDir, '{}_{}_{}_{}_rdm.csv'.format(sub, roi, label, metric))
                    print('Saved RDM: {}'.format(rdm_file))
                df.to_csv(rdm_file, index=False)
                
        # save averaged RDMs across runs/folds/splithalves
        for metric in avg_rdms[roi]:
            rdm_avg = avg_rdms[roi][metric]
            df_avg = pd.DataFrame(rdm_avg, index=conditions, columns=conditions)
            rdm_avg_file = op.join(rdmDir, '{}_{}_{}_averaged_rdm.csv'.format(sub, roi, metric))
            df_avg.to_csv(rdm_avg_file, index=False)
            print('Saved averaged RDM: {}'.format(rdm_avg_file))

# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-p', dest='projDir',
                        help='Project directory')
    parser.add_argument('-o', dest='outDir', default=os.getcwd(),
                        help='Output directory')
    parser.add_argument('-s', dest='subjects', nargs='*',
                        help='List of subjects to process (default: all)')
    parser.add_argument('-r', dest='runs', nargs='*',
                        help='List of runs for each subject')    
    parser.add_argument('-c', dest='config',
                        help='Configuration file')                                            
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
    froiDir=config_file.loc['froiDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    task=config_file.loc['task',1]
    folds=config_file.loc['folds',1]
    splithalf=config_file.loc['splithalf',1]
    conditions=config_file.loc['events',1].replace(' ','').split(',')
    mask_opts=config_file.loc['mask',1].replace(' ','').split(',')
    template=config_file.loc['template',1]
    normalise=config_file.loc['normalise_rdm',1]
    
    # lowercase conditions to avoid case errors - allows flexibility in how users specify events in config and contrasts files
    conditions = [c.lower() for c in conditions]
    
    if splithalf == 'yes':
        splithalves = [1,2]
    else:
        splithalves = [0]

    # print if results directory is not specified or found
    if resultsDir == None:
        raise IOError('No resultsDir was specified in config file, but is required to compute neural RDMs!')
    
    if not op.exists(resultsDir):
        raise IOError('Results directory {} not found.'.format(resultsDir))
        
    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        print('Computing neural RDMs for {}'.format(sub))
        
        # check that run info was provided in subject list, otherwise throw an error
        if not args.runs:
            raise IOError('Run or fold information missing. Make sure you are passing a subject-run or subject-fold list to the pipeline!')
            
        # pass runs for this sub
        sub_runs=args.runs[index]
        sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
        sub_runs=list(map(int, sub_runs)) # convert to integers
        
        # if only 1 run/fold was provided
        if splithalf == 'no' and len(sub_runs) == 1:
            print('Only 1 run or fold was specified, so neural RDMs will be computed on a single estimate.')
        else:
            print('Multiple runs or folds were specified, so neural RDMs will be combined across runs/folds.')
            
        # create a process_subject workflow with the inputs defined above
        generate_rdm(args.projDir, sharedDir, resultsDir, froiDir, sub, task, sub_runs, folds, splithalves, conditions, mask_opts, template, normalise)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()
    