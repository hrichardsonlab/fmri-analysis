"""
Individual run analysis using outputs from fMRIPrep

Adapted script from original notebook:
https://github.com/poldrack/fmri-analysis-vm/blob/master/analysis/postFMRIPREPmodelling/First%20and%20Second%20Level%20Modeling%20(FSL).ipynb

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page
Nesting of functions: main > argparser > process_subject > create_firstlevel_workflow > data_grabber > process_data_files > gen_model_info > read_contrasts > substitutes

Requirement: BIDS dataset (including events.tsv), derivatives directory with fMRIPrep outputs, and modeling files

"""
import nipype.algorithms.modelgen as model
from nipype.interfaces import fsl, ants
from nipype.interfaces.base import Bunch
from nipype import Workflow, Node, IdentityInterface, Function, DataSink, JoinNode, MapNode
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
def create_firstlevel_workflow(projDir, derivDir, workDir, outDir, 
                               sub, task, ses, runs, events_files, events, contrast, contrast_opts, timecourses,
                               regressor_opts, smoothing_kernel_size, resultsDir, hpf, TR, dropvols, splithalves, sparse,
                               name='sub-{}_task-{}_levelone'):
    """Processing pipeline"""
    
    # initialize workflow
    wf = Workflow(name=name.format(sub, task),
                  base_dir=workDir)
    
    # configure workflow
    # parameterize_dirs: parameterizations over 32 characters will be replaced by their hash; essentially prevented an issue of having too many characters in a file/folder name (i.e., https://github.com/nipy/nipype/issues/2061#issuecomment-1189562017)
    wf.config['execution']['parameterize_dirs'] = False

    infosource = Node(IdentityInterface(fields=['run_id', 'event_file', 'splithalf_id']), name='infosource')
    
    # define iterables to run nodes over runs, events, splithalves, and/or subs
    infosource.iterables = [('run_id', runs),
                            ('event_file', events_files),
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
    def data_grabber(sub, task, derivDir, resultsDir, outDir, ses, run_id, splithalf_id):
        """Quick filegrabber ala SelectFiles/DataGrabber"""
        import os
        import os.path as op
        import shutil
        from nibabel import load
        
        # define output filename and path, depending on whether session information is in directory/file names
        if ses != 'no': # if session was provided
            # define path to preprocessed functional and mask data (subject derivatives func folder)
            prefix = 'sub-{}_ses-{}_task-{}_run-{:02d}'.format(sub, ses, task, run_id)
            funcDir = op.join(derivDir, 'sub-{}'.format(sub), 'ses-{}'.format(ses), 'func')
            mni_mask = op.join(funcDir, 'sub-{}_ses-{}_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub, ses))
            
        else: # if session was 'no'
            # define path to preprocessed functional and mask data (subject derivatives func folder)
            prefix = 'sub-{}_task-{}_run-{:02d}'.format(sub, task, run_id)
            funcDir = op.join(derivDir, 'sub-{}'.format(sub), 'func')
            mni_mask = op.join(funcDir, 'sub-{}_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub))

        # grab the confound, MNI, and rapidart outlier file
        confound_file = op.join(funcDir, '{}_desc-confounds_timeseries.tsv'.format(prefix))
        mni_file = op.join(funcDir, '{}_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz'.format(prefix))
        art_file = op.join(funcDir, 'art', '{}{:02d}'.format(task, run_id), 'art.{}_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold_outliers.txt'.format(prefix))
        
        # get number of volumes in full functional run (done here in case splithalf files are requested)
        nVols = load(mni_file).shape[3]

        # check to see whether outputs exist in resultsDir (if resultsDir was specified in config file)
        if resultsDir:
            if splithalf_id != 0:
                smooth_file = op.join(resultsDir, 'sub-{}'.format(sub), 'preproc', 'run{}_splithalf{}'.format(run_id, splithalf_id), '{}_space-MNI-preproc_bold_smooth.nii.gz'.format(prefix))
            else:
                smooth_file = op.join(resultsDir, 'sub-{}'.format(sub), 'preproc', 'run{}'.format(run_id), '{}_space-MNI-preproc_bold_smooth.nii.gz'.format(prefix))
            if os.path.exists(smooth_file):
                mni_file = smooth_file
                print('Previously smoothed data file has been found and will be used: {}'.format(mni_file))
            else:
                print('WARNING: A resultsDir was specified in the config file but no smoothed data files were found.')
        else:
            print('No resultsDir specified in the config file. Using fMRIPrep outputs.')
        
        # make preproc directory
        if splithalf_id != 0:
            preprocDir = op.join(outDir, 'preproc', 'run{}_splithalf{}'.format(run_id, splithalf_id))
        else:
            preprocDir = op.join(outDir, 'preproc', 'run{}'.format(run_id))
        
        # save mni_file
        os.makedirs(preprocDir, exist_ok=True)
        shutil.copy(mni_file, preprocDir)

        return confound_file, art_file, mni_file, mni_mask, nVols
    
    datasource = Node(Function(output_names=['confound_file',
                                             'art_file',
                                             'mni_file',
                                             'mni_mask',
                                             'nVols'],
                               function=data_grabber),
                               name='datasource')
    wf.connect(infosource, 'run_id', datasource, 'run_id')
    wf.connect(infosource, 'splithalf_id', datasource, 'splithalf_id')
    datasource.inputs.sub = sub
    datasource.inputs.task = task
    datasource.inputs.derivDir = derivDir
    datasource.inputs.resultsDir = resultsDir
    datasource.inputs.outDir = outDir
    datasource.inputs.ses = ses

    # define function to process data into halves for analysis (if requested in config file)
    def process_data_files(sub, mni_file, event_file, timecourses, art_file, confound_file, regressor_opts, run_id, splithalf_id, TR, nVols, outDir):
        import os
        import os.path as op
        import pandas as pd
        from pandas.errors import EmptyDataError
        import numpy as np
        from nibabel import load
        
        # create a dictionary for mapping between config file and labels used in confounds file (more options can be added later)
        regressor_dict = {'FD': 'framewise_displacement',
                          'DVARS':'std_dvars',
                          'aCompCor': ['a_comp_cor_00', 'a_comp_cor_01', 'a_comp_cor_02', 'a_comp_cor_03', 'a_comp_cor_04']}
        
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
        confounds = confounds.filter(regressor_names)
        
        # read in art file, creating an empty dataframe if no outlier volumes (i.e., empty text file)
        try:
            outliers = pd.read_csv(art_file, header=None)[0].astype(int)
        except EmptyDataError:
            outliers = pd.DataFrame()
        
        # make art directory and specify splithalf outlier file name (used by process_data_files and modelspec functions)
        artDir = op.join(outDir, 'art_files')
        os.makedirs(artDir, exist_ok=True)
        if splithalf_id == 0: # if processing full run (splithalf = 'no' in config file)
            outlier_file = op.join(artDir, 'sub-{}_run-{:02d}.txt'.format(sub, run_id))
        else: # if splitting run in half (splithalf = 'yes' in config file)
            outlier_file = op.join(artDir, 'sub-{}_run-{:02d}_splithalf{}.txt'.format(sub, run_id, splithalf_id))
        
        # read in events or timecourse file depending on config file options
        if not 'no' in timecourses:
            tc_reg = pd.read_csv(event_file, sep='\t')
            # add timecourse regressors to list of regressor names
            regressor_names.extend(list(tc_reg.columns))
            # add timecourses to confounds dataframe
            confounds = tc_reg.join(confounds)
            # create empty stimuli dataframe
            stimuli = []
        else:
            stimuli = pd.read_csv(event_file, sep='\t')

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
            
            if len(stimuli) != 0: # if there are stimuli
                stimuli = stimuli[stimuli.onset < min(droppedVols+1)*TR] # select events that happen in the first half
            confounds = confounds.head(midVol-drop_nVols) # select confound variables from first half
            outliers = outliers[outliers < min(droppedVols)] # select outliers from first half
            
        # process second half of data
        if splithalf_id == 2:
            print('Splitting second half of the run for analysis')
            # take middle volume to last volume, dropping first 3s of run
            t_min=midVol+drop_nVols
            t_size=midVol-drop_nVols
            
            if len(stimuli) != 0: # if there are stimuli
                stimuli = stimuli[stimuli.onset > max(droppedVols+1)*TR] # select events that happen in the second half
                stimuli.onset = stimuli.onset-max(droppedVols+1)*TR # calculate onsets relative to start of run
            confounds = confounds.tail(midVol-drop_nVols) # select confound variables from second half
            outliers = outliers[outliers > max(droppedVols)] # select outliers from second half
            outliers = outliers-max(droppedVols+1) # outlier volume ids relative to start of run

        # get number of volumes in current run
        curVols = load(mni_file).shape[3]
 
        # process full timeseries if the current run is already split data
        if curVols < nVols:
            print('The data provided were already split into halves and will not be split again.')
            t_min=0
            t_size=curVols

        # save outliers (split or not) as text file in outDir for modeling
        outliers.to_csv(outlier_file, index=False, header=False)

        # return processed data - either split or full run depending on 'splithalf' parameter in config file
        return t_min, t_size, stimuli, confounds, regressor_names, outlier_file
         
    # set up splitdata Node with specified outputs
    splitdata = Node(Function(output_names=['t_min',
                                            't_size',
                                            'stimuli',
                                            'confounds',
                                            'regressor_names',
                                            'outlier_file'],
                              function=process_data_files), name='splitdata')

    # from infosource and datasource node add event and confound files and splithalf_id as input to splitdata node
    wf.connect(infosource, 'event_file', splitdata, 'event_file')
    wf.connect(infosource, 'run_id', splitdata, 'run_id')
    wf.connect(infosource, 'splithalf_id', splitdata, 'splithalf_id')
    wf.connect(datasource, 'nVols', splitdata, 'nVols')
    wf.connect(datasource, 'mni_file', splitdata, 'mni_file')
    wf.connect(datasource, 'confound_file', splitdata, 'confound_file')
    wf.connect(datasource, 'art_file', splitdata, 'art_file')
    splitdata.inputs.TR = TR
    splitdata.inputs.outDir = outDir
    splitdata.inputs.sub = sub
    splitdata.inputs.regressor_opts = regressor_opts
    splitdata.inputs.timecourses = timecourses

    # set up extractROI node to segment runs based on output from splitdata Node (output is called 'roi_file')
    mni_split = Node(fsl.ExtractROI(), name='mni_split')
    wf.connect(splitdata, 't_min', mni_split, 't_min')
    wf.connect(splitdata, 't_size', mni_split, 't_size')
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
        
    # define model configuration function
    def gen_model_info(stimuli, events, timecourses, confounds, regressor_names, dropvols):
        """Defines `SpecifyModel` information from BIDS events."""
        from nipype.interfaces.base import Bunch
        
        print('Using the following nuisance regressors in the model: {}'.format(regressor_names))
        
        # if there are stimuli/events to process (ie not timecourse regressors)
        if len(stimuli) != 0:
            trial_types = stimuli[stimuli.trial_type.isin(['{}'.format(e) for e in events])].trial_type.unique()
             
            # extract onset and duration for each trial type
            onset = []
            duration = []
            for trial in trial_types:
                # extract onset and duration information
                onset.append(stimuli[stimuli.trial_type == trial].onset.tolist())
                duration.append(stimuli[stimuli.trial_type == trial].duration.tolist())

            print('Configuring model to analyse the following events within the run: {}'.format(trial_types))

        # for each regressor
        regressors = []            
        for regressor in regressor_names:
            if regressor == 'framewise_displacement':
                print('Processing {} regressor'.format(regressor))
                regressors.append(confounds[regressor].fillna(0).iloc[dropvols:])
            elif regressor == 'std_dvars':
                print('Processing {} regressor'.format(regressor))
                regressors.append(confounds[regressor].fillna(0).iloc[dropvols:])
            else:
                regressors.append(confounds[regressor].iloc[dropvols:])
        
        # if ROI timecourses are being modelled
        if not 'no' in timecourses:
            info = [Bunch(
                regressors=regressors,
                regressor_names=regressor_names,
            )]
        else:
            info = [Bunch(
                conditions=trial_types,
                onsets=onset,
                durations=duration,
                regressors=regressors,
                regressor_names=regressor_names,
            )]

        return info

    # could format as bids model json in the future (https://bids-standard.github.io/stats-models/walkthrough-1.html)
    # need to add artifact volumes output from art in prior step [see below for how outlier_files were passed to modelspec]
    modelinfo = Node(Function(function=gen_model_info), name='modelinfo')
    modelinfo.inputs.dropvols = dropvols
    modelinfo.inputs.events = events
    modelinfo.inputs.timecourses = timecourses
    # from splitdata node add event and confound files and splithalf_id as input to modelinfo node
    wf.connect(splitdata, 'stimuli', modelinfo, 'stimuli')
    wf.connect(splitdata, 'confounds', modelinfo, 'confounds')
    wf.connect(splitdata, 'regressor_names', modelinfo, 'regressor_names') # pass regressor names to model info

    # if drop volumes requested (likely always no for us)
    if dropvols != 0:
        roi = Node(fsl.ExtractROI(t_min=dropvols, t_size=-1), name='extractroi')
        # drop volumes from smoothed data if smoothing was requested
        if run_smoothing:
            wf.connect(smooth, 'outputnode.smoothed_files', roi, 'in_file')
        # drop volumes from unsmoothed data if smoothing was not requested
        else: 
            wf.connect(mni_split, 'roi_file', roi, 'in_file')
    
    # if sparse model requested (allows model generation for sparse and sparse-clustered acquisition experiments)
    if sparse:
        modelspec = Node(model.SpecifySparseModel(), name='modelspec')
        modelspec.inputs.time_acquisition = None
    else:
        modelspec = Node(model.SpecifyModel(), name='modelspec')
        
    # specify model inputs
    modelspec.inputs.input_units = 'secs'
    modelspec.inputs.time_repetition = TR
    modelspec.inputs.high_pass_filter_cutoff = hpf
    wf.connect(modelinfo, 'out', modelspec, 'subject_info')
    
    print('Using a high pass filter cutoff of {}'.format(modelspec.inputs.high_pass_filter_cutoff))
    
    # pass data to modelspec depending on whether dropvols and/or smoothing were requested
    if dropvols !=0: # if drop volumes requested (likely always no for us)
        # pass dropped value files (smoothed or not depending on logic above) as functional runs to modelspec
        wf.connect(roi, 'roi_file', modelspec, 'functional_runs')
    else:
        if run_smoothing:
            # pass smoothed output files as functional runs to modelspec
            wf.connect(smooth, 'outputnode.smoothed_files', modelspec, 'functional_runs')
        else: 
           # pass unsmoothed output files as functional runs to modelspec
            wf.connect(mni_split, 'roi_file', modelspec, 'functional_runs')
            
    if 'art' in regressor_opts:
        print('ART identified motion spikes will be used as nuisance regressors')
        wf.connect(splitdata, 'outlier_file', modelspec, 'outlier_files') # generated using rapidart in motion exclusions script
    
    # define function to read in and parse task contrasts
    def read_contrasts(projDir, task, contrast, contrast_opts):
        import os.path as op
        import pandas as pd 

        contrasts = []
        
        if contrast == 'yes':
            print('Setting up contrasts')
            # read in data contrast file
            contrasts_file = op.join(projDir, 'data', 'contrast_files', 'contrasts.tsv')
            
            # if contrasts file not found
            if not op.exists(contrasts_file):
                raise FileNotFoundError('Contrasts file {} not found.'.format(contrasts_file))
            
            # read in contrasts file
            contrast_info = pd.read_csv(contrasts_file, sep='\t')
            
            # select contrasts of interest specified in config file
            contrast_info = contrast_info[contrast_info['desc'].isin(contrast_opts)]
            
            # for each row
            for index, row in contrast_info.iterrows():
                # skip a row specifies a contrast for a different task (i.e., not pixar)
                if row[0] != task:
                    continue
                
                # extract task contrasts
                contrasts.append([
                    row[1],
                    'T',
                    [cond for cond in row[2].split(' ')],
                    [float(w) for w in row[3].split(' ')]
                ])
            
            # raise if there are no contrasts in the file for the current task
            if not contrasts:
                raise AttributeError('No contrasts found for task {}'.format(task))
        else:
            print('Skipping contrast generation')
        
        return contrasts

    contrastgen = Node(Function(output_names=['contrasts'],
                                function=read_contrasts),
                       name='contrastgen')
    contrastgen.inputs.projDir = projDir
    contrastgen.inputs.task = task
    contrastgen.inputs.contrast = contrast
    contrastgen.inputs.contrast_opts = contrast_opts

    # provide first-level design parameters
    level1design = Node(fsl.Level1Design(), name='level1design')
    level1design.inputs.interscan_interval = TR
    level1design.inputs.bases = {'dgamma': {'derivs': False}}
    level1design.inputs.model_serial_correlations = True
    wf.connect(modelspec, 'session_info', level1design, 'session_info')
    if contrast == 'yes': # pass contrasts if requested in config file
        wf.connect(contrastgen, 'contrasts', level1design, 'contrasts')

    # use FSL FEAT for GLM
    modelgen = Node(fsl.FEATModel(), name='modelgen')
    wf.connect(level1design, 'fsf_files', modelgen, 'fsf_file')
    wf.connect(level1design, 'ev_files', modelgen, 'ev_files')

    # MapNode is a special version of Node that will create an instance of the Node [here ApplyMask()] for every item in the list from the input
    # interfield defines which input should be iterated over
    # after running, the outputs are collected into a list to pass to the next Node
    masker = MapNode(fsl.ApplyMask(), name='masker', iterfield=['in_file'])
    wf.connect(datasource, 'mni_mask', masker, 'mask_file')

    # if drop volumes was requested
    if dropvols !=0:
        wf.connect(roi, 'roi_file', masker, 'in_file')
    else:
        # if smoothing was requested
        if run_smoothing: 
            wf.connect(smooth, 'outputnode.smoothed_files', masker, 'in_file')
        else:
            # if smoothing was not requested
            wf.connect(mni_split, 'roi_file', masker, 'in_file')

    # configure GLM over design matrics
    glm = MapNode(fsl.FILMGLS(), name='filmgls', iterfield=['in_file'])
    if run_smoothing: 
        glm.inputs.mask_size = smoothing_kernel_size
        glm.inputs.smooth_autocorr = True
    wf.connect(masker, 'out_file', glm, 'in_file')
    wf.connect(modelgen, 'design_file', glm, 'design_file')
    wf.connect(modelgen, 'con_file', glm, 'tcon_file')
    wf.connect(modelgen, 'fcon_file', glm, 'fcon_file')

    # rename contrast output files with better filenames
    def substitutes(contrasts):
        """Datasink output path substitutes"""
        subs = []
        for i, con in enumerate(contrasts,1):
            # replace annoying chars in filename
            name = con[0].replace(' ', '').replace('>', '_gt_').lower()

            subs.append(('/cope%d.' % i, '/con_%d_%s_cope.' % (i,name)))
            subs.append(('/varcope%d.' % i, '/con_%d_%s_varcope.' % (i,name)))
            subs.append(('/zstat%d.' % i, '/con_%d_%s_zstat.' % (i, name)))
            subs.append(('/tstat%d.' % i, '/con_%d_%s_tstat.' % (i, name)))
            subs.append(('/_filmgls0/', '/'))
        return subs

    gensubs = Node(Function(function=substitutes), name='substitute_gen')
    wf.connect(contrastgen, 'contrasts', gensubs, 'contrasts')

    # extract components from working directory cache and store it at a different location
    sinker = Node(DataSink(), name='datasink')
    sinker.inputs.base_directory = outDir
    sinker.inputs.regexp_substitutions = [('_event_file.*run_id_', 'run'),
                                          ('_splithalf_id_0', ''),
                                          ('_splithalf_id_', '_splithalf'),
                                          ('_smooth0/',''),
                                          ('_roi',''),
                                          ('_filmgls0',''),
                                          ('MNI152NLin2009cAsym_res-2_desc','MNI')]
                                          
    # define where output files are saved
    wf.connect(gensubs, 'out', sinker, 'substitutions')
    wf.connect(mni_split, 'roi_file', sinker, 'preproc.@roi_file')
    if run_smoothing:
        wf.connect(smooth, 'outputnode.smoothed_files', sinker, 'preproc.@')
    wf.connect(modelgen, 'design_file', sinker, 'design.@design_file')
    wf.connect(modelgen, 'con_file', sinker, 'design.@tcon_file')
    wf.connect(modelgen, 'design_cov', sinker, 'design.@cov')
    wf.connect(modelgen, 'design_image', sinker, 'design.@design')
    wf.connect(glm, 'copes', sinker, 'model.@copes')
    wf.connect(glm, 'dof_file', sinker, 'model.@dof')
    wf.connect(glm, 'logfile', sinker, 'model.@log')
    wf.connect(glm, 'param_estimates', sinker, 'model.@pes')
    wf.connect(glm, 'residual4d', sinker, 'model.@res')
    wf.connect(glm, 'sigmasquareds', sinker, 'model.@ss')
    wf.connect(glm, 'thresholdac', sinker, 'model.@thresh')
    wf.connect(glm, 'tstats', sinker, 'model.@tstats')
    wf.connect(glm, 'varcopes', sinker, 'model.@varcopes')
    wf.connect(glm, 'zstats', sinker, 'model.@zstats')
    return wf

# define function to extract subject-level data for workflow
def process_subject(layout, projDir, derivDir, outDir, workDir, 
                    sub, task, ses, sub_runs, events, contrast, contrast_opts, timecourses,
                    regressor_opts, smoothing_kernel_size, resultsDir, hpf, dropvols, splithalf, sparse):
    """Grab information and start nipype workflow
    We want to parallelize runs for greater efficiency
    """
    import pandas as pd
    
    # define subject output directory
    suboutDir = op.join(outDir, 'sub-{}'.format(sub))
    
    # identify scan and events files
    if ses != 'no': # if session was provided
        print('Session information provided. Assuming data are organized into session folders.')
        
        # identify scans file (from derivDir bc artifact information is saved in the processed scans.tsv file)
        scans_tsv = glob.glob(op.join(derivDir, 'sub-{}'.format(sub), 'ses-{}'.format(ses), 'func', '*_scans.tsv'))[0]
        
        # identify events file
        events_all = glob.glob(op.join(derivDir, 'sub-{}'.format(sub), 'ses-{}'.format(ses), 'func', 'sub-{}_ses-{}_task-{}_*_events.tsv'.format(sub, ses, task)))
       
    else: # if session was 'no'
        # identify scans file (from derivDir bc artifact information is saved in the processed scans.tsv file)
        scans_tsv = glob.glob(op.join(derivDir, 'sub-{}'.format(sub), 'func', '*_scans.tsv'))[0]
        
        # identify events file
        events_all = glob.glob(op.join(derivDir, 'sub-{}'.format(sub), 'func', 'sub-{}_task-{}_*_events.tsv'.format(sub, task)))
    
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
    keepruns = scans_df[(scans_df.MotionExclusion == False) & (scans_df.task == task) & (scans_df.run.isin(['{:02d}'.format(r) for r in sub_runs]))].run
        
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
    
    # select timecourse files
    if not 'no' in timecourses: # if timecourses were provided (ie not 'no')
        print('ROI timecourses will be used as regressors')
        
        # make directory to save tc files
        tcDir = op.join(suboutDir , 'timecourses')
        os.makedirs(tcDir, exist_ok=True)
        
        # process each timecourse file and combine into dataframe
        tc_dat= []
        for t in timecourses:
            # read in timecourse file from project/data directory and combined into 1 dataframe
            tc_files = glob.glob(op.join(projDir, 'data', 'ROI_timecourses', '{}'.format(task), 'adult_TC-{}.tsv'.format(t)))
            tc = pd.read_csv(tc_files[0], sep='\t')
            tc_dat = tc.join(tc_dat)
        
        # remove timecourses if not specified in regressors list in config file
        tc_dat=tc_dat.filter(regressor_opts)

        # save as tc regressor file in tcDir
        tcreg_file = op.join(tcDir, 'sub-{}_ROI_timecourses.txt'.format(sub))
        pd.DataFrame(tc_dat).to_csv(tcreg_file, index=False, sep ='\t') 
        
        # assign timecourse files as events_files (duplicating for the number of kept runs because the same timecourses are used for each run)
        events_files = [] # initialize output
        events_files = np.repeat(tcreg_file, len(keepruns)).tolist()
    
    # select events files
    else: # if events files are trials within run
        # extract events in each run of data
        events_files = [] # initialize output
        for run in keepruns: # for each retained run
            ev_match = [evfile for evfile in events_all if 'run-{:02d}'.format(run) in evfile]
            events_files.append(ev_match[0])

    # if no events identified (e.g., resting state data)
    if not events_files:
        raise FileNotFoundError('No event files found for sub-{}'.format(sub))

    # call firstlevel workflow with extracted subject-level data
    wf = create_firstlevel_workflow(projDir, derivDir, workDir, suboutDir, 
                                    sub, task, ses, keepruns, events_files, events, contrast, contrast_opts, timecourses,
                                    regressor_opts, smoothing_kernel_size, resultsDir, hpf, TR, dropvols, splithalves, sparse)                                    
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
    
    # define output and working directories
    workDir, outDir = op.realpath(args.workDir), op.realpath(args.outDir)
    
    # identify analysis README file
    readme_file=op.join(outDir, 'README.txt')
    
    # read in configuration file and parse inputs
    config_file=pd.read_csv(args.config, sep='\t', header=None, index_col=0).replace({np.nan: None})
    bidsDir=config_file.loc['bidsDir',1]
    derivDir=config_file.loc['derivDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    task=config_file.loc['task',1]
    ses=config_file.loc['sessions',1]
    dropvols=int(config_file.loc['dropvols',1])
    smoothing_kernel_size=int(config_file.loc['smoothing',1])
    hpf=int(config_file.loc['hpf',1])
    contrast=config_file.loc['contrast',1]
    contrast_opts=config_file.loc['events',1].replace(' ','').split(',')
    events=config_file.loc['events',1].replace(' ','').replace(',','-').split('-')
    timecourses=config_file.loc['timecourses',1].replace(' ', '').split(',')
    regressor_opts=config_file.loc['regressors',1].replace(' ','').split(',')
    splithalf=config_file.loc['splithalf',1]
    overwrite=config_file.loc['overwrite',1]
    
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

    # print if BIDS directory is not found
    if not op.exists(bidsDir):
        raise IOError('BIDS directory {} not found.'.format(bidsDir))
    
    # print if the fMRIPrep directory is not found
    if not op.exists(derivDir):
        raise IOError('Derivatives directory {} not found.'.format(derivDir))
    
    # add config details to project README file
    with open(args.config, 'r') as file_1, open(readme_file, 'a') as file_2:
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
        sub_runs=list(map(int, sub_runs)) # convert to integers
              
        # create a process_subject workflow with the inputs defined above
        wf = process_subject(layout, args.projDir, derivDir, outDir, workDir, 
                             sub, task, ses, sub_runs, events, contrast, contrast_opts, timecourses,
                             regressor_opts, smoothing_kernel_size, resultsDir, hpf, dropvols, splithalf, args.sparse)
   
        # configure workflow options
        wf.config['execution'] = {'crashfile_format': 'txt',
                                  'remove_unnecessary_outputs': False,
                                  'keep_inputs': True}

        # run multiproc unless plugin specified in script call
        plugin = args.plugin if args.plugin else 'MultiProc'
        args_dict = {'n_procs' : 4}
        wf.run(plugin=plugin, plugin_args = args_dict)

# execute code when file is run as script (the conditional statement is TRUE when script is run in python)
if __name__ == '__main__':
    main()