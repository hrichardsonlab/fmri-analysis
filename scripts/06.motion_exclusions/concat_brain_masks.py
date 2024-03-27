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
# inputs: derivatives directory, subject, session
def concat_masks(derivDir, sub, ses=None): 
    # print current subject
    print('concatenating BOLD masks for ', sub)
    
    # define output filename and path, depending on whether session information is in BIDS directory/file names
    if ses: 
        # define path to inputs (subjects preprocessed functional data)
        subDir = op.join(derivDir, sub, 'ses-' + ses, 'func')
        concat_img_fname = '{}/{}_ses-{}_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(subDir, sub, ses)
    else: 
        # define path to inputs (subjects preprocessed functional data)
        subDir = op.join(derivDir, sub, 'func')
        concat_img_fname = '{}/{}_MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(subDir, sub)
    
    # identify all mask files (there should be 1 per functional run)
    maskfiles = glob.glob(op.join(subDir, '*MNI152NLin2009cAsym_res-2_desc-brain_mask.nii.gz'))  

    # if no mask files were found
    if len(maskfiles) == 0:
        print('No brain masks found for ', sub)
    # if mask files were found
    else:
        basemask = maskfiles[0] # take the first mask file as the base image
        basemask_img = image.load_img(basemask) # load the base mask image
        concat_mask_img = basemask_img # create the concatenated mask as a copy of the base mask image
        
        # if there are more than 1 mask files
        if len(maskfiles) > 1:
            # for each mask file (skipping the base mask, 0)
            for maskI in range(1, len(maskfiles)):
                # load the mask file
                mask_img = image.load_img(maskfiles[maskI])
                # add the mask file to the concatenated mask
                concat_mask_img = image.math_img("img1 + img2", img1 = concat_mask_img, img2 = mask_img)

        # binarize the concatenated mask file
        concat_mask_data = concat_mask_img.get_fdata() # get image data (as floating point data)
        concat_mask_data[concat_mask_data >= 1] = 1 # for values equal to or greater than 1, make 1 (values less than 1 are already 0)
        concat_mask_img_bin = image.new_img_like(basemask_img, concat_mask_data) # create a new image of the same class as the base mask image
        
        concat_mask_img_bin.to_filename(concat_img_fname)
        print('concatenated mask saved to: {}'.format(concat_img_fname))

# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument("-f", dest="derivDir",
                        help="Output directory of fmriprep")
    parser.add_argument("-s", dest="sub",
                        help="subject ID")                
    parser.add_argument("-ss", dest="ses", default=None,
                        help="Session to process (default: None)")
    return parser

# define function that checks inputs against parser function
def main(argv=None):
    parser = argparser()
    args = parser.parse_args(argv)
    
    # print if the fMRIPrep directory is not found
    if not op.exists(args.derivDir):
        raise IOError("fMRIprep directory {} not found.".format(args.derivDir))
    
    # run concat_masks function with different inputs depending on what was passed to the parser function
    if not args.ses == None: # if session argument was passed, pass to function
        concat_masks(args.derivDir, args.sub, args.ses) 
    else: # if no session argument was passed, leave session argument as default (FALSE)
        concat_masks(args.derivDir, args.sub)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == "__main__":
    main()
