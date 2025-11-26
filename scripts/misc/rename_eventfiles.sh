#!/bin/bash

# define directory where study events files live
eventsDir="/RichardsonLab/processing/event_files/KMVPA"

# for each folder and file in the main folder
find "$eventsDir" -type f -name "*.tsv" | while read -r file
do

  # get the directory of the current file
  dir=$(dirname "$file")
  
  # get the filename without the directory path
  filename=$(basename "$file")
  
  # remove the second '-' from the filename
  new_filename=$(echo "$filename" | sed 's/\(-\)/\1/2;s/-//2')
  
  # rename the file with the new name (removing the '-')
  mv "$file" "$dir/$new_filename"
  
  echo "Renamed $filename to $new_filename"

done