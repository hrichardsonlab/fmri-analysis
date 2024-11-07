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
def process_roi(projDir, sharedDir, derivDir, sub, FS_ROI, template):

    # define directories
    fsDir = op.join(derivDir, 'sourcedata/freesurfer')
    subDir = op.join(derivDir, 'sourcedata/freesurfer/sub-{}/mri'.format(sub))
    roiDir = op.join(projDir, 'files/ROIs')
    
    # make roi directory if it doesn't exist
    os.makedirs(roiDir, exist_ok=True)

    # check that fsDir directory exists
    if not op.exists(fsDir):
        raise IOError('FreeSurfer directory {} not found.'.format(fsDir))
        
    # read in participant file
    mgz_file = op.join(subDir, 'aparc+aseg.mgz')
    nii_file = op.join(roiDir, 'sub-{}_space-native_aparc+aseg.nii.gz'.format(sub))
    
    # read in look up table to derive index matching specified ROI
    lut_file = op.join(fsDir, 'desc-aparcaseg_dseg.tsv')
    lut = pd.read_csv(lut_file, sep='\t')
    # lowercase ROI name column to avoid case errors
    lut['name'] = lut['name'].str.lower()
    
    # grab template
    if template != 'anat':
        print('ROIs will be resampled to match dimensions of specified template: {}'. format(template))
       
        # grab template
        template_file = glob.glob(op.join(sharedDir, 'templates', '*{}*').format(template))

        # check projDir directory for template file if not in shared directory
        if not template_file:
            template_file = glob.glob(op.join(projDir, 'files', 'templates', '*{}*').format(template))
        
        # extract template name
        #template_name = template[:6] # take first 6 characters
        template_name = template.split('_')[0] # take full name
    
        # load template file
        #template_img = nib.load(template_file[0])
        #template_dat = template_img.get_fdata()
        template_img = image.load_img(template_file[0])
    
    # mgz to nii conversion
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
            print('Defining {} using {} index from look up table for sub-{}'.format(roi, roi_index, sub))
        else:
            print('No match found')

        # mask file to only include roi index
        mask = np.isin(nii_dat, roi_index)
        mask_dat = np.where(mask, nii_dat, 0) # set all non roi voxels to 0
        
        # save native space mask file
        native_roi_file = op.join(fsroiDir, 'sub-{}_space-native_{}.nii.gz'.format(sub, roi))
        native_roi_img = image.new_img_like(nii_img, mask_dat)
        nib.save(native_roi_img, native_roi_file)

        # resample ROI it to match specified template if requested
        if template != 'anat':
            # load roi mask
            mask_img = image.load_img(native_roi_file)
            
            # define output file
            mni_roi_file = op.join(fsroiDir, 'sub-{}_space-{}_{}.nii.gz'.format(sub, template_name, roi))
            
            # resample roi mask to template space
            mni_roi_img = image.resample_to_img(mask_img, template_img, interpolation='nearest')
            mni_roi_img.to_filename(mni_roi_file)
            
            # delete native space ROI file (could keep if desired)
            os.remove(native_roi_file)
            
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
    sharedDir=config_file.loc['sharedDir',1]
    FS_ROI=list(set(config_file.loc['FS_ROI',1].replace(' ','').split(',')))
    template=config_file.loc['template',1]
    
    if not template:
        template = 'anat'
        print('No template specified in config file. ROIs will be saved in native T1w space.')
    
    # lowercase ROI names to avoid case errors - allows flexibility in how users specify events in config and contrasts files
    FS_ROI = [r.lower() for r in FS_ROI]
    
    # print if the fMRIPrep directory is not found
    if not op.exists(derivDir):
        raise IOError('Derivatives directory {} not found.'.format(derivDir))
    
    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
       # pass inputs defined above to ROI processing function
        process_roi(args.projDir, sharedDir, derivDir, sub, FS_ROI, template)
   
# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()