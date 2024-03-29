#!/bin/bash

################################################################################
# GENERATE THE EVENTS FILES USED TO IDENTIFY EVENTS OF INTEREST IN THE FUNCTIONAL DATA
# 
# Each functional run should have a corresponding events file 
# The name of the functional run is indicated in the events file name (e.g., sub-001_ses-01_task-pixar_run-01_events.tsv)
# At the moment, there are pre-existing events and contrasts for the pixar data, but not sesame street
# No files are generated for sesame data (but could easily be generated in the future).
#
# More information on these files: 
#	https://bids-specification.readthedocs.io/en/stable/modality-specific-files/task-events.html
################################################################################

# usage documentation - shown if no text file is provided
Usage() {
    echo
    echo "Usage:"
    echo "./generate_eventfiles.sh <list of subject folders to convert>"
    echo
    echo "Example:"
    echo "./generate_eventfiles.sh list.txt"
    echo 
    echo "list.txt is a file containing the participants to generate the events.tsv files for:"
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
projDir=`cat ../../PATHS.txt`
bidsDir="/EBC/preprocessedData/TEBC-5y/BIDs_data"
derivDir="/EBC/preprocessedData/TEBC-5y/derivatives"

# ITERATE FOR ALL SUBJECTS IN THE TXT FILE
while read p
do
	ORIGINALNAME=` basename ${p} | cut -d '_' -f 1 `	# data folder name
	NAME=` basename ${p} |  cut -d "-" -f 3 `			# subj number from folder name
	
	# define subject derivatives directory
	subDir="${derivDir}/sub-${NAME}/ses-${ses}/func"
	
	# create events.tsv file for each subject who has functional data
	if [ -d ${subDir} ] # if the subject has a functional data folder
	then
	
		echo
		echo "Generating events.tsv files for sub-${NAME}"
		echo
		
		# delete events.tsv files if they already exist
		if [ -f ${subDir}/*run-01_events.tsv ]
		then 
			rm ${subDir}/*events.tsv
		fi
		
		# copy the event files saved in the data directory
		awk 'NR > 0' ${projDir}/data/event_files/pixar/mind_body.tsv >> ${subDir}/sub-${NAME}_ses-${ses}_task-pixar_run-01_events.tsv
		awk 'NR > 1' ${projDir}/data/event_files/pixar/faces_scenes.tsv >> ${subDir}/sub-${NAME}_ses-${ses}_task-pixar_run-01_events.tsv
		
		# copy for second run of data if it exists
		if [ -f ${subDir}/sub-${NAME}_ses-${ses}_task-pixar_run-02_desc*.tsv ]
		then 
			awk 'NR > 0' ${projDir}/data/event_files/pixar/mind_body.tsv >> ${subDir}/sub-${NAME}_ses-${ses}_task-pixar_run-02_events.tsv
			awk 'NR > 1' ${projDir}/data/event_files/pixar/faces_scenes.tsv >> ${subDir}/sub-${NAME}_ses-${ses}_task-pixar_run-02_events.tsv
		fi		

	fi
	
done <$1

