#!/bin/bash

################################################################################
# RUN MRIQC ON BIDS FORMATTED DATA
#
# The MRIQC singularity was installed using the following code:
# The cache is created at $HOME/.singularity/cache by default and there is limited space in this directory, so change the location of the cache
#	export SINGULARITY_TMPDIR=$PWD 
# 	export SINGULARITY_CACHEDIR=$PWD
# 	singularity build /EBC/processing/singularity_images/mriqc-23.1.0.simg docker://nipreps/mriqc:23.1.0
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
    echo
	echo
    echo "Usage:"
    echo "./run_mriqc.sh <list of subjects>"
    echo
    echo "Example:"
    echo "./run_mriqc.sh list.txt"
    echo
    echo "list.txt is a file containing the participants to run MRIQC on:"
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

# define subjects from text document
subjs=$(cat $1) 

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="$projDir/singularity_images"
bidsDir="/EBC/preprocessedData/TEBC-5y/BIDs_data"
qcDir="/EBC/preprocessedData/TEBC-5y/derivatives/mriqc"

# create QC directory if it doesn't exist
if [ ! -d ${qcDir} ]
then 
	mkdir -p ${qcDir}
fi

# display subjects
echo
echo "Running MRIQC for..."
echo "${subjs}"

# change the location of the singularity cache
export SINGULARITY_TMPDIR=$singularityDir
export SINGULARITY_CACHEDIR=$singularityDir
unset PYTHONPATH

# run MRIQC (https://mriqc.readthedocs.io/en/latest/running.html#singularity-containers)
## generate subject reports
singularity run -B ${bidsDir}:${bidsDir} -B ${qcDir}:${qcDir} -B ${singularityDir}:${singularityDir}	\
${singularityDir}/mriqc-23.1.0.simg																		\
${bidsDir} ${qcDir}																						\
participant																								\
--participant_label ${subjs}																			\
--no-sub 																								\
--fd_thres 2																							\
-m T1w bold																								\
-w ${singularityDir}

## generate group reports
singularity run -B ${bidsDir}:${bidsDir} -B ${qcDir}:${qcDir} -B ${singularityDir}:${singularityDir}	\
${singularityDir}/mriqc-23.1.0.simg																		\
${bidsDir} ${qcDir} group 																				\
-m T1w bold

# remove hidden files in singularity directory to avoid space issues
rm ${singularityDir}/.mriqc*
rm -r ${singularityDir}/.bids*
