# import modules
#from nipype.interfaces.ants import ApplyTransforms
import glob
import json
import re
import os
import os.path as op
import pandas as pd
import numpy as np
import argparse
import shutil
import subprocess
import nibabel as nib
from tedana import workflows
from multiprocessing import Pool
from nilearn import image
from nilearn.image import resample_to_img, math_img, load_img

# define function that will extract echo information and run tedana
def denoise_echoes(sub, session, bidsDir, derivDir, cores):
    # define subject files prefix based on whether session information is used
    if session == 'yes':
        sub_prefix = op.join(derivDir, '{}'.format(sub), 'ses-01')
    else:
        sub_prefix = op.join(derivDir, '{}'.format(sub))
    
    # grab grey and white matter mask files (we want to use native space files, not MNI files)
    gm_mask = glob.glob(op.join(sub_prefix, 'anat', '{}*_label-GM_probseg.nii.gz'.format(sub)))
    wm_mask = glob.glob(op.join(sub_prefix, 'anat', '{}*_label-WM_probseg.nii.gz'.format(sub)))
    
    # remove MNI space masks
    gm_mask = [m for m in gm_mask if 'MNI' not in m][0]
    wm_mask = [m for m in wm_mask if 'MNI' not in m][0]
    
    # confirm that masks were found
    if len(gm_mask) == 0 or len(wm_mask) == 0:
        print('No brain masks found for {}'.format(sub))
    
    # grab echo bold files
    echo_imgs = glob.glob(op.join(sub_prefix, 'func', '*_echo-*_bold.nii.gz'))
    
    # extract file prefixes before echoes (i.e., individual runs)
    prefix_list = [re.search('(.*)_echo-',f).group(1) for f in echo_imgs]
    prefix_list = set(prefix_list)
    
    # loop through each unique task/run
    dat = []
    for run in prefix_list:
        # extract task and run info
        task = re.search('task-(.*)', run).group(1)
        
        # make tedana output directory
        outDir = op.join(sub_prefix, 'func', 'tedana/{}'.format(task))
        os.makedirs(outDir, exist_ok=True)
        
        # grab bold and mask file
        bold_file = glob.glob(op.join('{}_echo-*1_desc-preproc_bold.nii.gz'.format(run)))[0]
        bold_mask = op.join('{}_desc-brain_mask.nii.gz'.format(run))
        bold_t1w_mask = op.join('{}_space-T1w_desc-brain_mask.nii.gz'.format(run))
        
        # dilate the bold mask to ensure coverage of whole brain
        dilated_mask_file = op.join(outDir, '{}_task-{}_desc-dilated_brain_mask.nii.gz'.format(sub, task))
        print('Generating and saving dilated BOLD mask: {}'.format(dilated_mask_file))
        cmd = 'fslmaths ' + bold_mask + ' '
        cmd = cmd + '-dilM -bin ' + dilated_mask_file
        result = subprocess.run(cmd, stdout=subprocess.PIPE, shell = True)
             
        # combine subject grey and white matter native space mask with BOLD mask in T1w space
        print('Combining grey and white matter masks for: {}'.format(run))
        
        gm_resampled = resample_to_img(gm_mask, bold_t1w_mask, interpolation='nearest')
        wm_resampled = resample_to_img(wm_mask, bold_t1w_mask, interpolation='nearest')
        
        # threshold and binarize gm and wm masks
        gm_bin = math_img('img > 0.1', img = gm_resampled)
        wm_bin = math_img('img > 0.1', img = wm_resampled)
        
        # combine masks
        gmwm_img = image.math_img('img1 + img2', img1 = gm_bin, img2 = wm_bin)
        
        # binarize mask
        gmwm_bin = image.math_img('img > 0', img = gmwm_img)
        
        # load and binarize bold masks
        bold_bin = image.math_img('img > 0', img = bold_mask)
        bold_t1w_bin = image.math_img('img > 0', img = bold_t1w_mask)
        
        # combine bold and gmwm masks
        combined_mask = image.math_img('img1 + img2', img1 = gmwm_bin, img2 = bold_t1w_bin)
        
        # binarize combined mask
        combined_mask = image.math_img('img > 0', img = combined_mask)
        
        # save masks
        mask_file = op.join(sub_prefix, 'func', '{}_task-{}_space-T1w_desc-gmwmbold_mask.nii.gz'.format(sub, task))
        combined_mask.to_filename(mask_file)
        print('Combined grey matter, white matter, bold mask saved to: {}'.format(mask_file))
        
        print('Denoising and optimally combining data for: {}'.format(run))
        
        # grab the json files with appropriate header info
        header_info = glob.glob(op.join(sub_prefix, 'func', '{}*_echo-*desc-preproc_bold.json'.format(run)))
        
        # extract echo times out of header info and sort
        echo_times = [json.load(open(f))['EchoTime'] for f in header_info]
        echo_times.sort()
        
        # extract TR
        rep_time = [json.load(open(f))['RepetitionTime'] for f in header_info][0]

        # grab images matching the appropriate run prefix
        run_list = []
        for echo in header_info:
            # extract echo number
            echo_num = re.search('echo-(.*)_desc', echo).group(1)
            
            # grab echo file
            img = glob.glob(op.join(sub_prefix, 'func', '{}_echo-{}_desc-preproc_bold.nii.gz'.format(run, echo_num)))
            
            # add TR info to header
            tr = rep_time # the TR that the data should have in seconds
            img_dat = nib.load(img[0])
            zooms = img_dat.header.get_zooms()
            new_zooms = (zooms[0], zooms[1], zooms[2], tr)
            img_dat.header.set_zooms(new_zooms)
            nib.save(img_dat, img[0])
            
            # add run to run_list
            run_list.append(img)
        
        run_list.sort()
        
        # remove nested lists if present
        run_imgs = []
        for element in run_list:
            if type(element) is list:
                for item in element:
                    run_imgs.append(item)
            else:
               run_imgs.append(element)
               
        # make a dataframe with sub, input files, and echo times
        dat.append([sub, task, run_imgs, dilated_mask_file, echo_times, outDir])
    
        print('Outputs will be saved to {}'.format(outDir))
        tedana_df = pd.DataFrame(data=dat, columns=['sub', 'task', 'EchoFiles', 'MaskFile', 'EchoTimes', 'outDir'])
        args=zip(tedana_df['sub'].tolist(),
                 tedana_df['task'].tolist(),
                 tedana_df['EchoFiles'].tolist(),
                 tedana_df['MaskFile'].tolist(),
                 tedana_df['EchoTimes'].tolist(),
                 tedana_df['outDir'].tolist())
             
        # run tedana
        pool = Pool(cores)
        results = pool.starmap(call_tedana, args)
    
    # the code below is used to normalized the denoised optimally combined tedana outputs to MNI space using the tranform files output by fMRIPrep. The version of ants available in the nipype singularity can't read these files however, so the code is commented out (more here: https://github.com/nipreps/fmriprep/issues/2756).
    
    # grab normalized anat transform file
    # T1w_MNI_transform = glob.glob(op.join(sub_prefix, 'anat', '*from-T1w_to-MNI152NLin2009cAsym_mode-image_xfm.h5'))[0]
        
    # # grab denoised and transform files
    # for run in prefix_list: # for each run
        # # extract task and run info
        # task = re.search('task-(.*)', run).group(1)
    
        # denoised_img = glob.glob(op.join(sub_prefix, 'func', 'tedana/{}/'.format(task), '*_desc-denoised_bold.nii.gz'))[0]
        # reference_img = glob.glob(op.join(sub_prefix, 'func', '*task-{}*MNI152NLin2009cAsym_res-2_boldref.nii.gz'.format(task)))[0]
        # native_T1w_transform = glob.glob(op.join(sub_prefix, 'func', '*task-{}*from-boldref_to-T1w_mode-image_desc-coreg_xfm.txt'.format(task)))[0]
        
        # # normalize denoised tedana outputs
        # normalize_data(denoised_img, reference_img, native_T1w_transform, T1w_MNI_transform)

