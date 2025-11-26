"""
Resample ROIs to match resolution of preprocessed functional data

This will often be the same template given that the lab uses the same template within fMRIPrep, 
but template option can be passed in the config file and will be used as long as it is saved in the
shared directory (/EBC/processing/templates) or in your project directory (<project directory>/files/templates)

"""
import nilearn
from nilearn import image
import os
import os.path as op
import numpy as np
import argparse
import pandas as pd
import glob
import shutil

# define first level workflow function
def resample_roi(projDir, roiDir, sharedDir, template):

    # define roi files in directory provided
    roi_files = glob.glob(op.join(roiDir, '*.nii*'))
    
    # grab template
    template_file = glob.glob(op.join(sharedDir, 'templates', '*{}*').format(template))
    
    # check projDir directory for template file if not in shared directory
    if not template_file:
        template_file = glob.glob(op.join(projDir, 'files', 'templates', '*{}*').format(template))
    
    # print if template file is not found
    if not template_file:
        raise IOError('{} template file not found. Make sure it is saved in the shared directory or your project directory!'.format(template))
    
    # extract template name
    #template_name = template[:6] # take first 6 characters
    template_name = template.split('_')[0] # take full name
    
    # load and binarize mni file
    template_img = image.load_img(template_file)
    
    # make template directory for resampled ROI files
    templateDir = op.join(roiDir, '{}'.format(template_name))
    os.makedirs(templateDir, exist_ok=True)
    
    # for each ROI in the resampleDir
    for m, roi in enumerate(roi_files):
        print('Resampling {} to {}'.format(roi, template))
        
        # extract file name
        roi_name = roi.replace('/','-').split('-')[-1]
        roi_name = roi_name.split('.nii')[0]

        # load roi mask
        mask_img = image.load_img(roi)
        
        # ensure that mask/ROI is binarized
        mask_bin = mask_img.get_fdata()
        mask_bin[mask_bin >= 1] = 1 # for values equal to or greater than 1, make 1 (values less than 1 are already 0)
        mask_bin = image.new_img_like(mask_img, mask_bin) # create a new image of the same class as the initial image        
        
        # resample roi mask to template space
        mask_bin_resampled = image.resample_to_img(mask_bin, template_img, interpolation='nearest')
        
        # save resampled roi file
        resampled_file = op.join(roiDir, '{}_{}.nii.gz'.format(roi_name, template_name)) # add template name to file       
        mask_bin_resampled.to_filename(resampled_file)
        
        # move resampled roi file to templateDir
        shutil.move(resampled_file, templateDir)
    
    return

# define command line parser function
def argparser():
    # create an instance of ArgumentParser
    parser = argparse.ArgumentParser()
    # attach argument specifications to the parser
    parser.add_argument('-p', dest='projDir',
                        help='Project directory')
    parser.add_argument('-c', dest='config',
                        help='Configuration file')                                            
    return parser

# define main function that parses the config file and runs the functions defined above
def main(argv=None):
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
    roiDir=config_file.loc['resampleDir',1]
    template=config_file.loc['template',1]
    
    # pass inputs defined above to main resampling function
    resample_roi(args.projDir, roiDir, sharedDir, template)
   
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()