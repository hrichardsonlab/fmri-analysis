#!/bin/bash

################################################################################
# RUN FREESURFER ON BIDS DATA
#
# This step must be run before the data can be fully processed through fMRIPrep
#
# The fMRIPrep singularity was installed using the following code:
# 	singularity build /EBC/processing/singularity_images/fmriprep-23.2.0.simg docker://nipreps/fmriprep:23.2.0
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
    echo
	echo
    echo "Usage:"
    echo "./run_freesurfer.sh <list of subjects>"
    echo
    echo "Example:"
    echo "./run_freesurfer.sh list.txt"
    echo
    echo "list.txt is a file containing the participants to run Freesurfer on:"
    echo "001"
    echo "002"
	echo "..."
    echo
	echo
	echo "This script must be run within the /EBC/ directory on the server due to space requirements."
	echo "The script will terminiate if run outside of the /EBC/ directory."
	echo
    echo "Script created by Manuel Blesa & Melissa Thye"
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
singularityDir="${projDir}/singularity_images"
bidsDir="/EBC/preprocessedData/TEBC-5y/BIDs_data"
derivDir="/EBC/preprocessedData/TEBC-5y/derivatives"

# create derivatives directory if it doesn't exist
if [ ! -d ${derivDir} ]
then 
	mkdir -p ${derivDir}
fi

# export freesurfer license file location
export license=/EBC/local/infantFS/freesurfer/license.txt

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export SINGULARITY_TMPDIR=${singularityDir}
export SINGULARITY_CACHEDIR=${singularityDir}
unset PYTHONPATH

# prepare some writeable bind-mount points
export SINGULARITYENV_TEMPLATEFLOW_HOME=${singularityDir}/fmriprep/.cache/templateflow

# display subjects
echo
echo "Running Freesurfer via fMRIPrep for..."
echo "${subjs}"

# ITERATE FOR ALL SUBJECTS IN THE TXT FILE
while read p
do
	
	ORIGINALNAME=` basename ${p} | cut -d '_' -f 1 `	# data folder name
	NAME=` basename ${p} |  cut -d "-" -f 3 `			# subj number from folder name
	
	# check whether the file already exists
	if [ ! -f ${derivDir}/sub-${NAME}/sourcedata/freesurfer/sub-${NAME}/mri/aparc+aseg.mgz ]
	then

		echo
		echo "Running anatomical workflow contained in fMRIprep for sub-${NAME}"
		echo
		
		# make output subject derivatives directory
		mkdir -p ${derivDir}/sub-${NAME}

		# run singularity
		singularity run -C -B /EBC:/EBC,${singularityDir}:/opt/templateflow \
		${singularityDir}/fmriprep-23.2.0.simg 								\
		${bidsDir} ${derivDir}/sub-${NAME}									\
		participant															\
		--participant-label ${NAME}											\
		--skip_bids_validation												\
		--nthreads 16														\
		--omp-nthreads 16													\
		--anat-only															\
		--output-space MNI152NLin2009cAsym:res-2 T1w						\
		--derivatives ${derivDir}/sub-${NAME}								\
		--stop-on-first-crash												\
		-w ${singularityDir}												\
		--fs-license-file ${license}  > ${derivDir}/sub-${NAME}/log_freesurfer_sub-${NAME}.txt
		
		# give other users permissions to created files
		chmod -R a+wrx ${derivDir}/sub-${NAME}

	fi

done <$1
