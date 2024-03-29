#!/bin/bash

################################################################################
# RUN THE FIRST LEVEL PIPELINE CALLING THE PIPELINE SCRIPT OF INTEREST
#
# This script runs the first-level pipeline specified in the command call within a nipype singularity
#
# The nipype singularity was installed using the following code:
# 	singularity build /EBC/processing/singularity_images/nipype-1.8.6.simg docker://nipype/nipype:latest
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
    echo
	echo
    echo "Usage:"
    echo "./run_first-level.sh <pipeline script> <list of subjects>"
    echo
    echo "Example:"
    echo "./run_first-level.sh pipeline-pixar_events.py list.txt"
    echo
    echo "list.txt is a file containing the participants to check:"
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
[ "$1" = "" ] | [ "$2" = "" ] && Usage

# define subjects from text document
pipeline=$1
subjs=$(cat $2) 

# check that inputs are expected file types
if [ ! ${pipeline##*.} == "py" ]
then
	echo
	echo "The pipeline script was not found."
	echo "The script must be submitted with a pipeline script then a subject list as in the example below."
	echo
	echo "./run_first-level.sh pipeline-pixar_events.py list.txt"
	echo
	
	# end script and show full usage documentation
	Usage
fi

if [ ! ${2##*.} == "txt" ]
then
	echo
	echo "The list of participants was not found."
	echo "The script must be submitted with a pipeline script then a subject list as in the example below."
	echo
	echo "./run_first-level.sh pipeline-pixar_events.py list.txt"
	echo
	
	# end script and show full usage documentation	
	Usage
fi

# if the script is run outside of the EBC directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/EBC/" ]]
then Usage
fi

# extract name of pipeline for output directory
outname=` basename ${pipeline} | cut -d '-' -f 2 | cut -d '.' -f 1 `

# define session (should always be 01, could alternatively comment out if no session info/directory in BIDS data)
ses=01

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"
codeDir="${projDir}/scripts/07.first_level"
bidsDir="/EBC/preprocessedData/TEBC-5y/BIDs_data"
derivDir="/EBC/preprocessedData/TEBC-5y/derivatives"
outDir="${projDir}/analysis/${outname}"

# create working and output directories if they don't exist
if [ ! -d ${outDir} ] || [ ! -d ${outDir}/processing ]
then 
	echo
	echo "Creating project analysis directory: ${outDir}"
	echo
	
	mkdir -p ${outDir}
	mkdir -p ${outDir}/processing 
	
	# make README doc that can be populated later
	echo "First level outputs were generated by running the ${pipeline} pipeline" > ${outDir}/README.txt	
fi

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export SINGULARITY_TMPDIR=${singularityDir}
export SINGULARITY_CACHEDIR=${singularityDir}
unset PYTHONPATH

# display subjects
echo
echo "Running" ${pipeline} "pipeline for..."
echo "${subjs}"

# run first-level workflow using script specified in script call
singularity exec -C -B /EBC:/EBC						\
${singularityDir}/nipype.simg							\
/neurodocker/startup.sh python ${codeDir}/${pipeline}	\
${projDir}												\
-b ${bidsDir}											\
-d ${derivDir}											\
-w ${outDir}/processing									\
-o ${outDir}											\
-ss ${ses}												\
-s ${subjs}
