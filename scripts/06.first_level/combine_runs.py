"""
Individual run analysis using outputs from firstlevel pipeline

Adapted script from original notebook:
https://github.com/poldrack/fmri-analysis-vm/blob/master/analysis/postFMRIPREPmodelling/First%20and%20Second%20Level%20Modeling%20(FSL).ipynb

More information on what this script is doing - beyond the commented code - is provided on the lab's github wiki page
Nesting of functions: main > argparser > process_subject > create_secondlevel_workflow > data_grabber > process_data_files > gen_model_info > read_contrasts > substitutes

Requirement: BIDS dataset (including events.tsv), derivatives directory with fMRIPrep outputs, and modeling files

"""
from nipype.interfaces import fsl
from niflow.nipype1.workflows.fmri.fsl.estimate import create_fixed_effects_flow
import nipype.interfaces.io as nio
from nipype import Workflow, Node, MapNode, IdentityInterface, Function, DataSink, JoinNode, SelectFiles
import os
import os.path as op
import glob
import numpy as np
import pandas as pd
import argparse
import glob
import shutil

# define average runs workflow function
def combine_runs_workflow(projDir, derivDir, resultsDir, subDir, workDir, sub, ses, task, runs, events, contrast_opts, splithalf_id, space_name, name='sub-{}_task-{}_combineruns'):
    """Processing pipeline"""
    
    # initialize workflow
    wf = Workflow(name=name.format(sub, task),
                  base_dir=workDir)
                  
    # create output directory for combined runs
    if splithalf_id == 0:
        combinedDir = op.join(subDir, 'model', 'combined_runs')
    else:
        combinedDir = op.join(subDir, 'model', 'combined_runs', 'splithalf{}'.format(splithalf_id))
    
    # identify each run
    def get_runs(subDir, derivDir, sub, ses, task):
        from nipype import SelectFiles, Node
        import os
        import os.path as op
        
        # define mask file name, depending on whether session information is in directory/file names
        if ses != 'no': # if session was provided
            # define path to preprocessed mask data (subject derivatives func folder)
            funcDir = op.join(derivDir, 'sub-{}'.format(sub), 'ses-{}'.format(ses), 'func')
            mni_mask = op.join(funcDir, 'sub-{}_ses-{}_space-{}_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub, ses, space_name))
            
        else: # if session was 'no'
            # define path to preprocessed mask data (subject derivatives func folder)
            funcDir = op.join(derivDir, 'sub-{}'.format(sub), 'func')
            mni_mask = op.join(funcDir, 'sub-{}_space-{}_desc-brain_mask_allruns-BOLDmask.nii.gz'.format(sub, space_name))
        
        # copy mask file to subject resultsDir so it can be easily picked up in next step
        shutil.copy(mni_mask, op.join(subDir, 'preproc'))
     
        # get run data
        templates = {'run': 'model/run*'}
        gr = Node(SelectFiles(templates),
                  name='selectfiles')
        gr.inputs.base_directory = subDir
        gr.inputs.subj = sub
        gr.inputs.task = task
        gr.inputs.space_name = space_name
        
        return gr.run().outputs
    
    # extract all stats files for each run
    def get_run_data(run):
        from nipype import SelectFiles, Node

        templates = {'dof': 'dof',
                     'copes': '*_cope.nii.gz',
                     'varcopes': '*_varcope.nii.gz',
                     'mask' : '../../preproc/*BOLDmask.nii.gz'}
        sf = Node(SelectFiles(templates),
                  name='selectfiles')

        sf.inputs.base_directory = run
        
        return sf.run().outputs
    
    # define contrasts node to extract contrasts from contrasts.tsv file
    def read_contrasts(projDir, task, contrast_opts):
        import os.path as op
        import pandas as pd 

        contrasts = []
        
        # read in data contrasts file
        contrasts_file = op.join(projDir, 'files', 'contrast_files', 'contrasts.tsv')
            
        # raise error if contrasts file not found
        if not op.exists(contrasts_file):
            raise FileNotFoundError('Contrasts file {} not found.'.format(contrasts_file))
        
        # read in contrasts file
        contrast_info = pd.read_csv(contrasts_file, sep='\t')
            
        # set contrasts condition column to lowercase to avoid case errors and allow users flexibility when specifying events in config and contrasts files
        contrast_info['desc'] = contrast_info['desc'].str.lower()
        contrast_info['conds'] = contrast_info['conds'].str.lower()
            
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
        
        # raise error if there are no contrasts in the file for the current task
        if not contrasts:
            raise AttributeError('No contrasts found for task {}'.format(task))
                        
        return contrasts     
    
    # define substitutes node
    def substitutes(contrasts):
        """Datasink output path substitutes"""
        subs = []
        
        # for each contrast
        for i, con in enumerate(contrasts):
            # replace annoying chars in filename
            name = con[0].replace(' ', '').replace('>', '-').lower()

            subs.append(('_flameo%d/cope1.' % i, 'con_%i_%s_cope.' % (i+1,name)))
            subs.append(('_flameo%d/varcope1.' % i, 'con_%i_%s_varcope.' % (i+1,name)))
            subs.append(('_flameo%d/zstat1.' % i, 'con_%i_%s_zstat.' % (i+1,name)))
            subs.append(('_flameo%d/tstat1.' % i, 'con_%i_%s_tstat.' % (i+1,name)))
            subs.append(('_flameo%d/mask.' % i, 'con_%i_%s_mask.' % (i+1,name)))
            
        return subs
    
    # fixed_effects to combine stats across runs
    fixed_fx = create_fixed_effects_flow()
    
    # process subject files (i.e., run functions defined above)
    sub_runs = get_runs(subDir, derivDir, sub, ses, task)
    
    # convert tuple to easier to work with format
    if type(sub_runs.run) is str:
        sub_runs.run=[sub_runs.run]
    
    # if splithalf remove runs from other half
    if splithalf_id == 1:
        sub_runs.run = [path for path in sub_runs.run if not path.endswith('2')]
        
    if splithalf_id == 2:
        sub_runs.run = [path for path in sub_runs.run if not path.endswith('1')]
    
    print('Combining the following runs: {}'.format(sub_runs.run))
    
    # initialize stats files
    copes=[]
    varcopes=[]
    dofs=[]
    mask=[]
    included_runs=[]
    
    # grab stats for each run
    for run in sub_runs.run:
        included_runs.append(run)
        newrun=get_run_data(run)
        
        # convert tuple to easier to work with format
        if type(newrun.copes) == str:
            newcopes = [newrun.copes]
            newvarcopes = [newrun.varcopes]
        else:
            newcopes = newrun.copes
            newvarcopes = newrun.varcopes
        
        # append run data on each loop
        copes.append(newcopes)
        varcopes.append(newvarcopes)
        dofs.append(newrun.dof)
        mask.append(newrun.mask)
    
    fixed_fx.get_node('l2model').inputs.num_copes = len(included_runs)
    fixed_fx.get_node('flameo').inputs.mask_file = mask[0] # use the first mask since they should all be in same space
    
    # pass dof, copes, and varcopes files to fixed effects function
    zcopes = [list(cope) for cope in zip(*copes)]
    zvarcopes = [list(varcope) for varcope in zip(*varcopes)]
    fixed_fx.inputs.inputspec.dof_files = dofs
    fixed_fx.inputs.inputspec.copes=zcopes
    fixed_fx.inputs.inputspec.varcopes=zvarcopes
    
    # set up contrasts node
    contrastgen = Node(Function(output_names=['contrasts'],
                                function=read_contrasts),
                                name='contrastgen')
    contrastgen.inputs.projDir = projDir
    contrastgen.inputs.task = task
    contrastgen.inputs.contrast_opts = contrast_opts

    # connect contrasts generation with substitutes node
    gensubs = Node(Function(function=substitutes), 
                            name='substitute-gen')
    wf.connect(contrastgen, 'contrasts', gensubs, 'contrasts')
    
    # stats should equal number of conditions...
    sinker = Node(DataSink(), name='datasink')
    sinker.inputs.base_directory = combinedDir
    sinker.inputs.regexp_substitutions = [('_event_file.*run_id_', 'run')]
    
    dg = nio.DataGrabber(infields=['dir'],sort_filelist=True)
    dg.inputs.base_directory='/'
    dg.inputs.template = '%s/mask*'
    datasource = Node(dg, name='datasource')

    templates = {'mask': '*'}
    gr = Node(SelectFiles(templates), name='selectfiles')

    wf.connect(gensubs, 'out', sinker, 'substitutions')
    
    wf.connect(fixed_fx, 'outputspec.zstats', sinker, '@zstats')
    wf.connect(fixed_fx, 'outputspec.copes', sinker, '@copes')
    wf.connect(fixed_fx, 'outputspec.tstats', sinker, '@tstats')
    wf.connect(fixed_fx, 'outputspec.varcopes', sinker, '@varcopes')
    wf.connect(fixed_fx, 'flameo.stats_dir', datasource, 'dir')
    wf.connect(datasource, 'outfiles', sinker, '@maskfiles')
        
    return wf
    
# define function to process subject level data 
def process_subject(projDir, derivDir, resultsDir, workDir, sub, ses, task, sub_runs, events, contrast_opts, splithalf_id, space_name):

    # define subject output directory
    subDir = op.join(resultsDir, 'sub-{}'.format(sub))

    # raise an error if the firstlevel output directory doesn't exist
    if not subDir:
        raise FileNotFoundError('No firstlevel outputs found for sub-{}'.format(sub))
    
    # delete prior processing directories because cache files can interfere with workflow
    subworkDir = op.join(workDir, 'sub-{}_task-{}_combineruns'.format(sub, task))
    if os.path.exists(subworkDir):
        shutil.rmtree(subworkDir)
        
    # call timecourse workflow with extracted subject-level data
    wf = combine_runs_workflow(projDir, derivDir, resultsDir, subDir, workDir, sub, ses, task, sub_runs, events, contrast_opts, splithalf_id, space_name)  
                        
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
    derivDir=config_file.loc['derivDir',1]
    resultsDir=config_file.loc['resultsDir',1]
    task=config_file.loc['task',1]
    ses=config_file.loc['sessions',1]
    contrast_opts=config_file.loc['contrast',1].replace(' ','').split(',')
    events=list(set(config_file.loc['events',1].replace(' ','').replace(',','-').split('-')))
    splithalf=config_file.loc['splithalf',1]
    space=config_file.loc['space',1]
    
    # define working directory
    workDir = op.join(resultsDir, 'processing')
    
    # lowercase contrast_opts and events to avoid case errors - allows flexibility in how users specify events in config and contrasts files
    contrast_opts = [c.lower() for c in contrast_opts]
    events = [e.lower() for e in events]
    
    if splithalf == 'yes':
        splithalves = [1,2]
    else:
        splithalves = [0]
    
    if space == 'MNI':
        space_name = 'MNI152NLin2009cAsym_res-2'
        print('Pipeline will be run using outputs in {} space'.format(space_name))
    if space == 'native':
        space_name = 'T1w'
        print('Pipeline will be run using outputs in {} space'.format(space_name))

    # identify analysis README file
    readme_file=op.join(resultsDir, 'README.txt')
    
    # add config details to project README file
    with open(readme_file, 'a') as file_1:
        file_1.write('\n')
        file_1.write('Subject runs were averaged using the combine_runs.py script and options specified in the config file: {} \n'.format(args.config))

    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        for splithalf_id in splithalves:
            # pass runs for this sub
            sub_runs=args.runs[index]
            sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
            sub_runs=list(map(int, sub_runs)) # convert to integers
                  
            # create a process_subject workflow with the inputs defined above
            wf = process_subject(args.projDir, derivDir, resultsDir, workDir, sub, ses, task, sub_runs, events, contrast_opts, splithalf_id, space_name)
       
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