#!/bin/bash

################################################################################
# CREATE SYMBOLIC LINKS FROM /EBC/code/singularity_images : 
#
# We want singularity images accessible but we don't want a bunch of copies
# so this creates a symbolic link for all the content of the lab standard 
# containers and puts those links in your project folder
################################################################################

# usage documentation
Usage() {
    echo
	echo
    echo "Usage:"
    echo "./symlink_singularities"
	echo
	echo "You must have a PATHS.txt file in your project folder with the path to your project folder within the text file."
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

# if the script is run outside of the EBC directory (e.g., in home directory where space is limited), terminate the script and show usage documentation
if [[ ! "$PWD" =~ "/EBC/" ]]; 
	then Usage
fi

# if the PATHS.txt document does not exist where expected, terminate the script and show usage documentation
if [[ ! -f  "../../PATHS.txt" ]]; 
	then Usage
fi

# location of shared singularity images
masterDir="/EBC/processing/singularity_images"

# study folder to create symlink
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"

# make the study directory if it doesn't exist
if [[ ! -e ${singularityDir} ]] 
then
	mkdir ${singularityDir}
else 
	echo "singularity directory already exists for project folder"
fi

# create symlinks if the directory is empty
if [ -z "$(ls -A ${singularityDir})" ]
then
	ln -s ${masterDir}/*.* ${singularityDir}/
	echo "symbolically linking singularity containers"
else 
	echo "singularity directory is not empty, aborting"
fi
