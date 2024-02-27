#!/bin/bash

################################################################################
# MARK RUNS THAT EXCEED MOTION THRESHOLDS
#
# This script moves select fMRIPrep output files to a data checking directory for ease of QC
# It then runs the concat_brain_masks.py and mark_motion_exclusions.py scripts within a nipype singularity/cache
# concat_brain_masks.py outputs an averaged, binarized EPI mask from whatever functional data each subject has
# mark_motion_exclusions.py uses framewise displacement and standardized dvars to identify outlier volumes
# If more than 1/3rd of the volumes in a given run are tagged, the run is marked for exclusion in a generated tsv file (in subject derivatives folder and data checking directory)
#
# The nipype singularity was installed using the following code:
# 	singularity build /EBC/processing/singularity_images/nipype-1.8.6.simg docker://nipype/nipype:latest
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
    echo
	echo
    echo "Usage:"
    echo "./check_data.sh <list of subjects>"
    echo
    echo "Example:"
    echo "./check_data.sh list.txt"
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
[ "$1" = "" ] && Usage

# if the script is run outside of the EBC directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/EBC/" ]]
then Usage
fi

# define subjects from text document
subjs=$(cat $1) 

# define session (should always be 01, could alternatively comment out if no session info/directory in BIDS data)
ses=01

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"
codeDir="${projDir}/scripts/06.motion_exclusions"
derivDir="/EBC/preprocessedData/TEBC-5y/derivatives"
qcDir="${projDir}/data/data_checking"

# create data checking directory if it doesn't exist
if [ ! -d ${qcDir} ]
then 
	mkdir -p ${qcDir}
fi

# delete data checking scans-group.tsv file if it already exists
if [ -f ${qcDir}/scans-group.tsv ]
then 
	rm ${qcDir}/scans-group.tsv
fi

# change the location of the singularity cache ($HOME/.singularity/cache by default, but limited space in this directory)
export SINGULARITY_TMPDIR=${singularityDir}
export SINGULARITY_CACHEDIR=${singularityDir}
unset PYTHONPATH

# display subjects
echo
echo "Checking data for..."
echo "${subjs}"

# ITERATE FOR ALL SUBJECTS IN THE TXT FILE
while read p
do

	ORIGINALNAME=` basename ${p} | cut -d '_' -f 1 `	# data folder name
	NAME=` basename ${p} |  cut -d "-" -f 3 `			# subj number from folder name
		
	# make subject data checking directory
	mkdir -p ${qcDir}/sub-${NAME}
	
	# copy fMRIPrep output images to data checking directory for QC
	cp ${derivDir}/sub-${NAME}/sub-${NAME}/figures/*reconall_T1w.svg ${qcDir}/sub-${NAME}
	cp ${derivDir}/sub-${NAME}/sub-${NAME}/figures/*MNI152NLin2009cAsym_desc-preproc_T1w.svg ${qcDir}/sub-${NAME}
	cp ${derivDir}/sub-${NAME}/sub-${NAME}/figures/*desc-coreg_bold.svg ${qcDir}/sub-${NAME}
	cp ${derivDir}/sub-${NAME}/sub-${NAME}/figures/*desc-sdc_bold.svg ${qcDir}/sub-${NAME}
	
	# run singularity to create average functional mask
	singularity exec -C -B /EBC:/EBC																			\
	${singularityDir}/nipype.simg																				\
	/neurodocker/startup.sh python ${codeDir}/concat_brain_masks.py	-f ${derivDir} -s sub-${NAME} -ss ${ses}
	
	# run singularity to generate files with motion information for run exclusion
	singularity exec -C -B /EBC:/EBC															\
	${singularityDir}/nipype.simg 																\
	/neurodocker/startup.sh python ${codeDir}/mark_motion_exclusions.py sub-${NAME} ${derivDir}	\
	-w ${singularityDir}
	
	# give other users permissions to created files
	chmod a+wrx ${derivDir}/sub-${NAME}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_scans.tsv
	chmod a+wrx ${derivDir}/sub-${NAME}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz
	
	# add scan information to data checking scans file
	if [ ! -f ${qcDir}/scans-group.tsv ] # on first loop, take header information from first subject
	then
		awk 'NR == 0' ${derivDir}/sub-${NAME}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_scans.tsv >> ${qcDir}/scans-group.tsv
	else
		awk 'NR > 1' ${derivDir}/sub-${NAME}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_scans.tsv >> ${qcDir}/scans-group.tsv
	fi

done <$1
