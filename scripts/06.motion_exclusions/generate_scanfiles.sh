#!/bin/bash

################################################################################
# GENERATE THE SCANS.TSV FILE THAT WILL BE USED TO MARK RUN EXCLUSIONS
# 
# More information on these files: 
#	https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files.html#scans-file
################################################################################

# usage documentation - shown if no text file is provided
Usage() {
    echo
    echo "Usage:"
    echo "./generate_scanfiles.sh <list of subject folders to convert>"
    echo
    echo "Example:"
    echo "./generate_scanfiles.sh list.txt"
    echo 
    echo "list.txt is a file containing the participants to generate the scans.tsv file for:"
    echo "001"
    echo "002"
	echo "..."
    echo
	echo
    echo "Script created by Melissa Thye"
    echo
    exit
}
[ "$1" = "" ] && Usage

# define subjects from text document
subjs=$(cat $1)

# define session (should always be 01 for EBC data)
ses=01

# define directories
bidsDir="/EBC/preprocessedData/TEBC-5y/BIDs_data/pilot"
derivDir="/EBC/preprocessedData/TEBC-5y/derivatives/pilot"

# ITERATE FOR ALL SUBJECTS IN THE TXT FILE
while read p
do
	ORIGINALNAME=` basename ${p} | cut -d '_' -f 1 `	# data folder name
	NAME=` basename ${p} |  cut -d "-" -f 3 `			# subj number from folder name
	
	# create scan.tsv file for each subject who has functional data
	if [ -d ${bidsDir}/sub-${NAME}/ses-${ses}/func ] # if the subject has a functional data folder
	then
	
		echo
		echo "Generating scans.tsv file for sub-${NAME}"
		echo
		
		# delete scans.tsv file if it already exists
		if [ -f ${derivDir}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_scans.tsv ]
		then 
			rm ${bidsDir}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_scans.tsv
			rm ${derivDir}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_scans.tsv
		fi
		
		# print run info to scan.tsv file
		printf "filename" >> ${bidsDir}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_scans.tsv
	
		# list of functional files
		files=(`ls ${bidsDir}/sub-${NAME}/ses-${ses}/func/*nii.gz`)
		
		# for each file in the func directory, add filename to scans.tsv file
		for f in ${files[@]}
		do
			# extract file name (remove full path)
			current=`basename ${f}`
		
			# add file name (with directory) to scans.tsv file
			name=""
			name='\nfunc/'${current}
			printf ${name} >> ${bidsDir}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_scans.tsv
		done
	fi
	
	# copy scans.tsv to derivDir
	cp ${bidsDir}/sub-${NAME}/ses-${ses}/func/sub-${NAME}_ses-${ses}_scans.tsv ${derivDir}/sub-${NAME}/ses-${ses}/func
	
done <$1

