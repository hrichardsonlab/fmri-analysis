#!/bin/bash

################################################################################
# GENERATE THE EVENTS FILES USED TO IDENTIFY EVENTS OF INTEREST IN THE FUNCTIONAL DATA
# 
# Each functional run should have a corresponding events file 
# The name of the functional run is indicated in the events file name (e.g., sub-001_task-KMVPAst_run-01_events.tsv)
# In order for event files to be generated, there needs to be pre-existing events.tsv files in the project data directory
#
# More information on these files: 
#	https://bids-specification.readthedocs.io/en/stable/modality-specific-files/task-events.html
#
################################################################################

# usage documentation - shown if no text file is provided
Usage() {
	echo
	echo "Usage:"
	echo "./generate_eventfiles.sh <subject-run list> <task>"
	echo
	echo "Example:"
	echo "./generate_eventfiles.sh KMVPA_subjs.txt KMVPA"
	echo 
	echo "KMVPA_subjs.txt is a subject-run file containing the participants and run info to generate the events.tsv files for:"
	echo "001 1,2"
	echo "002 2"
	echo "..."
	echo
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] | [ "$2" = "" ] && Usage

# indicate whether session folders are used (always 'yes' for EBC data)
sessions='no'

# define task from script call
task=$2

# extract study name from list of subjects filename
study=` basename $1 | cut -d '_' -f 1 `

# define data directories depending on study information
bidsDir="/RichardsonLab/preprocessedData/${study}"
derivDir="${bidsDir}/derivatives"

# print confirmation of sample and directory
echo 'Generating events.tsv files for' ${study} 'data in' ${derivDir}

# define project directory
projDir=`cat ../../PATHS.txt`

# iterate over subjects
while read p
do
	# define subjects and runs from text file passed in script call
	runs=$(echo ${p} |awk '{print $2}')
	sub=$(echo ${p} |awk '{print $1}')
	
	# define subject derivatives directory depending on whether data are organized in session folders
	if [[ ${sessions} == 'yes' ]]
	then
		subDir="${derivDir}/${sub}/ses-01/func"
		tsv_prefix="${sub}_ses-01_task-${task}"
	else
		subDir="${derivDir}/${sub}/func"
		tsv_prefix="${sub}_task-${task}"
	fi
	
	# create events.tsv file for each subject who has functional data
	if [ -d ${subDir} ] # if the subject has a functional data folder
	then
		echo "Generating ${task} events.tsv files for ${sub}"
	
		# if runs are specified (i.e., task includes several runs specified in file name)
		if [[ ${runs} != 'NA' ]]
		then
			# for each run specified in text file
			for r in $(echo ${runs} | tr "," "\n") # runs separated by commas in text file
			do
				# define event file for run
				run_file="${tsv_prefix}_run-00${r}_events.tsv"
				
				# delete events file if is already exists
				if [ -f ${subDir}/${run_file} ]
				then 
					rm ${subDir}/${run_file}
				fi	
				
				# copy same onsets and durations for pixar or copy subject-specific events files
				if [ ${study} == 'open-pixar' ]
				then
					# copy the event files saved in the project files directory
					for e in ${projDir}/files/event_files/*.tsv
					do
						awk 'NR>0' ${e} >> ${subDir}/tmp.tsv
					done
					
					# remove duplicate rows (header info) and tmp file
					awk '!NF || !seen[$0]++' ${subDir}/tmp.tsv >> ${subDir}/${run_file}
					rm ${subDir}/tmp.tsv
				
				else
					# copy the subject-specific event files saved in the project files directory
					cp ${projDir}/files/event_files/${sub}/*run-00${r}*.tsv ${subDir}
				fi

			done
		# if no run information is specified (i.e., only 1 run or not indicated in filenames)
		else
			# define event file for run
			run_file="${tsv_prefix}_events.tsv"
		
			# delete events file if is already exists
			if [ -f ${subDir}/${run_file} ]
			then 
				rm ${subDir}/${run_file}
			fi	

			# copy same onsets and durations for pixar or copy subject-specific events files
			if [ ${study} == 'open-pixar' ]
			then
				# copy the event files saved in the project files directory
				for e in ${projDir}/files/event_files/*.tsv
				do
					awk 'NR>0' ${e} >> ${subDir}/tmp.tsv
				done
				
				# remove duplicate rows (header info) and tmp file
				awk '!NF || !seen[$0]++' ${subDir}/tmp.tsv >> ${subDir}/${run_file}
				rm ${subDir}/tmp.tsv
			
			else
				# copy the subject-specific event files saved in the project files directory
				cp ${projDir}/files/event_files/${sub}/*run-00${r}*.tsv ${subDir}
			fi
		fi
	fi
	
done <$1


