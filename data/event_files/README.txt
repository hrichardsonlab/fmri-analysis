The purpose of events files is to describe timing and other properties of events recorded during a run. Events are stimuli presented to the participant or participant responses.

The same events file can be used for the 5y and 7y EBC data given that the same functional paradigms are used for both datasets.

Several important things to note: 

- A single event file MAY include any combination of stimulus, response, and other events.

- Events MAY overlap in time. 

- Please mind that this does not imply that only so called "event related" study designs are supported (in contrast to "block" designs) - each "block of events" can be represented by an individual row in the events.tsv file (with a long duration).

- Each task events file REQUIRES a corresponding task data file. The events file name must have the name of the corresponding data file indicated in it's name (e.g., sub-001_ses-01_task-pixar_run-01_events.tsv)

- Columns indicating the onset and duration are required. Optionally, a trial_type column can be included - this is almost always needed to indicate which events the onset and durations refer to.
