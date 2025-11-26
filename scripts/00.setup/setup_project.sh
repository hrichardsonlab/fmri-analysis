#!/bin/bash

################################################################################
# SETUP PROJECT DIRECTORY WITH NECESSARY SCRIPTS AND DATA FILES
#
# This script should be run in the directory where the project folder will be generated
# This should typically be in your RichardsonLab/home/<name> folder
#
# This script copies and organizes the scripts and data files saved in the 
# shared location (e.g., RichardsonLab/processing) to your project folder and generates
# a PATHS.txt file. Larger data files (e.g., ROI files) won't be transferred
#
################################################################################

# usage documentation - shown if no project name is provided
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./setup_project study PROJECT_NAME"
	echo
	echo "You must provide (1) the study for analysis and (2) a PROJECT_NAME (with no spaces) so the associated project folder can be generated"
	echo
	echo "Example:"
	echo "./setup_project KMVPA kmvpa_analysis"
	echo
	echo
	echo "This script must be run within the /RichardsonLab/ directory on the server due to space requirements."
	echo "The script will terminiate if run outside of the /RichardsonLab/ directory."
	echo
	echo "This script only needs to be run once when setting up your project folder."
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] | [ "$2" = "" ] && Usage

# define study
study=$1

# define project as text provided after script call
proj=$2

# define directories
dataDir="/RichardsonLab/processing" # location of shared files

# if the script is run outside of the RichardsonLab directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/RichardsonLab/" ]]; 
then Usage
fi

# warn if the project directory already exists
if [ -d ${proj} ]
then
	echo
	echo "${proj} project directory already exists!"
	echo
	# rm -r ${proj} # could remove project directory
else
	# make project directories
	echo
	echo "making ${proj} project directory"
	echo

	mkdir ${proj}
	mkdir ${proj}/files
	mkdir ${proj}/scripts

	# create PATHS.txt file
	echo
	echo "saving project path to PATHS.txt file"
	echo

	echo $PWD/${proj} >> ${proj}/PATHS.txt

	# copy shared files to project directory
	echo
	echo "copying scripts and data files to project directory"
	echo
	
	# some studies won't have all these files so (where relevant) check that directory exists first befoe trying to copy to project folder
	cp -r ${dataDir}/scripts/. ${proj}/scripts
	
	# subj lists
	if [ -d "${dataDir}/subj_lists/${study}" ]
	then
		cp -r ${dataDir}/subj_lists/${study}/. ${proj}/files/subj_lists
	fi
	# event files
	if [ -d "${dataDir}/event_files/${study}" ]
	then
		cp -r ${dataDir}/event_files/${study}/. ${proj}/files/event_files
	fi
	
	# contrast files
	if [ -d "${dataDir}/contrast_files/${study}" ]
	then
		cp -r ${dataDir}/contrast_files/${study}/. ${proj}/files/contrast_files
	fi
	
	# ROI timecourses
	if [ -d "${dataDir}/ROI_timecourses/${study}" ]
	then
		cp -r ${dataDir}/ROI_timecourses/${study}/. ${proj}/files/ROI_timecourses
	fi

	# copy example config file as template with motion thresholds that were already applied to data
	cp -r ${dataDir}/config_files/config-study_template.tsv ${proj}
fi

# optional, but nice to clean up environment
rm setup_project.sh
