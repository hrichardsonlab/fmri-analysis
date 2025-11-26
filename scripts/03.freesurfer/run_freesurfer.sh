#!/bin/bash

################################################################################
# RUN FREESURFER ON BIDS DATA
#
# This script is used in the event a participant *only* has anatomical data
#
# The fMRIPrep singularity was installed using the following code:
# 	SINGULARITY_TMPDIR=/RichardsonLab/processing SINGULARITY_CACHEDIR=/RichardsonLab/processing sudo singularity build /RichardsonLab/processing/singularity_images/fmriprep-24.0.0.simg docker://nipreps/fmriprep:24.0.0
#
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside RichardsonLab directory
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./run_freesurfer.sh <list of subjects>"
	echo
	echo "Example:"
	echo "./run_freesurfer.sh KMVPA_subjs.txt"
	echo
	echo "KMVPA_subjs.txt is a file containing the participants to run fMRIPrep on:"
	echo "001"
	echo "002"
	echo "..."
	echo
	echo
	echo "This script must be run within the /RichardsonLab/ directory on the server due to space requirements."
	echo "The script will terminiate if run outside of the /RichardsonLab/ directory."
	echo
	echo "Script created by Manuel Blesa & Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] && Usage

# if the script is run outside of the RichardsonLab directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/RichardsonLab/" ]]; 
then Usage
fi

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"

# define subjects from text document
subjs=$(cat $1 | awk '{print $1}') 

# extract study name from list of subjects filename
study=` basename $1 | cut -d '_' -f 1 `

# define data directories depending on study information
bidsDir="/RichardsonLab/preprocessedData/${study}"
derivDir="${bidsDir}/derivatives"

# create derivatives directory if it doesn't exist
if [ ! -d ${derivDir} ]
then 
	mkdir -p ${derivDir}
fi

# export freesurfer license file location
export license=/RichardsonLab/processing/tools/license.txt

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export APPTAINER_TMPDIR=${singularityDir}
export APPTAINER_CACHEDIR=${singularityDir}
unset PYTHONPATH

# prepare some writeable bind-mount points
export APPTAINERENV_TEMPLATEFLOW_HOME=${singularityDir}/fmriprep/.cache/templateflow

# display subjects
echo
echo "Running Freesurfer via fMRIPrep for..."
echo "${subjs}"

# iterate for all subjects in the text file
while read p
do	
	NAME=` basename ${p} | awk -F- '{print $NF}' `	# subj number
	
	# check whether the file already exists
	if [ ! -f ${derivDir}/sourcedata/freesurfer/sub-${NAME}/mri/aparc+aseg.mgz ]
	then

		echo
		echo "Running anatomical workflow contained in fMRIprep for sub-${NAME}"
		echo
		
		# make output subject derivatives directory
		mkdir -p ${derivDir}/sub-${NAME}

		# run singularity
		singularity run -B /RichardsonLab:/RichardsonLab,${singularityDir}:/opt/templateflow \
		${singularityDir}/fmriprep-24.0.0.simg  							\
		${bidsDir} ${derivDir}												\
		participant															\
		--participant-label ${NAME}											\
		--skip_bids_validation												\
		--nthreads 8														\
		--omp-nthreads 4													\
		--anat-only															\
		--output-space MNI152NLin2009cAsym:res-2 T1w						\
		--derivatives ${derivDir}											\
		--stop-on-first-crash												\
		-w ${singularityDir}												\
		--fs-license-file ${license}  > ${derivDir}/sub-${NAME}/log_freesurfer_sub-${NAME}.txt
		
		# move subject report and freesurfer output files to appropriate directories
		mv ${derivDir}/*dseg.tsv ${derivDir}/sourcedata/freesurfer
		mv ${derivDir}/sub-${NAME}.html ${derivDir}/sub-${NAME}
			
		# give other users permissions to created files
		#chmod -R a+wrx ${derivDir}/sub-${NAME}

	fi

done <$1
