#!/bin/bash

################################################################################
# SETUP PROJECT DIRECTORY WITH NECESSARY SCRIPTS AND DATA FILES
#
# This script should be run in the directory where the project folder will be generated
# This should typically be in your EBC/home/UUN folder
# The scripts and subject lists saved in the EBC/processing folder will be copied
# to the project folder and a PATHS.txt file will be generated
################################################################################

# usage documentation - shown if no project name is provided
Usage() {
    echo
	echo
    echo "Usage:"
    echo "./setup_project PROJECT_NAME"
	echo
	echo "You must provide a PROJECT_NAME (with no spaces) so the associated project folder can be generated"
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
[ "$1" = "" ] && Usage

# define directories
dataDir="/EBC/processing/subj_lists/TEBC-5y"	# location of shared data files
codeDir="/EBC/processing/scripts/TEBC-5y"		# location of shared scripts

# define project as text provided after script call
proj=$1

# delete the project directory if it already exists
if [ -d ${proj} ]
then
	rm -r ${proj}
fi

# if the script is run outside of the EBC directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/EBC/" ]]; 
	then Usage
fi

# make project directories
echo
echo "making ${proj} project directory"
echo

mkdir ${proj}
mkdir ${proj}/data
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

cp -r ${codeDir}/. ${proj}/scripts
cp -r ${dataDir}/. ${proj}/data/subj_lists