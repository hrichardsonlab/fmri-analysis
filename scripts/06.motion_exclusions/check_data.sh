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

# define session (should always be 01 for EBC data, could alternatively put 'None' for non-EBC data)
ses=01

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"
codeDir="${projDir}/scripts/06.motion_exclusions"
qcDir="${projDir}/data/data_checking"

# define subjects from text document
subjs=$(cat $1) 

# extract sample from list of subjects filename (i.e., are these pilot or HV subjs)
sample=` basename $1 | cut -d '-' -f 3 | cut -d '.' -f 1 `
cohort=` basename $1 | cut -d '_' -f 1 `

# define data directories depending on sample information
if [[ ${sample} == 'pilot' ]]
then
	derivDir="/EBC/preprocessedData/${cohort}/derivatives/pilot"
elif [[ ${sample} == 'HV' ]]
then
	derivDir="/EBC/preprocessedData/${cohort}-adultpilot/derivatives"
else
	derivDir="/EBC/preprocessedData/${cohort}/derivatives"
fi

# print confirmation of sample and directory
echo 'Checking data files for' ${sample} 'data in' ${derivDir}

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

# iterate over subjects
while read p
do
	sub=$(echo ${p} | awk '{print $1}')
	
	# define subject derivatives directory depending on whether data are organized in session folders
	if [[ ${ses} != 'None' ]]
	then
		subDir="${derivDir}/sub-${sub}/ses-01/func"
		scan_file="${subDir}/sub-${sub}_ses-01_scans.tsv"
	else
		subDir="${derivDir}/sub-${sub}/func"
		scan_file="${subDir}/sub-${sub}_scans.tsv"
	fi
			
	# make subject data checking directory
	mkdir -p ${qcDir}/sub-${sub}
	
	# copy fMRIPrep output images to data checking directory for QC
	cp ${derivDir}/sub-${sub}/figures/*reconall_T1w.svg ${qcDir}/sub-${sub}
	cp ${derivDir}/sub-${sub}/figures/*MNI152NLin2009cAsym_desc-preproc_T1w.svg ${qcDir}/sub-${sub}
	cp ${derivDir}/sub-${sub}/figures/*desc-coreg_bold.svg ${qcDir}/sub-${sub}
	cp ${derivDir}/sub-${sub}/figures/*desc-sdc_bold.svg ${qcDir}/sub-${sub}
	
	# run singularity to create average functional mask
	singularity exec -C -B /EBC:/EBC																			\
	${singularityDir}/nipype.simg																				\
	/neurodocker/startup.sh python ${codeDir}/concat_brain_masks.py	-f ${derivDir} -s sub-${sub} -ss ${ses}
	
	# run singularity to generate files with motion information for run exclusion
	singularity exec -C -B /EBC:/EBC															\
	${singularityDir}/nipype.simg 																\
	/neurodocker/startup.sh python ${codeDir}/mark_motion_exclusions.py sub-${sub} ${derivDir}	\
	-w ${singularityDir}
	
	# give other users permissions to created files
	chmod a+wrx ${scan_file}
	chmod a+wrx ${subDir}/*_space-MNI152NLin2009cAsym_res-2_desc-brain_mask_allruns-BOLDmask.nii.gz

	# add scan information to data checking scans file
	if [ ! -f ${qcDir}/scans-group.tsv ] # on first loop, take header information from first subject
	then
		awk 'NR>0' ${scan_file} >> ${qcDir}/scans-group.tsv
	else
		awk 'NR>1' ${scan_file} >> ${qcDir}/scans-group.tsv
	fi

done <$1
