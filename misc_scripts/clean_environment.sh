#!/bin/bash

################################################################################
# CLEAN UP TEMPORARY WORKFLOW DIRECTORIES GENERATED BY FREESURFER AND FMRIPREP
#
################################################################################

# usage documentation - shown if no PATH.txt file is found
Usage() {
    echo
	echo
    echo "Usage:"
    echo "./clean_environment.sh"
    echo
	echo
	echo "This script will look for a PATHS.txt file saved 2 directories above where this script is saved"
	echo
	echo
    echo "Script created by Melissa Thye"
    echo
    exit
}
[ "$1" = "" ] && Usage

if [ ! -f ../../PATHS.txt ]
then Usage
done

# define directories
projDir=`cat ../../PATHS.txt`
singularityDir="${projDir}/singularity_images"

# display subjects
echo
echo "Cleaning up temporary workflow directories in..." ${singularityDir}
echo

# remove temporary directories
rm -r ${singularityDir}/fmriprep-23_2_wf/sub_${NAME}_wf
rm -r ${singularityDir}/rootfs*
rm -r ${singularityDir}/20*
rm -r ${singularityDir}/fmriprep