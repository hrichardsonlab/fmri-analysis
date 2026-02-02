"""
Calculate percent signal change using the outputs from the firstlevel model.

This script will:
(1) calculate and output the voxelwise mean signal value
(2) calculate percent signal change for requested conditions (from config file) using the following approach:
PSC = (voxelwise beta map / voxelwise mean signal value) * 100

The outputs are saved in the *psc* folder for each run for each subject. 

This script should be run prior to the extract stats script is the user wants to extract mean PSC values.

"""
#from nipype.interfaces import fsl
from nipype.interfaces.fsl import MeanImage, BinaryMaths, ImageMaths
import nipype.interfaces.io as nio
#from nipype import Workflow, Node, MapNode, IdentityInterface, Function, DataSink, JoinNode, SelectFiles
from nipype import Workflow, Node
import os
import os.path as op
import glob
import numpy as np
import pandas as pd
import argparse
import glob
import shutil

# define calc psc workflow function
def calc_psc_workflow(projDir, resultsDir, smoothDir, workDir, sub, ses, task, sub_runs, contrast_opts, splithalf_id, name='{}_task-{}_calcpsc'):

    # define subject output directory
    subDir = op.join(resultsDir, '{}'.format(sub))

    # raise an error if the firstlevel output directory doesn't exist
    if not subDir:
        raise FileNotFoundError('No firstlevel outputs found for {}'.format(sub))
    
    # delete prior processing directories because cache files can interfere with workflow
    subworkDir = op.join(workDir, '{}_task-{}_calcpsc'.format(sub, task))
    if os.path.exists(subworkDir):
        shutil.rmtree(subworkDir)
        
    # initialize workflow
    wf = Workflow(name=name.format(sub, task),
                  base_dir=workDir)
                  
    # for each run
    for r in sub_runs:
        # create output directory for psc outputs
        if splithalf_id == 0:
            pscDir = op.join(subDir, 'psc', 'run{}'.format(r))
        else:
            pscDir = op.join(subDir, 'psc', 'run()_splithalf{}'.format(r, splithalf_id))
        
        os.makedirs(pscDir, exist_ok=True)
        
        # grab preproc file (depending on smoothing options in config file)
        if smoothDir:
            preprocDir = op.join(smoothDir, '{}'.format(sub), 'preproc', 'run{}'.format(r))
        else:
            preprocDir = op.join(resultsDir, '{}'.format(sub), 'preproc', 'run{}'.format(r))
        
        # default to assuming preproc file is smooth, but use nonsmoothed output if not
        preproc_file = glob.glob(op.join(preprocDir, '*_smooth.nii.gz'))
        if not preproc_file:
            preproc_file = glob.glob(op.join(preprocDir, '*_bold.nii.gz'))
            
        print('Will use the following file to calculate voxelwise mean in run {}: {}'.format(r, preproc_file))
        
        # define output run mean file
        mean_file = op.join(pscDir, 'voxelwise_mean.nii.gz')
        
        # step 1: calculate voxelwise mean across this run
        meanfunc = Node(MeanImage(), name='meanfunc_run{}'.format(r))
        meanfunc.inputs.dimension = 'T' # returns the mean across time
        meanfunc.inputs.in_file = preproc_file[0]
        meanfunc.inputs.out_file = mean_file
        
        # add the meanfunc node to the workflow
        wf.add_nodes([meanfunc])

        # loop over beta maps
        for b in contrast_opts:
            print('Calculating percent signal change for {} condition'.format(b))
            
            # grab copes file corresponding to beta map
            beta_file = glob.glob(op.join(subDir, 'model', 'run{}'.format(r), 'con*_{}_cope.nii.gz'.format(b)))[0]
            
            print('Using {} cope file for calculation'.format(beta_file))
            
            # define psc output files
            div_file = op.join(pscDir, '{}_divided.nii.gz'.format(b))
            psc_file = op.join(pscDir, '{}_psc.nii.gz'.format(b))

            # step 2: divide beta map by the voxelwise mean_file
            dividefunc = Node(BinaryMaths(), name='dividefunc_run{}_{}'.format(r,b))
            dividefunc.inputs.operation = 'div' # divide
            dividefunc.inputs.in_file = beta_file
            #dividefunc.inputs.out_file = div_file # can return this file as a data checking step
            
            # step 3: multiply output maps by 100 to get percent
            multiplyfunc = Node(ImageMaths(), name='multiplyfunc_run{}_{}'.format(r,b))
            multiplyfunc.inputs.args = '-mul 100'
            multiplyfunc.inputs.out_file = psc_file
            
            # add nodes to workflow and connect inputs
            wf.add_nodes([dividefunc, multiplyfunc])
            wf.connect(meanfunc, 'out_file', dividefunc, 'operand_file')
            wf.connect(dividefunc, 'out_file', multiplyfunc, 'in_file')
                        
            
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
    resultsDir=config_file.loc['resultsDir',1]
    smoothDir=config_file.loc['smoothDir',1]
    task=config_file.loc['task',1]
    ses=config_file.loc['sessions',1]
    contrast_opts=config_file.loc['contrast',1].replace(' ','').split(',')
    splithalf=config_file.loc['splithalf',1]
    
    # define working directory
    workDir = op.join(resultsDir, 'processing')
    
    # lowercase contrast_opts and events to avoid case errors - allows flexibility in how users specify events in config and contrasts files
    contrast_opts = [c.lower() for c in contrast_opts]
    
    if splithalf == 'yes':
        splithalves = [1,2]
    else:
        splithalves = [0]
    
    # identify analysis README file
    readme_file=op.join(resultsDir, 'README.txt')
    
    # add config details to project README file
    with open(readme_file, 'a') as file_1:
        file_1.write('\n')
        file_1.write('Percent signal change was calculated using the calc_psc.py script and options specified in the config file: {} \n'.format(args.config))

    # for each subject in the list of subjects
    for index, sub in enumerate(args.subjects):
        for splithalf_id in splithalves:
            # check that run info was provided in subject list, otherwise throw an error
            if not args.runs:
                raise IOError('Run information missing. Make sure you are passing a subject-run list to the pipeline!')
            
            # pass runs for this sub
            sub_runs=args.runs[index]
            sub_runs=sub_runs.replace(' ','').split(',') # split runs by separators
            if sub_runs == ['NA']: # if run info isn't used in file names
                sub_runs = [1] # because outputs saved in run1 folders even if run info isn't specified in file name
            else:
                sub_runs=list(map(int, sub_runs)) # convert to integers
                  
            # create calc psc workflow with the inputs defined above
            wf = calc_psc_workflow(args.projDir, resultsDir, smoothDir, workDir, sub, ses, task, sub_runs, contrast_opts, splithalf_id)
       
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