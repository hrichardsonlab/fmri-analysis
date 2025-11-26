"""
Identify, convert, and mask Freesurfer outputs

The results are saved in the ROIs folder in the project directory

"""
import nilearn
from nilearn import image
import nibabel as nib
from nipype.interfaces.freesurfer import MRIConvert
import os
import os.path as op
import numpy as np
import argparse
import pandas as pd
import glob
import shutil

# define first level workflow function
def process_roi(projDir, derivDir, ses, sub, FS_ROI):

    # define directories
    fsDir = op.join(derivDir, 'sourcedata/freesurfer')
    subDir = op.join(derivDir, 'sourcedata/freesurfer/{}/mri'.format(sub))
    roiDir = op.join(projDir, 'files/ROIs')
    
    # define func directory, depending on whether session information is in directory/file names
    if ses != 'no': # if session was provided
        funcDir = op.join(derivDir, '{}'.format(sub), 'ses-{}'.format(ses), 'func')
    else:
        funcDir = op.join(derivDir, '{}'.format(sub), 'func')
    
    # check that fsDir directory exists
    if not op.exists(fsDir):
        raise IOError('FreeSurfer directory {} not found.'.format(fsDir))
    
    # make roi directory if it doesn't exist
    os.makedirs(roiDir, exist_ok=True)

    # grab functional data file (grabs the first one because all that matters is the dimensions of the data)
    func_file = glob.glob(op.join(funcDir, '{}_*_space-T1w_desc-preproc_bold.nii.gz'.format(sub)))[0]
    func_img = image.load_img(func_file)
    print('ROIs will be resampled to match dimensions of functional data: {}'.format(func_file ))

    # grab freesurfer file for conversion to nifti
    mgz_file = op.join(subDir, 'aparc+aseg.mgz')
    nii_file = op.join(roiDir, '{}_space-T1w_aparc+aseg.nii.gz'.format(sub))
    
    # grab look up table to derive index matching specified ROI
    lut_file = op.join(fsDir, 'desc-aparcaseg_dseg.tsv')
    lut = pd.read_csv(lut_file, sep='\t')
    
    # lowercase ROI name column to avoid case errors
    lut['name'] = lut['name'].str.lower()

    # setup mgz to nii conversion
    mc = MRIConvert()
    mc.inputs.in_file = mgz_file
    mc.inputs.out_file = nii_file
    mc.inputs.out_type = 'niigz'

    # run the conversion
    print('Converting subject parcellation and segmentation file to nifti format: {}'. format(nii_file))
    mc.run()
    
    # load nifti file
    nii_img = nib.load(nii_file)
    nii_dat = nii_img.get_fdata()
    
    # for each ROI specified in config file
    for r, roi in enumerate(FS_ROI):
        # make roi directory if it doesn't exist
        fsroiDir = op.join(projDir, 'files/ROIs/{}'.format(roi))
        os.makedirs(fsroiDir, exist_ok=True)

        # filter the DataFrame and get the index value
        roi_index = lut.loc[lut['name'] == roi, 'index'].values[0]
        
        # check if an index value was found
        if roi_index > 0:
            print('Defining {} using {} index from look up table for {}'.format(roi, roi_index, sub))
        else:
            print('No match found in the look up table for {}'.format(roi))

        # mask file to only include roi index
        mask = np.isin(nii_dat, roi_index)
        mask_dat = np.where(mask, nii_dat, 0) # set all non roi voxels to 0
        mask_img = image.new_img_like(nii_img, mask_dat)
        
        # define output file
        roi_file = op.join(fsroiDir, '{}_space-T1w_{}.nii.gz'.format(sub, roi))

        # resample mask to match functional data
        roi_img = image.resample_to_img(mask_img, func_img, interpolation='nearest')
        roi_img.to_filename(roi_file)
        
    # delete native space aseg+aparc nifti file (could keep if desired)
    os.remove(nii_file)
    
    return

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
    
    # print if config file is not found
    if not op.exists(args.config):
        raise IOError('Configuration file {} not found. Make sure it is saved in your project directory!'.format(args.config))
    
    # read in configuration file and parse inputs
    config_file=pd.read_csv(args.config, sep='\t', header=None, index_col=0).replace({np.nan: None})
    derivDir=config_file.loc['derivDir',1]
    ses=config_file.loc['sessions',1]
    FS_ROI=list(set(config_file.loc['FS_ROI',1].replace(' ','').split(',')))
    
    # print if the fMRIPrep directory is not found
    if not op.exists(derivDir):
        raise IOError('Derivatives directory {} not found.'.format(derivDir))
    
    # lowercase ROI names to avoid case errors - allows flexibility in how users specify ROIs in config file
    FS_ROI = [r.lower() for r in FS_ROI]
    
    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
       # pass inputs defined above to ROI processing function
        process_roi(args.projDir, derivDir, ses, sub, FS_ROI)
   
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()