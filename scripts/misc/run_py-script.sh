#!/bin/bash

################################################################################
# RUN MISC PYTHON SCRIPTS ASSOCIATED WITH FMRI PIPELINE
#
# This script runs the python script specified in the command call within a nipype singularity:
# A config.tsv file must exist in the project directory. This file has the processing options passed to
# the pipeline. These parameters are likely to vary for each study, so must be specified for each project.
#
# The nipype singularity was installed using the following code:
# 	SINGULARITY_TMPDIR=/RichardsonLab/processing SINGULARITY_CACHEDIR=/RichardsonLab/processing sudo singularity build /RichardsonLab/processing/singularity_images/nipype.simg docker://nipype/nipype:latest
#
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside RichardsonLab directory
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./run_py-script.sh <python script> <configuration file name>"
	echo
	echo "Example:"
	echo "./run_py-script.sh resample_ROIs.py config-kmvpa_mental-physical.tsv"
	echo
	echo "the config file name (not path!) should be provided"
	echo
	echo
	echo "This script must be run within the /RichardsonLab/ directory on the server due to space requirements."
	echo "The script will terminiate if run outside of the /RichardsonLab/ directory."
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] | [ "$2" = "" ] && Usage

# if the script is run outside of the RichardsonLab directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/RichardsonLab/" ]]; 
then Usage
fi

# check that inputs are expected file types
if [ ! ${1##*.} == "py" ]
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

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export APPTAINER_TMPDIR=${singularityDir}
export APPTAINER_CACHEDIR=${singularityDir}
unset PYTHONPATH

# display script
echo
echo "Running" ${script} "for..."
echo

# run first-level workflow using script specified in script call
singularity exec -B /RichardsonLab:/RichardsonLab	\
${singularityDir}/nipype_nilearn.simg					\
/neurodocker/startup.sh python ${codeDir}/${script}		\
-p ${projDir}											\
-c ${projDir}/${config}
