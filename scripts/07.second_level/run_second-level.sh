#!/bin/bash

################################################################################
# RUN THE SECOND LEVEL PIPELINE CALLING THE PIPELINE SCRIPT OF INTEREST
#
# This script runs the second-level pipeline specified in the command call within a nipype singularity
# A config.tsv file must exist in the project directory. This file has the processing options passed to
# the pipeline. These parameters are likely to vary for each study, so must be specified for each project.
#
# The nipype singularity was installed using the following code:
# 	SINGULARITY_TMPDIR=/EBC/processing SINGULARITY_CACHEDIR=/EBC/processing singularity build /EBC/processing/singularity_images/nipype-1.8.6.simg docker://nipype/nipype:latest
#
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./run_second-level.sh <pipeline script> <configuration file name> <list of subjects>"
	echo
	echo "Example:"
	echo "./run_second-level.sh secondlevel_pipeline.py config-pixar_mind-body.tsv TEBC-5y_subjs.txt"
	echo
	echo "the config file name (not path!) should be provided"
	echo
	echo "TEBC-5y_subjs.txt is a file containing the participants to process:"
	echo "001"
	echo "002"
	echo "..."
	echo
	echo
	echo "This script must be run within the /EBC/ directory on the server due to space requirements."
	echo "The script will terminiate if run outside of the /EBC/ directory."
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] | [ "$2" = "" ] | [ "$3" = "" ] && Usage

# if the script is run outside of the EBC directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/EBC/" ]]
then Usage
fi

# check that inputs are expected file types
if [ ! ${pipeline##*.} == "py" ]
then
	echo
	echo "The pipeline script was not found."
	echo "The script must be submitted with (1) a pipeline script, (2) a configuration file name, and (3) a subject list as in the example below."
	echo
	echo "./run_second-level.sh secondlevel_pipeline.py config-events.tsv TEBC-5y_subjs.txt"
	echo
	
	# end script and show full usage documentation
	Usage
fi

if [ ! ${2##*.} == "tsv" ]
then
	echo
	echo "The configuration file was not found."
	echo "The script must be submitted with (1) a pipeline script, (2) a configuration file name, and (3) a subject list as in the example below."
	echo
	echo "./run_second-level.sh secondlevel_pipeline.py config-events.tsv TEBC-5y_subjs.txt"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

if [ ! ${3##*.} == "txt" ]
then
	echo
	echo "The list of participants was not found."
	echo "The script must be submitted with (1) a pipeline script, (2) a configuration file name, and (3) a subject list as in the example below."
	echo
	echo "./run_second-level.sh secondlevel_pipeline.py config-events.tsv TEBC-5y_subjs.txt"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

# define pipeline, configuration options and subjects from files passed in script call
pipeline=$1
config=$2
subjs=$(cat $3 | awk 'NR>1 {print $1}') 
sub_file=$(readlink -f $3)
runs=$(cat $3 | awk ' NR>1{print $2}') 

# extract project and analysis name from config file
proj_name=` basename ${config} | cut -d '-' -f 2 | cut -d '_' -f 1 ` # name provided after hyphen and before underscore
analysis_name=` basename ${config} | cut -d '_' -f 2 | cut -d '.' -f 1 ` # name provided after underscore

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"
codeDir="${projDir}/scripts/07.second_level"
outDir="${projDir}/analysis/${proj_name}/${analysis_name}"

# convert the singularity image to a sandbox if it doesn't already exist to avoid having to rebuild on each run
if [ ! -d ${singularityDir}/nipype_sandbox ]
then
	singularity build --sandbox ${singularityDir}/nipype_sandbox ${singularityDir}/nipype_nilearn.simg
fi

# define output logfile
if [[ ${pipeline} == *'pipeline.py'* ]]
then
	export log_file="${projDir}/analysis/${proj_name}/${analysis_name}_${pipeline::-12}_logfile.txt"
else
	export log_file="${projDir}/analysis/${proj_name}/${analysis_name}_${pipeline::-3}_logfile.txt"
fi

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export SINGULARITY_TMPDIR=${singularityDir}
export SINGULARITY_CACHEDIR=${singularityDir}
unset PYTHONPATH

# display subjects
echo
echo "Running" ${pipeline} "for..."
echo "${subjs}"

# run second-level workflow using script specified in script call
singularity exec -C -B /EBC:/EBC						\
${singularityDir}/nipype_sandbox						\
/neurodocker/startup.sh python ${codeDir}/${pipeline}	\
-p ${projDir}											\
-s ${subjs}												\
-f ${sub_file}											\
-r ${runs}												\
-c ${projDir}/${config} | tee ${log_file}
