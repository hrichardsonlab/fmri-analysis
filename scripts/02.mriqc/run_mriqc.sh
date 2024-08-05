#!/bin/bash

################################################################################
# RUN MRIQC ON BIDS FORMATTED DATA
#
# The MRIQC singularity was installed using the following code:
# 	SINGULARITY_TMPDIR=/EBC/processing SINGULARITY_CACHEDIR=/EBC/processing singularity build /EBC/processing/singularity_images/mriqc-24.0.0.simg docker://nipreps/mriqc:24.0.0
#
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
    echo
	echo
    echo "Usage:"
    echo "./run_mriqc.sh <list of subjects>"
    echo
    echo "Example:"
    echo "./run_mriqc.sh TEBC-5y_subjs.txt"
    echo
    echo "TEBC-5y_subjs.txt is a file containing the participants to run MRIQC on:"
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
[ "$1" = "" ] && Usage

# if the script is run outside of the EBC directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/EBC/" ]]
then Usage
fi

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"

# convert the singularity image to a sandbox if it doesn't already exist to avoid having to rebuild on each run
if [ ! -d ${singularityDir}/mriqc_sandbox ]
then
	singularity build --sandbox ${singularityDir}/mriqc_sandbox ${singularityDir}/mriqc-24.0.0.simg
fi

# define subjects from text document
subjs=$(cat $1) 

# extract sample from list of subjects filename (i.e., are these pilot or HV subjs)
sample=` basename $1 | cut -d '-' -f 3 | cut -d '.' -f 1 `
cohort=` basename $1 | cut -d '_' -f 1 `

# define data directories depending on sample information
if [[ ${sample} == 'pilot' ]]
then
	bidsDir="/EBC/preprocessedData/${cohort}/BIDs_data/pilot"
	qcDir="/EBC/preprocessedData/${cohort}/derivatives/pilot/mriqc"
elif [[ ${sample} == 'HV' ]]
then
	bidsDir="/EBC/preprocessedData/${cohort}-adultpilot/BIDs_data"
	qcDir="/EBC/preprocessedData/${cohort}-adultpilot/derivatives/mriqc"

else
	bidsDir="/EBC/preprocessedData/${cohort}/BIDs_data"
	qcDir="/EBC/preprocessedData/${cohort}/derivatives/mriqc"
fi

# create QCdirectory if they don't exist
if [ ! -d ${qcDir} ]
then 
	mkdir -p ${qcDir}
fi

# display subjects
echo
echo "Running MRIQC for..."
echo "${subjs}"

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export SINGULARITY_TMPDIR=${singularityDir}
export SINGULARITY_CACHEDIR=${singularityDir}
unset PYTHONPATH

# run MRIQC (https://mriqc.readthedocs.io/en/latest/running.html#singularity-containers)
## generate subject reports
singularity run -B ${bidsDir}:${bidsDir} -B ${qcDir}:${qcDir} -B ${singularityDir}:${singularityDir}	\
${singularityDir}/mriqc_sandbox																			\
${bidsDir} ${qcDir}																						\
participant																								\
--participant_label ${subjs}																			\
--no-sub 																								\
--fd_thres 1																							\
-m T1w bold 																							\
-w ${singularityDir}

# generate group reports
singularity run -B ${bidsDir}:${bidsDir} -B ${qcDir}:${qcDir} -B ${singularityDir}:${singularityDir}	\
${singularityDir}/mriqc_sandbox																			\
${bidsDir} ${qcDir} group 																				\
-m T1w bold

# remove hidden files in singularity directory to avoid space issues
rm ${singularityDir}/config*
rm -r ${singularityDir}/.bids*
rm -r ${singularityDir}/mriqc_wf*
rm -r ${singularityDir}/reportlets
