#!/bin/bash

################################################################################
# SETUP PROJECT DIRECTORY WITH NECESSARY SCRIPTS AND DATA FILES
#
# This script should be run in the directory where the project folder will be generated
# This should typically be in your EBC/home/UUN folder
#
# This script copies and organizes the scripts and data files saved in the 
# shared location (e.g., EBC/processing) to your project folder and generates
# a PATHS.txt file. Larger data files (e.g., ROI files) won't be transferred
#
################################################################################

# usage documentation - shown if no project name is provided
Usage() {
	echo
	echo
	echo "Usage:"
	echo "./setup_project cohort PROJECT_NAME"
	echo
	echo "You must provide (1) the cohort for analysis and (2) a PROJECT_NAME (with no spaces) so the associated project folder can be generated"
	echo
	echo "Example:"
	echo "./setup_project TEBC-5y pixar"
	echo
	echo "For non-EBC data, the 'cohort' argument passed in the script call will be the name of the study or dataset"
	echo
	echo "This script must be run within the /EBC/ directory on the server due to space requirements."
	echo "The script will terminiate if run outside of the /EBC/ directory."
	echo
	echo "This script only needs to be run once when setting up your project folder."
	echo
	echo "Script created by Melissa Thye"
	echo
	exit
}
[ "$1" = "" ] | [ "$2" = "" ] && Usage

# define cohort
cohort=$1

# define project as text provided after script call
proj=$2

# define directories
dataDir="/EBC/processing" # location of shared files

# if the script is run outside of the EBC directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/EBC/" ]]; 
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
	cp -r ${dataDir}/scripts/fMRI/. ${proj}/scripts
	
	# subj lists
	if [ -d "${dataDir}/subj_lists/${cohort}" ]
	then
		cp -r ${dataDir}/subj_lists/${cohort}/. ${proj}/files/subj_lists
	fi
	# event files
	if [ -d "${dataDir}/event_files" ]
	then
		cp -r ${dataDir}/event_files ${proj}/files
	fi
	
	# contrast files
	if [ -d "${dataDir}/contrast_files" ]
	then
		cp -r ${dataDir}/contrast_files ${proj}/files
	fi
	
	# ROI timecourses
	if [ -d "${dataDir}/ROI_timecourses" ]
	then
		cp -r ${dataDir}/ROI_timecourses ${proj}/files
	fi
	
	# copy example config file as template with motion thresholds that were already applied to data
	cp -r ${dataDir}/config_files/config-study_template.tsv ${proj}
fi

# optional, but nice to clean up environment
rm setup_project.sh
