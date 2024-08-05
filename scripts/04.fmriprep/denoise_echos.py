# import modules
from nipype import Workflow, Node
from tedana import workflows
from multiprocessing import Pool
#from nipype.interfaces.ants import ApplyTransforms
import nibabel as nib
import os.path as op
import pandas as pd
import numpy as np
import argparse
import shutil
import glob
import json
import os
import re

# define function that will extract echo information and run tedana
def denoise_echoes(sub, session, bidsDir, derivDir, cores):
    # print current subject
    print('Denoising and optimally combining data for sub-{}'.format(sub))
    
    # grab echo files
    if session == 'yes':
        sub_prefix = glob.glob(op.join(derivDir, 'sub-{}'.format(sub), 'ses-01'))
    else:
        sub_prefix = glob.glob(op.join(derivDir, 'sub-{}'.format(sub)))
        
    echo_imgs = glob.glob(op.join(sub_prefix, 'func', '*_echo-*_bold.nii.gz'))
        
    # extract file prefixes before echoes (i.e., individual runs)
    prefix_list = [re.search('(.*)_echo-',f).group(1) for f in echo_imgs]
    prefix_list = set(prefix_list)
    
    # make a dataframe with sub, inputFiles, and echo times
    dat = []
    for run in prefix_list: # for each run
        # extract task and run info
        task = re.search('task-(.*)', run).group(1)

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
            
            img = glob.glob(op.join(sub_prefix, 'func', '{}_echo-{}_desc-preproc_bold.nii.gz'.format(run, echo_num)))
            
            # add TR info to header
            tr = rep_time # the TR that the data should have in seconds
            #output_image = op.join(sub_prefix, 'func', '{}_echo-{}_desc-preproc_bold-TR.nii.gz'.format(run, echo_num))
            img_dat = nib.load(img[0])
            zooms = img_dat.header.get_zooms()
            new_zooms = (zooms[0], zooms[1], zooms[2], tr)
            img_dat.header.set_zooms(new_zooms)
            nib.save(img_dat, img[0])
            
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

        # define output directory
        os.makedirs(op.join(sub_prefix, 'func', 'tedana'), exist_ok=True)
        outDir = op.join(sub_prefix, 'func', 'tedana/{}'.format(task))

        # save files and outDir to dat
        dat.append([sub, task, run_imgs, echo_times, outDir])
    
    print('Outputs will be saved to {}'.format(outDir))
    tedana_df = pd.DataFrame(data=dat, columns=['sub', 'task', 'EchoFiles', 'EchoTimes', 'outDir'])
    args=zip(tedana_df['sub'].tolist(),
             tedana_df['task'].tolist(),
             tedana_df['EchoFiles'].tolist(),
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
def call_tedana(sub, task, EchoFiles, EchoTimes, outDir):
    if os.path.isdir(outDir): # if subject tedana files already exist
        print('skipping tedana because tedana outputs found for sub-{}'.format(sub))

    else: # if subject tedana files don't exist
        # for more info: https://tedana.readthedocs.io/en/stable/generated/tedana.workflows.tedana_workflow.html
        workflows.tedana_workflow(EchoFiles, 
                                  EchoTimes,
                                  out_dir = outDir,
                                  prefix = 'sub-{}_task-{}_space-native'.format(sub, task),
                                  fittype = 'curvefit',
                                  tedpca = 'kic',
                                  overwrite = True,
                                  gscontrol = None) 

# def normalize_data(denoised_img, reference_img, native_T1w_transform, T1w_MNI_transform):
    # # extract file prefix from img for naming outputs
    # img_prefix = re.search('(.*)-native', denoised_img).group(1)
    # normalized_img = op.join('{}-MNI152NLin2009cAsym_res-2_desc-denoised_bold.nii.gz'.format(img_prefix))

    # if os.path.isfile(normalized_img): # if output file already exists
        # print('Skipping normalization because normalized outputs found for sub-{}'.format(sub))
        
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