"""
Individual run analysis using outputs from fMRIPrep

Adapted script from original notebook:
https://github.com/poldrack/fmri-analysis-vm/blob/master/analysis/postFMRIPREPmodelling/First%20and%20Second%20Level%20Modeling%20(FSL).ipynb

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page
Nesting of functions: main > argparser > process_subject > create_timecourse_workflow > data_grabber > process_data_files > denoise_data > extract_timecourse

Requirement: BIDS dataset (including events.tsv), derivatives directory with fMRIPrep outputs, and modeling files

"""
from nipype.interfaces import fsl
from nipype import Workflow, Node, IdentityInterface, Function, DataSink, JoinNode, MapNode
import nilearn
import os
import os.path as op
import numpy as np
import argparse
from bids.layout import BIDSLayout
from niflow.nipype1.workflows.fmri.fsl import create_susan_smooth
import pandas as pd
import glob
import shutil
from datetime import datetime

# define first level workflow function
def create_timecourse_workflow(sharedDir, projDir, derivDir, workDir, outDir, subDir, 
                               sub, task, ses, multiecho, runs, regressor_opts, mask_opts, smoothing_kernel_size, resultsDir, smoothDir, hpf, filter_opt, TR, detrend,standardize, template, extract_opt, dropvols, splithalves,
                               name='sub-{}_task-{}_timecourses'):
    """Processing pipeline"""

    # initialize workflow
    wf = Workflow(name=name.format(sub, task),
                  base_dir=workDir)
    
    # configure workflow
    # parameterize_dirs: parameterizations over 32 characters will be replaced by their hash; essentially prevented an issue of having too many characters in a file/folder name (i.e., https://github.com/nipy/nipype/issues/2061#issuecomment-1189562017)
    wf.config['execution']['parameterize_dirs'] = False

    infosource = Node(IdentityInterface(fields=['run_id', 'splithalf_id']), name='infosource')

    # define iterables to run nodes over runs and splithalves
    infosource.iterables = [('run_id', runs),
                            ('splithalf_id', splithalves)]
    infosource.synchronize = True
   
    # enable/disable smoothing based on value provided in config file
    if smoothing_kernel_size != 0: # if smoothing kernel size is not 0
        # use spatial smoothing
        run_smoothing = True
        print('Spatial smoothing will be run using a {}mm smoothing kernel.'.format(smoothing_kernel_size))
    else: 
        # don't do spatial smoothing
        run_smoothing = False
        print('Spatial smoothing will not be run.')
        
    # define data grabber function
    def data_grabber(sub, task, mask_opts, sharedDir, projDir, derivDir, resultsDir, smoothDir, subDir, template, dropvols, ses, multiecho, run_id, splithalf_id):
        """Quick filegrabber ala SelectFiles/DataGrabber"""
        import os
        import os.path as op
        import glob
        import shutil
        from nibabel import load

        # define output filename and path, depending on whether session information is in directory/file names
        if ses != 'no': # if session was provided
            # define path to preprocessed functional and mask data (subject derivatives func folder)
            prefix = 'sub-{}_ses-{}_task-{}'.format(sub, ses, task)
            funcDir = op.join(derivDir, 'sub-{}'.format(sub), 'ses-{}'.format(ses), 'func')
            mni_mask = op.join(funcDir, 'sub-{}_ses-{}_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub, ses))
            
        else: # if session was 'no'
            # define path to preprocessed functional and mask data (subject derivatives func folder)
            prefix = 'sub-{}_task-{}'.format(sub, task)
            funcDir = op.join(derivDir, 'sub-{}'.format(sub), 'func')
            mni_mask = op.join(funcDir, 'sub-{}_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub))
        
        # add run info to file prefix if necessary
        if run_id != 0:
            prefix = '{}_run-{:02d}'.format(prefix, run_id)
        
        # identify mni file based on whether data are multiecho
        if multiecho == 'yes': # if multiecho sequence, look for outputs in tedana folder
            mni_file = op.join(funcDir, 'tedana/{}'.format(task), '{}_space-MNI152NLin2009cAsym_res-2_desc-denoised_bold.nii.gz'.format(prefix))
            print('Will use multiecho outputs from tedana: {}'.format(mni_file))
        else:            
            mni_file = op.join(funcDir, '{}_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz'.format(prefix))

        # grab the confound, MNI, and rapidart outlier file
        confound_file = op.join(funcDir, '{}_desc-confounds_timeseries.tsv'.format(prefix))
        
        if run_id != 0: # if run info is in filename
            art_file = op.join(funcDir, 'art', '{}{:02d}'.format(task, run_id), 'art.{}_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold_outliers.txt'.format(prefix))
        else: # if no run info is in file name
            art_file = op.join(funcDir, 'art', '{}'.format(task), 'art.{}_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold_outliers.txt'.format(prefix))        

        # get number of volumes in full functional run minus dropped volumes (done here in case splithalf files are requested)
        nVols = (load(mni_file).shape[3] - dropvols)
        
        # define run name depending on whether run info is in file name
        if run_id != 0:
            run_name = 'run{}'.format(run_id)
        else:
            run_name = 'run1' # if no run info is in filename, then results are saved under 'run1'

        # check to see whether outputs exist in smoothDir (if smoothDir was specified in config file)
        if smoothDir:
            if splithalf_id != 0:
                smooth_file = op.join(smoothDir, 'sub-{}'.format(sub), 'preproc', '{}_splithalf{}'.format(run_name, splithalf_id), '{}_space-MNI-preproc_bold_smooth.nii.gz'.format(prefix))
                
                # ensure that the fROI from the *opposite* splithalf is picked up for timecourse extraction (e.g., timecourse from splithalf1 is extracted from fROI defined in splithalf2)
                if splithalf_id == 1:
                    print('Will skip signal extraction in splithalf{} for any fROIs defined in splithalf{}'.format(splithalf_id, splithalf_id))
                    froi_prefix = op.join(resultsDir, 'sub-{}'.format(sub), 'frois', '{}_splithalf2'.format(run_name))
                    
                if splithalf_id == 2:
                    print('Will skip signal extraction in splithalf{} for any fROIs defined in splithalf{}'.format(splithalf_id, splithalf_id))
                    froi_prefix = op.join(resultsDir, 'sub-{}'.format(sub), 'frois', '{}_splithalf1'.format(run_name))
            else:
                smooth_file = op.join(smoothDir, 'sub-{}'.format(sub), 'preproc', '{}'.format(run_name), '{}_space-MNI-preproc_bold_smooth.nii.gz'.format(prefix))
                froi_prefix = op.join(resultsDir, 'sub-{}'.format(sub), 'frois', '{}'.format(run_name))
            
            if os.path.exists(smooth_file):
                mni_file = smooth_file
                print('Previously smoothed data file has been found and will be used: {}'.format(mni_file))
            else:
                print('WARNING: A smoothDir was specified in the config file but no smoothed data files were found.')
        else:
            print('No smoothDir specified in the config file. Using fMRIPrep outputs.')
        
        # define preproc directory depending on whether splithalf was requested
        if splithalf_id != 0:
            preprocDir = op.join(subDir, 'preproc', '{}_splithalf{}'.format(run_name, splithalf_id))
        else:
            preprocDir = op.join(subDir, 'preproc', '{}'.format(run_name))
        
        # make preproc directory and save mni_file
        os.makedirs(preprocDir, exist_ok=True)
        
        if not resultsDir:
            shutil.copy(mni_file, preprocDir) 
        
        # grab roi file for each mask requested
        roi_masks = list()
        for m in mask_opts:
            if 'whole_brain' in m:
                roi_masks.append(mni_mask)
                print('Will extract whole brain timecourses')
            elif 'fROI' in m:
                if not froi_prefix: # resultsDir:
                    print('ERROR: unable to locate fROI file. Make sure a resultsDir is provided in the config file!')
                else:
                    roi_name = m.split('-')[1]
                    # roi_name = roi_name.lower() # if roi names are lowercase in define_fROI.py script
                    roi_file = glob.glob(op.join('{}'.format(froi_prefix),'*{}*.nii.gz'.format(roi_name)))#[0]
                    roi_masks.append(roi_file)
                    print('Using {} fROI file from {}'.format(roi_name, roi_file))
            else:
                if template is not None:
                    #template_name = template[:6] # take first 6 characters
                    template_name = template.split('_')[0] # take full template name
                    roi_file = glob.glob(op.join(sharedDir, 'ROIs', '{}'.format(template_name), '{}*.nii.gz'.format(m)))[0]
                else:
                    roi_file = glob.glob(op.join(sharedDir, 'ROIs', '{}*.nii.gz'.format(m)))[0]
                
                roi_masks.append(roi_file)
                print('Using {} ROI file from {}'.format(m, roi_file)) 
        
        return confound_file, art_file, mni_file, mni_mask, roi_masks, nVols
        
    datasource = Node(Function(output_names=['confound_file',
                                             'art_file',
                                             'mni_file',
                                             'mni_mask',
                                             'roi_masks',
                                             'nVols'],
                               function=data_grabber),
                               name='datasource')
    wf.connect(infosource, 'run_id', datasource, 'run_id')
    wf.connect(infosource, 'splithalf_id', datasource, 'splithalf_id')
    datasource.inputs.sub = sub
    datasource.inputs.mask_opts = mask_opts
    datasource.inputs.template = template
    datasource.inputs.task = task
    datasource.inputs.derivDir = derivDir
    datasource.inputs.projDir = projDir
    datasource.inputs.subDir = subDir
    datasource.inputs.resultsDir = resultsDir
    datasource.inputs.smoothDir = smoothDir
    datasource.inputs.sharedDir = sharedDir
    datasource.inputs.ses = ses
    datasource.inputs.dropvols = dropvols
    datasource.inputs.multiecho = multiecho

    # if drop volumes requested
    if dropvols != 0:
        print('Dropping {} volumes from the beginning of the functional run.'.format(dropvols))
        roi = Node(fsl.ExtractROI(t_min=dropvols, t_size=-1), name='extractroi')
        wf.connect(datasource, 'mni_file', roi, 'in_file')

    # define function to process data into halves for analysis (if requested in config file)
    def process_data_files(sub, mni_file, art_file, confound_file, regressor_opts, task, run_id, splithalf_id, TR, nVols, dropvols, subDir):
        import os
        import os.path as op
        import pandas as pd
        from pandas.errors import EmptyDataError
        import numpy as np
        from nibabel import load
        
        # create a dictionary for mapping between config file and labels used in confounds file (more options can be added later)
        regressor_dict = {'fd': 'framewise_displacement',
                          'dvars':'std_dvars',
                          'acompcor': ['a_comp_cor_00', 'a_comp_cor_01', 'a_comp_cor_02', 'a_comp_cor_03', 'a_comp_cor_04'],
                          'motion_params-6': ['trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z'],
                          'motion_params-12': ['trans_x', 'trans_x_derivative1', 'trans_y', 'trans_y_derivative1', 'trans_z', 'trans_z_derivative1', 'rot_x', 'rot_x_derivative1', 'rot_y', 'rot_y_derivative1', 'rot_z', 'rot_z_derivative1']}
        
        # extract the entries from the dictionary that match the key value provided in the config file
        regressor_list=list({r: regressor_dict[r] for r in regressor_opts if r in regressor_dict}.values())
        
        # remove nested lists if present (e.g., aCompCor regressors)
        regressor_names=[]
        for element in regressor_list:
            if type(element) is list:
                for item in element:
                    regressor_names.append(item)
            else:
                regressor_names.append(element)        
        
        # read in and filter confound file according to config file options
        confounds = pd.read_csv(confound_file, sep='\t', na_values='n/a')
        #confounds = confounds.filter(regressor_names)

        # read in art file, creating an empty dataframe if no outlier volumes (i.e., empty text file)
        try:
            outliers = pd.read_csv(art_file, header=None)[0].astype(int)
        except EmptyDataError:
            outliers = pd.DataFrame()      
        
        # make art directory and specify splithalf outlier file name
        if run_id != 0:
            run_abrv = 'run{}'.format(run_id)
            run_full = 'run-{:02d}'.format(run_id)
            outlier_file_prefix = 'sub-{}_task-{}_{}'.format(sub, task, run_full)
        else:
            run_abrv = 'run1'
            run_full = 'run-01'
            outlier_file_prefix = 'sub-{}_task-{}'.format(sub, task)         
        
        if splithalf_id == 0:  # if processing full run (splithalf = 'no' in config file)
            artDir = op.join(subDir, 'art_files', '{}'.format(run_abrv))
            outlier_file = op.join(artDir, '{}.txt'.format(outlier_file_prefix))
            vol_indx_file = op.join(artDir, '{}_incl-vols.txt'.format(outlier_file_prefix))
        else:
            artDir = op.join(subDir, 'art_files', '{}_splithalf{}'.format(run_abrv, splithalf_id))
            outlier_file = op.join(artDir,'{}_splithalf-{:02d}.txt'.format(outlier_file_prefix, splithalf_id))
            vol_indx_file = op.join(artDir, '{}_splithalf-{:02d}_incl-vols.txt'.format(outlier_file_prefix, splithalf_id))
        
        os.makedirs(artDir, exist_ok=True)

        # for each regressor
        regressors = []            
        for regressor in regressor_names:
            # framewise_displacement and dvars are relative to prior volume, so first value is nan
            if regressor == 'framewise_displacement' or regressor == 'std_dvars' or '_x' in regressor or '_y' in regressor or '_z' in regressor:
                print('Processing {} regressor'.format(regressor))
                regressors.append(confounds[regressor].fillna(0).iloc[dropvols:])
            else:
                regressors.append(confounds[regressor].iloc[dropvols:])
        
        print('Using the following nuisance regressors in the model: {}'.format(regressor_names))        
 
        # convert motion regressors to dataframe
        motion_params = pd.DataFrame(regressors).transpose()
        
        # generate vector of volume indices (where inclusion means to retain volume) to use for scrubbing
        vol_indx = np.arange(motion_params.shape[0], dtype=np.int64)
        
        # if art regressor was included in regressor_opts list in config file        
        if 'art' in regressor_opts:
            print('ART identified motion spikes will be scrubbed from data')
            if np.shape(outliers)[0] != 0: # if there are outlier volumes
                # remove excluded volumes from vec
                vol_indx = np.delete(vol_indx, [outliers])
                print('{} outlier volumes will be scrubbed in {}'.format(len(outliers), run_full))
        
        # get middle volume to define halves
        midVol = int(nVols/2)
        # number of volumes to drop per run (drop 6s total: 3s from each run)
        drop_nVols = int((6/TR)/2)
        
        # list of volumes to drop around midpoint (6s total, 3s on each side of midVol)
        droppedVols = np.arange(midVol-drop_nVols, midVol+drop_nVols, 1)
        
        # process full run if splithalf not requested
        if splithalf_id == 0:
            print('Using the full run for analysis')
            t_min=0
            t_size=nVols
        
        # process first half of data
        if splithalf_id == 1:
            print('Splitting first half of the run for analysis')
            # take first volume to middle volume, dropping final 3s of run
            t_min=0
            t_size=midVol-drop_nVols
            
            motion_params = motion_params.head(midVol-drop_nVols) # select confound variables from first half
            outliers = outliers[outliers < min(droppedVols)] # select outliers from first half
            vol_indx = vol_indx[vol_indx < min(droppedVols)] # select included volumes from first half
            
        # process second half of data
        if splithalf_id == 2:
            print('Splitting second half of the run for analysis')
            # take middle volume to last volume, dropping first 3s of run
            t_min=midVol+drop_nVols
            t_size=midVol-drop_nVols
            
            motion_params = motion_params.tail(midVol-drop_nVols) # select confound variables from second half
            outliers = outliers[outliers > max(droppedVols)] # select outliers from second half
            outliers = outliers-max(droppedVols+1) # outlier volume ids relative to start of run
            vol_indx = vol_indx[vol_indx > max(droppedVols)] # select included volumes from second half
            vol_indx = vol_indx-max(droppedVols+1) # volume ids relative to start of run

        # get number of volumes in current run
        curVols = load(mni_file).shape[3]
 
        # process full timeseries if the current run is already split data
        if curVols < nVols:
            print('The data provided were already split into halves and will not be split again.')
            t_min=0
            t_size=curVols

        # save outliers (split or not) as text file in subDir for modeling
        outliers.to_csv(outlier_file, index=False, header=False)
        pd.DataFrame(vol_indx).to_csv(vol_indx_file, index=False, header=False)
        
        # return processed data - either split or full run depending on 'splithalf' parameter in config file
        return t_min, t_size, motion_params, vol_indx, outliers
         
    # set up splitdata Node with specified outputs
    splitdata = Node(Function(output_names=['t_min',
                                            't_size',
                                            'motion_params',
                                            'vol_indx',
                                            'outliers'],
                              function=process_data_files), name='splitdata')

    # from infosource and datasource node add event and confound files and splithalf_id as input to splitdata node
    wf.connect(infosource, 'run_id', splitdata, 'run_id')
    wf.connect(infosource, 'splithalf_id', splitdata, 'splithalf_id')
    wf.connect(datasource, 'nVols', splitdata, 'nVols')
    wf.connect(datasource, 'confound_file', splitdata, 'confound_file')
    wf.connect(datasource, 'art_file', splitdata, 'art_file')
    splitdata.inputs.dropvols = dropvols
    splitdata.inputs.TR = TR
    splitdata.inputs.subDir = subDir
    splitdata.inputs.sub = sub
    splitdata.inputs.task = task
    splitdata.inputs.regressor_opts = regressor_opts
    if dropvols != 0: # pass file with dropped volumes if requested
        wf.connect(roi, 'roi_file', splitdata, 'mni_file')
    else: # otherwise pass preprocessed data file
        wf.connect(datasource, 'mni_file', splitdata, 'mni_file')
        
    # set up extractROI node to segment runs based on output from splitdata Node (output is called 'roi_file')
    mni_split = Node(fsl.ExtractROI(), name='mni_split')
    wf.connect(splitdata, 't_min', mni_split, 't_min')
    wf.connect(splitdata, 't_size', mni_split, 't_size')
    if dropvols != 0: # pass file with dropped volumes if requested
        wf.connect(roi, 'roi_file',  mni_split, 'in_file')
    else: # otherwise pass preprocessed data file
        wf.connect(datasource, 'mni_file', mni_split, 'in_file')

    # if requested, smooth before running model
    if run_smoothing:
        # create_susan_smooth refers to FSL's Susan algorithm for smoothing data
        smooth = create_susan_smooth()
        
        # smoothing workflow requires the following inputs:
            # inputnode.in_files : functional runs (filename or list of filenames)
            # inputnode.fwhm : fwhm for smoothing with SUSAN
            # inputnode.mask_file : mask used for estimating SUSAN thresholds (but not for smoothing)
        
        # provide smoothing_kernel_size, mask files, and split mni file
        smooth.inputs.inputnode.fwhm = smoothing_kernel_size
        wf.connect(datasource, 'mni_mask', smooth, 'inputnode.mask_file')
        wf.connect(mni_split, 'roi_file', smooth, 'inputnode.in_files')

    # define function to denoise data
    def denoise_data(imgs, mni_mask, motion_params, vol_indx, outliers, TR, hpf, filter_opt, detrend, standardize,  subDir, sub, run_id, splithalf_id, task):
        import nibabel as nib
        from nibabel import load
        import nilearn
        from nilearn import image
        import pandas as pd
        import numpy as np
        import os
        import os.path as op
        
        # define run name depending on whether run info is in file name
        if run_id != 0:
            run_abrv = 'run{}'.format(run_id)
            run_full = 'run-{:02d}'.format(run_id)
        else: # if no run info is in filename, then results are saved under 'run1'
            run_abrv = 'run1'
            run_full = 'run-01'

        # make output directory
        if splithalf_id != 0:
            denoiseDir = op.join(subDir, 'denoised', '{}_splithalf{}'.format(run_abrv, splithalf_id))
        else:
            denoiseDir = op.join(subDir, 'denoised', '{}'.format(run_abrv))
        
        os.makedirs(denoiseDir, exist_ok=True)
     
        # define output file names depending on whether run info is in file name
        if run_id != 0:
            denoise_file = op.join(denoiseDir, 'sub-{}_task-{}_{}_splithalf-{:02d}_denoised_bold.nii.gz'.format(sub, task, run_full, splithalf_id))
            pad_file = op.join(denoiseDir, 'sub-{}_task-{}_{}_splithalf-{:02d}_denoised_padded_bold.nii.gz'.format(sub, task, run_full, splithalf_id))
        else: # if no run info is in filename, then results are saved under 'run1'
            denoise_file = op.join(denoiseDir, 'sub-{}_task-{}_splithalf-{:02d}_denoised_bold.nii.gz'.format(sub, task, splithalf_id))
            pad_file = op.join(denoiseDir, 'sub-{}_task-{}_splithalf-{:02d}_denoised_padded_bold.nii.gz'.format(sub, task, splithalf_id))
        
        # the smoothing node returns a list object but clean_img needs a path to the file
        if isinstance(imgs, list):
            imgs=imgs[0]        
        
        # process options from config file
        if detrend == 'yes':
            detrend_opt = True
        else:
            detrend_opt = False
        if standardize != 'no':
            standardize_opt = standardize
        else:
            standardize_opt = False
            
        # convert filter from seconds to Hz
        hpf_hz = 1/hpf
        
        print('Will apply a {} filter using a high pass filter cutoff of {}Hz for {}.'.format(filter_opt, hpf_hz, run_full))

        # define kwargs input to signal.clean function
        if filter_opt == 'butterworth':
            kwargs_opts={'clean__sample_mask':vol_indx, 
                         'clean__butterworth__t_r':TR,
                         'clean__butterworth__high_pass':hpf_hz}
        elif filter_opt == 'cosine':
            kwargs_opts={'clean__sample_mask':vol_indx, 
                         'clean__cosine__t_r':TR,
                         'clean__cosine__high_pass':hpf_hz}
        else:
            kwargs_opts={'clean__sample_mask':vol_indx,
                         'clean__t_r':TR}

        # process signal data with parameters specified in config file
        denoised_data = image.clean_img(imgs, mask_img=mni_mask, confounds=motion_params, detrend=detrend_opt, standardize=standardize_opt, **kwargs_opts)
        
        # save denoised data
        nib.save(denoised_data, denoise_file)
        
        # load denoised data and extract dimension info
        denoise_img = image.load_img(denoised_data)
        img_dim = denoise_img.shape
        
        # load input data and extract volume info
        input_img = image.load_img(imgs)
        curVols = input_img.shape[3]
        
        # create vector of volumes for indexing
        all_vols_vec = np.arange(curVols, dtype=np.int64)
        
        # create nan volume
        nan_vol = np.empty((img_dim[:-1]))
        nan_vol[:] = np.nan
        nan_img = image.new_img_like(denoise_img, nan_vol, affine=denoise_img.affine)

        # pad denoised data with nan vols where vols were scrubbed
        d=0 # index for denoised data which has a volume for index in vol_indx [curVols - outliers]
        pad_imgs = list()
        for vol in all_vols_vec: # for each volume
            if vol in vol_indx:
                tmp_vol = image.index_img(denoise_img, d)
                pad_imgs.append(tmp_vol)
                d += 1
            else:
                tmp_vol = nan_img
                pad_imgs.append(tmp_vol)
        
        # concatente list of 3D imgs to one 4D img
        pad_concat = image.concat_imgs(pad_imgs)
       
        # save padded data
        nib.save(pad_concat, pad_file)
        
        return denoised_data, pad_concat
    
    # process signal, passing generated confounds
    cleansignal = Node(Function(output_names=['denoised_data',
                                              'pad_concat'],
                                function=denoise_data), 
                                name='cleansignal')
    wf.connect(datasource, 'mni_mask', cleansignal, 'mni_mask')
    wf.connect(splitdata, 'motion_params', cleansignal, 'motion_params')
    wf.connect(splitdata, 'vol_indx', cleansignal, 'vol_indx')
    wf.connect(splitdata, 'outliers', cleansignal, 'outliers')
    wf.connect(infosource, 'run_id', cleansignal, 'run_id')
    wf.connect(infosource, 'splithalf_id', cleansignal, 'splithalf_id')
    cleansignal.inputs.sub = sub
    cleansignal.inputs.TR = TR
    cleansignal.inputs.task = task
    cleansignal.inputs.hpf = hpf
    cleansignal.inputs.detrend = detrend
    cleansignal.inputs.standardize = standardize
    cleansignal.inputs.filter_opt = filter_opt
    cleansignal.inputs.subDir = subDir
    
    # pass data to cleansignal depending on whether smoothing was requested
    if run_smoothing:
        # pass smoothed output files as functional runs to denoise function
        wf.connect(smooth, 'outputnode.smoothed_files', cleansignal, 'imgs')
    else: 
       # pass unsmoothed output files as functional runs to modelspec
        wf.connect(mni_split, 'roi_file', cleansignal, 'imgs')
    
    def extract_timecourse(denoised_data, pad_concat, roi_masks, mask_opts, extract_opt, outDir, subDir, sub, run_id, splithalf_id, task, nVols, vol_indx):
        import nibabel as nib
        from nilearn.maskers import NiftiMasker
        from nilearn import image
        import re
        import os
        import os.path as op
        import numpy as np
        import pandas as pd 
        
        # make output directory
        tcDir = op.join(subDir, 'timecourses')
        os.makedirs(tcDir, exist_ok=True)
        
        # define run name depending on whether run info is in file name
        if run_id != 0:
            run_full = 'run-{:02d}'.format(run_id)
            run_prefix = op.join(tcDir, 'sub-{}_task-{}_{}'.format(sub, task, run_full))
        else: # if no run info is in filename, then results are saved under 'run1'
            run_full = 'run-01'
            run_prefix = op.join(tcDir, 'sub-{}_task-{}'.format(sub, task))

        # extract timecourses for each ROI provided in config file
        for m, mask in enumerate(roi_masks):

            print('Extracting signal from {} ROI'.format(mask_opts[m]))
            
            # ensure that mask/ROI is binarized
            mask_img = image.load_img(mask)
            mask_bin = mask_img.get_fdata() # get image data (as floating point data)
            mask_bin[mask_bin >= 1] = 1 # for values equal to or greater than 1, make 1 (values less than 1 are already 0)
            mask_bin = image.new_img_like(mask_img, mask_bin) # create a new image of the same class as the initial image
            
            # the masks should already be resampled, but check if this is true and resample if not
            if denoised_data.shape[0:3] != mask_bin.shape[0:3]:
                print('WARNING: the mask provided has different dimensions than the functional data!')
                
                # make directory to save resampled rois
                roiDir = op.join(outDir, 'resampled_rois')
                os.makedirs(roiDir, exist_ok=True)
                
                # extract file name
                roi_name = mask[0].split('/')[-1].split('.nii.gz')[0]
  
                resampled_file = op.join(roiDir, '{}_resampled.nii.gz'.format(roi_name))
                
                # check if file already exists
                if os.path.isfile(resampled_file):
                    print('Found previously resampled {} ROI in output directory'.format(mask_opts[m]))
                    mask_bin = image.load_img(resampled_file)
                else:
                    # resample image
                    print('Resampling {} ROI to match functional data'.format(mask_opts[m]))
                    mask_bin = image.resample_to_img(mask_bin, denoised_data, interpolation='nearest')
                    mask_bin.to_filename(resampled_file)

            # instantiate the masker
            masker = NiftiMasker(mask_img = mask_bin)
            
            # apply mask to denoised padded data
            padded_masked = masker.fit_transform(pad_concat)
            padded_masked_df = pd.DataFrame(padded_masked)
            
            # add splithalf info to output file name     
            if splithalf_id != 0:
                if 'fROI' in mask_opts[m]:
                    # extract contrast used to generate fROI from file name
                    contrast = roi_masks[m][0].split('_')[-2]
                    # get fROI splithalf info from roi mask and add to output file name
                    roi_splithalf = re.search('splithalf-(.+?)_', roi_masks[m][0]).group().split('_')[0]
                                        
                    tc_prefix = op.join('{}_splithalf-{:02d}_{}-{}-{}'.format(run_prefix, splithalf_id, mask_opts[m], contrast, roi_splithalf))
                else:
                    tc_prefix = op.join('{}_splithalf-{:02d}_{}'.format(run_prefix, splithalf_id, mask_opts[m]))
            else:
                tc_prefix = op.join('{}_{}'.format(run_prefix, mask_opts[m]))
            
            # average data in mask if requested and add info to output file name
            if extract_opt == 'mean':
                # average voxelwise timecourses
                print('Averging voxelwise timecourses within {} mask'.format(mask_opts[m]))
                padded_masked_df = padded_masked_df.mean(axis=1).replace([0], np.nan)
                tc_file = op.join('{}_mean_timecourse.csv'.format(tc_prefix))
            else:
                tc_file = op.join('{}_voxelwise_timecourses.csv'.format(tc_prefix))
            
            # save file
            padded_masked_df.to_csv(tc_file, header = False, index=False)
            
        return padded_masked
        
    extractsignal = Node(Function(output_names=['denoised_masked',
                                                'padded_masked'],
                                  function=extract_timecourse), 
                                  name='extractsignal')
    
    wf.connect(infosource, 'run_id', extractsignal, 'run_id')
    wf.connect(infosource, 'splithalf_id', extractsignal, 'splithalf_id')
    wf.connect(datasource, 'nVols', extractsignal, 'nVols')
    wf.connect(datasource, 'roi_masks', extractsignal, 'roi_masks')
    wf.connect(splitdata, 'vol_indx', extractsignal, 'vol_indx')                                   
    wf.connect(cleansignal, 'denoised_data', extractsignal, 'denoised_data')
    wf.connect(cleansignal, 'pad_concat', extractsignal, 'pad_concat')
    extractsignal.inputs.sub = sub
    extractsignal.inputs.task = task
    extractsignal.inputs.outDir = outDir
    extractsignal.inputs.subDir = subDir
    extractsignal.inputs.mask_opts = mask_opts
    extractsignal.inputs.extract_opt = extract_opt
    
    # extract components from working directory cache and store it at a different location
    sinker = Node(DataSink(), name='datasink')
    sinker.inputs.base_directory = subDir
    sinker.inputs.regexp_substitutions = [('_run_id_', 'run'),
                                          ('run0', 'run1'),
                                          ('_splithalf_id_0', ''),
                                          ('_splithalf_id_', '_splithalf'),
                                          ('_smooth0/',''),
                                          ('_roi',''),
                                          ('MNI152NLin2009cAsym_res-2_desc','MNI')]          
    
    # define where output files are saved
    wf.connect(mni_split, 'roi_file', sinker, 'preproc.@roi_file')
    if run_smoothing:
        wf.connect(smooth, 'outputnode.smoothed_files', sinker, 'preproc.@')  
        
    return wf

# define function to extract subject-level data for workflow
def process_subject(layout, sharedDir, projDir, derivDir, outDir, workDir, 
                    sub, task, ses, multiecho, sub_runs, regressor_opts, mask_opts, smoothing_kernel_size,resultsDir,smoothDir, hpf, filter_opt, detrend, standardize, template, extract_opt, dropvols, splithalf):    
    """Grab information and start nipype workflow
    We want to parallelize runs for greater efficiency
    """
    # define subject output directory
    subDir = op.join(outDir, 'sub-{}'.format(sub))
    
    # identify scan and events files
    if ses != 'no': # if session was provided
        print('Session information provided. Assuming data are organized into session folders.')
        
        # identify scans file (from derivDir bc artifact information is saved in the processed scans.tsv file)
        scans_tsv = glob.glob(op.join(derivDir, 'sub-{}'.format(sub), 'ses-{}'.format(ses), 'func', '*_scans.tsv'))[0]
        
    else: # if session was 'no'
        # identify scans file (from derivDir bc artifact information is saved in the processed scans.tsv file)
        scans_tsv = glob.glob(op.join(derivDir, 'sub-{}'.format(sub), 'func', '*_scans.tsv'))[0]
        
    # return error if scan file not found
    if not os.path.isfile(scans_tsv):
        raise IOError('scans file {} not found.'.format(scans_tsv))

    # read in scans file
    scans_df = pd.read_csv(scans_tsv, sep='\t')

    # extract subject, task, and run information from filenames in scans.tsv file
    scans_df['task'] = scans_df['filename'].str.split('task-', expand=True).loc[:,1]
    scans_df['task'] = scans_df['task'].str.split('_run', expand=True).loc[:,0]
    scans_df['task'] = scans_df['task'].str.split('_bold', expand=True).loc[:,0]
    scans_df['run'] = scans_df['filename'].str.split(scans_df['task'][0], expand=True).loc[:,1]
    scans_df['run'] = scans_df['run'].str.split('_bold', expand=True).loc[:,0]
    if not scans_df['run'][0]: # if no run information
        scans_df['run'] = None
    else:
        scans_df['run'] = scans_df['run'].str.split('-', expand=True).loc[:,1]
    
    # remove runs tagged with excessive motion, that are for a different task, or aren't in run list in the config file
    if sub_runs != 0:
        keepruns = scans_df[(scans_df.MotionExclusion == False) & (scans_df.task == task) & (scans_df.run.isin(['{:02d}'.format(r) for r in sub_runs]))].run
    else:
        keepruns = scans_df[(scans_df.MotionExclusion == False) & (scans_df.task == task)].run.fillna(value='0')    

    # if split half requested
    if splithalf == 'yes':
        keepruns = keepruns.loc[keepruns.index.repeat(2)] # duplicate runs
        splithalves=[1,2] * int(len(keepruns)/2) # create split half id for each run
    else:
        splithalves=[0] * int(len(keepruns)) # create split half id 0 for each run
    
    # convert runs to list of values
    keepruns = list(keepruns.astype(int).values)

    # if the participant didn't have any runs for this task or all runs were excluded due to motion
    if not keepruns:
        raise FileNotFoundError('No included bold {} runs found for sub-{}'.format(task, sub))
   
    # extract TR info from bidsDir bold json files (assumes TR is same across runs)
    epi = layout.get(subject=sub, suffix='bold', task=task, return_type='file')[0] # take first file
    TR = layout.get_metadata(epi)['RepetitionTime'] # extract TR field
    
    # delete prior processing directories because cache files can interfere with workflow
    subworkDir = op.join(workDir, 'sub-{}_task-{}_timecourses'.format(sub, task))
    if os.path.exists(subworkDir):
        shutil.rmtree(subworkDir)

    # call timecourse workflow with extracted subject-level data
    wf = create_timecourse_workflow(sharedDir, projDir, derivDir, workDir, outDir, subDir, sub,
                                    task, ses, multiecho, keepruns, regressor_opts, mask_opts, smoothing_kernel_size, resultsDir, smoothDir, hpf, filter_opt, TR, detrend, standardize, template, extract_opt, dropvols, splithalves)  
                                    
                                    
    return wf

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
    sharedDir=config_file.loc['sharedDir',1]
    bidsDir=config_file.loc['bidsDir',1]
    derivDir=config_file.loc['derivDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    smoothDir=config_file.loc['smoothDir',1]
    task=config_file.loc['task',1]
    ses=config_file.loc['sessions',1]
    multiecho=config_file.loc['multiecho',1]
    dropvols=int(config_file.loc['dropvols',1])
    smoothing_kernel_size=int(config_file.loc['smoothing',1])
    hpf=int(config_file.loc['hpf',1])
    filter_opt=config_file.loc['filter',1]
    detrend=config_file.loc['detrend',1]
    standardize=config_file.loc['standardize',1]
    regressor_opts=config_file.loc['regressors',1].replace(' ','').split(',')
    mask_opts=config_file.loc['mask',1].replace(' ','').split(',')
    splithalf=config_file.loc['splithalf',1]
    template=config_file.loc['template',1]
    extract_opt=config_file.loc['extract',1]
    overwrite=config_file.loc['overwrite',1]
    
    # print if BIDS directory is not found
    if not op.exists(bidsDir):
        raise IOError('BIDS directory {} not found.'.format(bidsDir))
    
    # print if the fMRIPrep directory is not found
    if not op.exists(derivDir):
        raise IOError('Derivatives directory {} not found.'.format(derivDir))
    
    # lowercase regressor options - allows flexibility in how users specify in config file
    regressor_opts = [r.lower() for r in regressor_opts]
    
    # define output and working directories
    if resultsDir: # if resultsDir was specified
        # save outputs to established resultsDir
        print('Saving results to existing results directory: {}'.format(resultsDir))
        outDir = resultsDir
        workDir = op.join(outDir, 'processing')
        
        # identify analysis README file
        readme_file=op.join(outDir, 'README.txt')
        
        # add config details to project README file
        with open(readme_file, 'a') as file_1:
            file_1.write('\n')
            file_1.write('Timecourses were extracted using the timecourse_pipeline.py \n')
            file_1.write('The following masks were specified in the config file: {} \n'.format(mask_opts))
    
    else: # if no resultsDir was specified        
        workDir, outDir = op.realpath(args.workDir), op.realpath(args.outDir)
    
        # identify analysis README file
        readme_file=op.join(outDir, 'README.txt')
        
        # if user requested overwrite, delete previous directories
        if (overwrite == 'yes') & (len(os.listdir(workDir)) != 0):
            print('Overwriting existing outputs.')
            shutil.copy(readme_file, args.projDir)  # temporarily copy README to project directory
            # remove directories
            shutil.rmtree(outDir)
            # create new directories
            os.mkdir(outDir)
            os.mkdir(workDir)
            tmp_file=op.join(args.projDir, 'README.txt')
            shutil.copy(tmp_file, readme_file) # copy README to new working directory
            os.remove(tmp_file) # delete temp file
        
        # if user requested no overwrite, create new working directory with date and time stamp
        if (overwrite == 'no') & (len(os.listdir(workDir)) != 0):
            print('Creating new output directories to avoid overwriting existing outputs.')
            today = datetime.now() # get date
            datestring = today.strftime('%Y-%m-%d_%H-%M-%S')
            outDir = (outDir + '_' + datestring) # new directory path
            workDir = op.join(outDir, 'processing')
            # create new directories
            os.mkdir(outDir)
            os.mkdir(workDir)      
            shutil.copy(readme_file, outDir)  # copy README to new output directory
            readme_file=op.join(outDir, 'README.txt') # re-identify current analysis README file
            
        # add config details to project README file
        with open(args.config, 'r') as file_1, open(readme_file, 'a') as file_2:
            file_2.write('Timecourses were extracted by running the timecourse_pipeline.py \n')
            file_2.write('Pipeline parameters were defined by the {} file \n'.format(args.config))
            for line in file_1:
                file_2.write(line)

    # get layout of BIDS directory
    # this is necessary because the pipeline reads the functional json files that have TR info
    # the derivDir (where fMRIPrep outputs are) doesn't have json files with this information, so getting the layout of that directory will result in an error
    layout = BIDSLayout(bidsDir)

    # define subjects - if none are provided in the script call, they are extracted from the BIDS directory layout information
    subjects = args.subjects if args.subjects else layout.get_subjects()

    # for each subject in the list of subjects
    for index, sub in enumerate(subjects):
        # pass runs for this sub
        sub_runs=args.runs[index]
        sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
        if sub_runs == ['NA']: # if run info isn't used in file names
            sub_runs = 0
        else:
            sub_runs=list(map(int, sub_runs)) # convert to integers        
              
        # create a process_subject workflow with the inputs defined above
        wf = process_subject(layout, sharedDir, args.projDir, derivDir, outDir, workDir, sub,
                             task, ses, multiecho, sub_runs, regressor_opts, mask_opts, smoothing_kernel_size, resultsDir, smoothDir, hpf, filter_opt, detrend, standardize, template, extract_opt, dropvols, splithalf)
   
        # configure workflow options
        wf.config['execution'] = {'crashfile_format': 'txt',
                                  'remove_unnecessary_outputs': False,
                                  'keep_inputs': True}

        # run multiproc
        args_dict = {'n_procs' : 4}
        wf.run(plugin='MultiProc', plugin_args = args_dict)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()