# define function to pass to multiprocess 
def call_tedana(sub, task, EchoFiles, MaskFile, EchoTimes, outDir):
    print(op.join(outDir, '{}_task-{}_tedana_report.html'.format(sub, task)))
    if os.path.isfile(op.join(outDir, '{}_task-{}_tedana_report.html'.format(sub, task))): # if subject tedana report already exists
        print('Skipping tedana because tedana outputs found for {}'.format(sub))
        
    else: # if subject tedana files don't exist
        # for more info: https://tedana.readthedocs.io/en/stable/generated/tedana.workflows.tedana_workflow.html
        print('Echo Times: {}'.format(EchoTimes))
        
        workflows.tedana_workflow(EchoFiles, 
                                  EchoTimes,
                                  mask = MaskFile,
                                  out_dir = outDir,
                                  prefix = '{}_task-{}'.format(sub, task),
                                  fittype = 'curvefit',
                                  tedpca = 'aic', # default is aic (least aggressive), kic is a moderate option, mdl is an aggressive option
                                  ica_method = 'robustica',
                                  n_robust_runs = 35, # only applicable if robustica method is used; default is 30
                                  overwrite = True,
                                  gscontrol = None)

# def normalize_data(denoised_img, reference_img, native_T1w_transform, T1w_MNI_transform):
    # # extract file prefix from img for naming outputs
    # img_prefix = re.search('(.*)-T1w', denoised_img).group(1)
    # normalized_img = op.join('{}-MNI152NLin2009cAsym_res-2_desc-denoised_bold.nii.gz'.format(img_prefix))

    # if os.path.isfile(normalized_img): # if output file already exists
        # print('Skipping normalization because normalized outputs found for {}'.format(sub))
        
    # else:
        # print('Normalizing tedana outputs')
    
        # # configure ants apply transform call
        # at = ApplyTransforms()
        # at.inputs.input_image = denoised_img
        # at.inputs.input_image_type = 3
        # at.inputs.reference_image = reference_img
        # #at.inputs.float = True
        # at.inputs.output_image = normalized_img
        # at.inputs.transforms = [ native_T1w_transform, T1w_MNI_transform ]
        # at.inputs.interpolation = 'LanczosWindowedSinc'
        # at.cmdline  
        # at.run()

# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-s', dest='subjects', nargs='*',
                        help='List of subjects to process (default: all)')
    parser.add_argument('-n', dest='session', nargs='*',
                        help='Whether data are organized into session folders')                       
    parser.add_argument('-b', dest='bidsDir',
                        help='BIDS directory')                       
    parser.add_argument('-d', dest='derivDir', default=os.getcwd(),
                        help='derivatives directory')  
    parser.add_argument('-c', dest='cores',
                        help='number of cores')                                
    return parser

# define function that checks inputs against parser function
def main(argv=None):
    # call argparser function that defines command line inputs
    parser = argparser()
    args = parser.parse_args(argv)

    # print if the project directory is not found
    if not op.exists(args.derivDir):
        raise IOError('derivatives directory {} not found.'.format(args.derivDir))
    
    # print if the project directory is not found
    if not op.exists(args.bidsDir):
        raise IOError('BIDS directory {} not found.'.format(args.bidsDir))

    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        # run denoise_echos workflow with the inputs defined above
        denoise_echoes(sub, args.session, args.bidsDir, args.derivDir, int(args.cores))
        
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()