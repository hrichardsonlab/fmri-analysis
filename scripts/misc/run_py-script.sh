#!/bin/bash

################################################################################
# RUN MISC PYTHON SCRIPTS ASSOCIATED WITH FMRI PIPELINE
#
# This script runs the python script specified in the command call within a nipype singularity:
# A config.tsv file must exist in the project directory. This file has the processing options passed to
# the pipeline. These parameters are likely to vary for each study, so must be specified for each project.
#
# The nipype singularity was installed using the following code:
# 	SINGULARITY_TMPDIR=/EBC/processing SINGULARITY_CACHEDIR=/EBC/processing singularity build /EBC/processing/singularity_images/nipype-1.8.6.simg docker://nipype/nipype:latest
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./run_py-script.sh <python script> <configuration file name>"
	echo
	echo "Example:"
	echo "./run_py-script.sh resample_ROIs.py config-pixar_mind-body.tsv"
	echo
	echo "the config file name (not path!) should be provided"
	echo
	echo
	echo "This script must be run within the /EBC/ directory on the server due to space requirements."
	echo "The script will terminiate if run outside of the /EBC/ directory."
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] | [ "$2" = "" ] && Usage

# if the script is run outside of the EBC directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/EBC/" ]]
then Usage
fi

# check that inputs are expected file types
if [ ! ${pipeline##*.} == "py" ]
then
	echo
	echo "The pipeline script was not found."
	echo "The script must be submitted with (1) a python script and (2) a configuration file name as in the example below."
	echo
	echo "./run_py-script.sh resample_ROIs.py config-pixar_mind-body.tsv"
	echo
	
	# end script and show full usage documentation
	Usage
fi

if [ ! ${2##*.} == "tsv" ]
then
	echo
	echo "The configuration file was not found."
	echo "The script must be submitted with (1) a python script and (2) a configuration file name as in the example below."
	echo
	echo "./run_py-script.sh resample_ROIs.py config-pixar_mind-body.tsv"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

# define python script and configuration options from files passed in script call
script=$1
config=$2

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"
codeDir="${projDir}/scripts/misc"

# convert the singularity image to a sandbox if it doesn't already exist to avoid having to rebuild on each run
if [ ! -d ${singularityDir}/nipype_sandbox ]
then
	singularity build --sandbox ${singularityDir}/nipype_sandbox ${singularityDir}/nipype_nilearn.simg
fi

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export SINGULARITY_TMPDIR=${singularityDir}
export SINGULARITY_CACHEDIR=${singularityDir}
unset PYTHONPATH

# display script
echo
echo "Running" ${script} "for..."
echo

# run first-level workflow using script specified in script call
singularity exec -C -B /EBC:/EBC						\
${singularityDir}/nipype_sandbox						\
/neurodocker/startup.sh python ${codeDir}/${script}		\
-p ${projDir}											\
-c ${projDir}/${config}
