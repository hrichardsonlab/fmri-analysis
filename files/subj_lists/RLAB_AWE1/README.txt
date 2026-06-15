The bids conversion script will convert all relevant data, including repeated sequences. This file notes where data were intentionally not converted according to the information provided in the scan log. Where scans were repeated, the higher quality scan (based on visual inspection or the scan log notes) have already been selected and converted. The lower quality scan has been removed from the BIDS directory to avoid accidental use in analysis. 

The SeriesNumber is provided, where relevant, in case users want to confirm that the data are from the correct sequence. The json files associated with each nifti file will have this SeriesNumber number information for cross-referencing.

sub-RLABAWE102
- two T1w images collected: use the second run (SeriesNumber 6) because the head coil didn't seem to be fully connected for the first run, so there's anterior signal dropout.
- awe run 1: incomplete run (stopped around trial 16)

sub-RLABAWE108
- awe run 4: looks like the experiment triggered early (by about ~14s), so the onsets should be shifted to account for this.

sub-RLABAWE110
- four fieldmaps collected: use all of them. The first 2 fieldmaps were acquired during the first session. The second one was acquired due to an apparent artifact in the functional data. Two additional fieldmaps were acquired because the participant took multiple breaks.

sub-RLABAWE118
- two fieldmaps collected during first session. Fine to use either, but used the second one.

sub-RLABAWE119
- two T1w images collected: use the second run (SeriesNumber 6) because high motion in the first run.

sub-RLABAWE121
- three fieldmaps collected throughout session (1 in first session - fieldmap1; 2 in the second session - both called fieldmap2). The BIDS conversion returns 2 runs of fieldmap2 - these were modified to (1) rename them (run-002, run-003) according to their SeriesNumber (the third fieldmap was acquired after the first, so the SeriesNumber is higher - this will match the raw data folder name) and (2) to ensure the third fieldmap's IntendedFor field points to the 3 echoes of the snack attack data.

sub-RLABAWE124
- awe run 1: the first run was incomplete but complete enough to be converted, but the second run was complete and should be used for analyses. The BIDs conversion returns 2 runs of run-001, but labels them as 'run-01' and 'run-02'. The 'run-01' files were deleted and the 'run-02' files were renamed according to the usual naming convention (i.e., run-001). The run 2 fieldmap json files were edited to ensure the IntendedFor field had the correct run name (run-001 instead of run-01 and run-02).

sub-RLABAWE126
- three fieldmaps collected throughout session (1 in first session - fieldmap1; 2 in second session - fieldmap2 + fieldmap3). fieldmap1 (for session 1 data) and fieldmap3 (for session 2 data) should be used in analyses. The dcm2nifti config file for this participant should already handle this. There are 2 raw data folders for the snack attack movie data. The first data transfer attempt sent an incomplete dataset (missing ~10 volumes), so the data were sent again with '_RR' (repreprocessed) appended to the file name. These are the data that should be used for analyses. The bids conversion will return both runs of the snack attack data. Delete the first run and rename the second run to remove run information. The run 2 fieldmap json files were edited to have the correct file name in the IntendedFor field (snack attack without any run information).