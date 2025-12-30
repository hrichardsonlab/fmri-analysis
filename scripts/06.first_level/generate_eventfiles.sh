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

# usage documentation
Usage() {
	echo
	echo "Usage:"
	echo "./generate_eventfiles.sh <config file> <subject-run list>"
	echo
	echo "Example:"
	echo "./generate_eventfiles.sh config-awe_emo-phys.tsv RLABPILOT_subjs.txt"
	echo 
	echo "RLABPILOT_subjs.txt is a file containing the participants to generate the scans.tsv file for:"
	echo "sub-RLABPILOT01"
	echo "sub-RLABPILOT02"
	echo "..."
	echo
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] | [ "$2" = "" ] && Usage

# check files passed in script call
if [ ! ${1##*.} == "tsv" ]
then
	echo
	echo "The configuration file was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject list as in the example below."
	echo
	echo "./generate_eventfiles.sh config-awe_emo-phys.tsv RLABPILOT_subjs.txt"
	echo	
	# end script and show full usage documentation	
	Usage
fi

if [ ! ${2##*.} == "txt" ]
then
	echo
	echo "The list of participants was not found."
	echo "The script must be submitted with (1) a configuration file name and (2) a subject list as in the example below."
	echo
	echo "./generate_eventfiles.sh config-awe_emo-phys.tsv RLABPILOT_subjs.txt"
	echo	
	# end script and show full usage documentation	
	Usage
fi

# define directories
projDir=`cat ../../PATHS.txt`

# define config file and subjects from files passed in script call
config=${projDir}/$1
subjs=$(cat $2 | awk '{print $1}')

# define data directories depending on study information
bidsDir=$(awk -F'\t' '$1=="bidsDir"{print $2}' "$config")
derivDir=$(awk -F'\t' '$1=="derivDir"{print $2}' "$config")
task=$(awk -F'\t' '$1=="task"{print $2}' "$config")
sessions=$(awk -F'\t' '$1=="sessions"{print $2}' "$config")

# strip extra formatting if present
bidsDir="${bidsDir%$'\r'}"
derivDir="${derivDir%$'\r'}"
task="${task%$'\r'}"
sessions="${sessions%$'\r'}"

# print confirmation of study directory
echo 'Generating events.tsv files for data in' ${derivDir}

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
				
				# copy same onsets and durations for tasks that have same event timings for all participants or copy subject-specific events files
				if [ ${task} == 'pixar' ]
				then
					# copy the event files saved in the project files directory
					for e in ${projDir}/files/event_files/*.tsv
					do
						awk 'NR>0' ${e} >> ${subDir}/tmp.tsv
					done
					
					# remove duplicate rows (header info) and tmp file
					awk '!NF || !seen[$0]++' ${subDir}/tmp.tsv >> ${subDir}/${run_file}
					rm ${subDir}/tmp.tsv
				
				elif [ ${task} == 'tomloc' ]
				then
					# copy the event files saved in the project files directory
					cp ${projDir}/files/event_files/${task}_run-00${r}_events.tsv ${subDir}/${run_file}
					
				elif [ ${task} == 'langloc' ]
				then
					# copy the event files saved in the project files directory
					cp ${projDir}/files/event_files/${task}_run-00${r}_events.tsv ${subDir}/${run_file}				
				
				else
					# copy the subject-specific event files saved in the project files directory
					cp ${projDir}/files/event_files/${sub}/*task-${task}_run-00${r}*.tsv ${subDir}
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
			if [ ${task} == 'pixar' ]
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
				cp ${projDir}/files/event_files/${sub}/*task-${task}*.tsv ${subDir}
			fi
		fi
	fi
	
done <$2


