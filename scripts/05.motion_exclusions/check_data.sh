#!/bin/bash

###############################################################################
# MARK RUNS THAT EXCEED MOTION THRESHOLDS
#
# This script moves select fMRIPrep output files to a data checking directory for ease of QC
# It then runs the concat_brain_masks.py and mark_motion_exclusions.py scripts within a nipype singularity
# concat_brain_masks.py outputs an averaged, binarized EPI mask using whatever functional data each subject has
# mark_motion_exclusions.py uses framewise displacement and standardized dvars to identify outlier volumes
# If more than the specified proportion of the volumes in a run are tagged, the run is marked for exclusion in a generated tsv file (in subject derivatives folder and data checking directory)
#
# The nipype singularity was installed using the following code:
# 	SINGULARITY_TMPDIR=/RichardsonLab/processing SINGULARITY_CACHEDIR=/RichardsonLab/processing sudo singularity build /RichardsonLab/processing/singularity_images/nipype.simg docker://nipype/nipype:latest
#
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./check_data.sh <configuration file name> <list of subjects>"
	echo
	echo "Example:"
	echo "./check_data.sh config-pixar_mind-body.tsv KMVPA_subjs.txt"
	echo
	echo "KMVPA_subjs.txt is a file containing the participants to check:"
	echo "001"
	echo "002"
	echo "..."
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

if [ ! ${1##*.} == "tsv" ]
then
	echo
	echo "The configuration file was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject list as in the example below."
	echo
	echo "./check_data.sh config-pixar_mind-body.tsv KMVPA_subjs.txt"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

if [ ! ${2##*.} == "txt" ]
then
	echo
	echo "The list of participants was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject list as in the example below."
	echo
	echo "./check_data.sh config-pixar_mind-body.tsv KMVPA_subjs.txt"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

# define configuration options and subjects from files passed in script call
config=$1
subjs=$(cat $2 | awk '{print $1}') 

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"
codeDir="${projDir}/scripts/05.motion_exclusions"

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export APPTAINER_TMPDIR=${singularityDir}
export APPTAINER_CACHEDIR=${singularityDir}
unset PYTHONPATH

# display subjects
echo
echo "Checking data for..."
echo "${subjs}"

# iterate over subjects
while read p
do
	sub=$(echo ${p} | awk '{print $1}')
			
	# run singularity to create average functional mask
	singularity exec -B /RichardsonLab:/RichardsonLab				\
	${singularityDir}/nipype_nilearn.simg							\
	/neurodocker/startup.sh python ${codeDir}/concat_brain_masks.py \
	-s ${sub} \
	-c ${projDir}/${config}
	
	# run singularity to generate files with motion information for run exclusion
	singularity exec -B /RichardsonLab:/RichardsonLab					\
	${singularityDir}/nipype_nilearn.simg 								\
	/neurodocker/startup.sh python ${codeDir}/mark_motion_exclusions.py \
	-s ${sub} 															\
	-c ${projDir}/${config} 											\
	-w ${singularityDir}

done <$2
