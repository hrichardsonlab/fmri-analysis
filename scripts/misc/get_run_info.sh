#!/bin/bash

################################################################################
# GET INFORMATION FOR EACH FUNCTIONAL RUN
################################################################################

# usage documentation - shown if no text file is provided or if script is run outside EBC directory
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./get_run_info.sh <list of subjects>"
	echo
	echo "Example:"
	echo "./get_run_info.sh TEBC-5y_subjs.txt"
	echo
	echo "TEBC-5y_subjs.txt is a file containing the participants to check:"
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

# indicate whether session folders are used (always 'yes' for EBC data)
sessions='yes'

# define directories
projDir=`cat ../../PATHS.txt`
qcDir="${projDir}/analysis"

# extract sample from list of subjects filename (i.e., are these pilot or HV subjs)
sample=` basename $1 | cut -d '-' -f 3 | cut -d '.' -f 1 `
cohort=` basename $1 | cut -d '_' -f 1 `

# define data directories depending on sample information
if [[ ${sample} == 'pilot' ]]
then
	bidsDir="/EBC/preprocessedData/${cohort}/BIDs_data/pilot"
elif [[ ${sample} == 'HV' ]]
then
	bidsDir="/EBC/preprocessedData/${cohort}-adultpilot/BIDs_data"
else
	bidsDir="/EBC/preprocessedData/${cohort}/BIDs_data"
fi

# print confirmation of sample and directory
echo "Getting run information for" ${sample} "participants..."

# create data checking directory if it doesn't exist
if [ ! -d ${qcDir} ]
then 
	mkdir -p ${qcDir}
fi

# delete data checking scans-group.tsv file if it already exists
if [ -f ${qcDir}/run_info.tsv ]
then 
	rm ${qcDir}/run_info.tsv
fi

# iterate over subjects
while read p
do
	sub=$(echo ${p} | awk '{print $1}')
	
	echo "Checking files for ${sub}"
	
	# define subject BIDS directory depending on whether data are organized in session folders
	if [[ ${sessions} == 'yes' ]]
	then
		subDir="${bidsDir}/sub-${sub}/ses-01/func"
	else
		subDir="${bidsDir}/sub-${sub}/func"
	fi
	
	# check whether subject has functional data
	if [ -d ${subDir} ]
	then
		files=`ls ${subDir}/*_bold.nii.gz`
		
		# print the subID in the very first column
		3dinfo -prefix_noext -nv ${files} >> ${qcDir}/tmp.tsv
		awk '{$1=$1};1' ${qcDir}/tmp.tsv >> ${qcDir}/run_info.tsv
		rm ${qcDir}/tmp.tsv
	else
		echo "No functional data found for sub-${sub}..."
	fi
	
done <$1
