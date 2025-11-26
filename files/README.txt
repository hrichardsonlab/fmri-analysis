Dataset files are saved in the following directories within a shared location on the server (e.g., /RichardsonLab/processing)

atlases/ : 
Contains anatomical atlas files (e.g., Harvard Oxford atlas). These files are not currently used in the pipeline but may prove useful for region-based analyses at some point.

config_files/ :
These files are used to specify processing options for the pipeline scripts. Example config files are provided here and a template file is copied over by the project setup scripts.

contrast_files/ :
These files list all condition contrasts for a dataset. Multiple tasks can (and should!) be included in the same contrasts file.

event_files/ :
These files are tab-delimited files containing stimulus presentation and optionally response information. Where relevant, individual events files are provided per participant if stimulus presentation differed across participants and/or runs.

ROI_timecourses/ :
Averaged adult timecourses from ROIs isolated using functional localisers. Not all datasets will have associated timecourses (likely only pixar at the moment).

ROIs/ :
Any group or atlas based ROI to use at any point during the analysis.

scripts/ :
Current fMRI processing scripts organised into folders corresponding to each analysis step.

search_spaces / :
Large regions used to mask subject-level data to define functional ROIs and extract timeseries or stats.

singularity_images / :
The containers we use for analyses with the required software and packages pre-configured to create a reproducible workflow.

subj_lists/ :
Lists of subjects passed to most of the pipeline scripts. Some of the subject lists include run information which is required for the first and second level pipelines.

templates / :
MNI (typically) template files used to resample participant and ROI files to a common atlas space.

tools / :
Contains shared toolboxes or files used for analysis. At the moment the FreeSurfer license file is saved here because it needs to be referenced when calling fMRIPrep.