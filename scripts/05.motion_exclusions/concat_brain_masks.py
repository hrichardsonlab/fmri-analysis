# import modules
from nilearn import image
import nilearn
import argparse
import pandas as pd
import numpy as np
import os
import os.path as op
import glob

# define mask concatenation function
def concat_masks(derivDir, sub, ses): 
    # print current subject
    print('concatenating BOLD masks for sub-{}'.format(sub))
    
    # define output filename and path, depending on whether session information is in BIDS directory/file names
    if ses != 'no':
        print('Session information provided. Assuming data are organized into session folders.')
        
        # define path to inputs (subjects preprocessed functional data)
        subDir = op.join(derivDir, 'sub-{}'.format(sub), 'ses-{}'.format(ses), 'func')
        mni_img_fname = '{}/{}_ses-{}_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(subDir, sub, ses)
        t1w_img_fname = '{}/{}_ses-{}_space-T1w_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(subDir, sub, ses)
        
    else: # if session was 'no'
        # define path to inputs (subjects preprocessed functional data)
        subDir = op.join(derivDir, 'sub-{}'.format(sub), 'func')
        mni_img_fname = '{}/sub-{}_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(subDir, sub, ses)
        t1w_img_fname = '{}/sub-{}_space-T1w_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(subDir, sub, ses)
    
    # identify all mask files (there should be 1 per functional run)
    mni_maskfiles = glob.glob(op.join(subDir, '*MNI152NLin2009cAsym_res-2_desc-brain_mask.nii.gz'))  
    t1w_maskfiles = glob.glob(op.join(subDir, '*T1w_desc-brain_mask.nii.gz'))  

    # generate MNI mask
    if len(mni_maskfiles) == 0: # if no mask files were found
        print('No MNI space brain masks found for sub-{}'.format(sub))
    
    else: # if mni mask files were found
        mni_basemask = mni_maskfiles[0] # take the first mask file as the base image
        mni_basemask_img = image.load_img(mni_basemask) # load the base mask image
        mni_mask_img = mni_basemask_img # create the concatenated mask as a copy of the base mask image
        
        # if there are more than 1 mask files
        if len(mni_maskfiles) > 1:
            # for each mask file (skipping the base mask, 0)
            for maskI in range(1, len(mni_maskfiles)):
                # load the mask file
                mask_img = image.load_img(mni_maskfiles[maskI])
                # add the mask file to the concatenated mask
                mni_mask_img = image.math_img('img1 + img2', img1 = mni_mask_img, img2 = mask_img)

        # binarize the concatenated mask file
        mni_mask_data = mni_mask_img.get_fdata() # get image data (as floating point data)
        mni_mask_data[mni_mask_data >= 1] = 1 # for values equal to or greater than 1, make 1 (values less than 1 are already 0)
        mni_mask_img_bin = image.new_img_like(mni_basemask_img, mni_mask_data) # create a new image of the same class as the base mask image
        
        mni_mask_img_bin.to_filename(mni_img_fname)
        print('concatenated mask saved to: {}'.format(mni_img_fname))

    # generate T1w mask
    if len(t1w_maskfiles) == 0: # if no mask files were found
        print('No MNI space brain masks found for sub-{}'.format(sub))
    
    else: # if mni mask files were found
        t1w_basemask = t1w_maskfiles[0] # take the first mask file as the base image
        t1w_basemask_img = image.load_img(t1w_basemask) # load the base mask image
        t1w_mask_img = t1w_basemask_img # create the concatenated mask as a copy of the base mask image
        
        # if there are more than 1 mask files
        if len(t1w_maskfiles) > 1:
            # for each mask file (skipping the base mask, 0)
            for maskI in range(1, len(t1w_maskfiles)):
                # load the mask file
                mask_img = image.load_img(t1w_maskfiles[maskI])
                # add the mask file to the concatenated mask
                t1w_mask_img = image.math_img('img1 + img2', img1 = t1w_mask_img, img2 = mask_img)

        # binarize the concatenated mask file
        t1w_mask_data = t1w_mask_img.get_fdata() # get image data (as floating point data)
        t1w_mask_data[t1w_mask_data >= 1] = 1 # for values equal to or greater than 1, make 1 (values less than 1 are already 0)
        t1w_mask_img_bin = image.new_img_like(t1w_basemask_img, t1w_mask_data) # create a new image of the same class as the base mask image
        
        t1w_mask_img_bin.to_filename(t1w_img_fname)
        print('concatenated mask saved to: {}'.format(t1w_img_fname))

# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-s', dest='sub',
                        help='subject ID')
    parser.add_argument('-c', dest='config',
                        help='Configuration file')                                 
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

    # print if the fMRIPrep directory is not found
    if not op.exists(derivDir):
        raise IOError('Derivatives directory {} not found.'.format(derivDir))       
    
    # run concat_masks function with different inputs depending on config options
    concat_masks(derivDir, args.sub, ses)
    
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()
