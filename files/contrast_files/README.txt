Several important things to note: 

- multiple tasks (experiments) can be included in the same contrasts file. In fact, you should only have one contrasts file per BIDS dataset. The column 'task' indicates which task the contrasts belong to. Task names must be consistent across functional data and the contrasts / event files, etc. This will allow matching to correct functional data files.  

- the description should be a single string (using _ or - is fine), describing what the contrast is (a single condition as compared to rest/non-modelled data? a condition preferred over another condition? a category of conditions over another category of conditions?)

- the weights applied must sum to 0 and are listed in the same order as the contrast's conditions under 'conds' 

- you can list conditions under 'conds' that are not weighted in a given contrast, and therefore the weight is 0 (e.g. if you list all conditions under 'conds' column for every contrast, but some contrasts don't use or care about a subset of that full set of conditions, then that subset can just be weighted as 0)

- you can have multiple conditions on either side of a contrast: e.g. for the Mind, Body, Faces, and Scenes conditions in the pixar data, you can define a contrast of social over nonsocial by saying: 

task	desc		conds						weights
pixar	social-nonsocial 	Mind Body Faces Scenes 	1 -1 1 -1

- you can also have imbalanced conditions, but they still must sum to 0. For example, for Mind, Body, Faces, Scenes conditions, I might want the contrast of Faces over everything else, except Animal, which was an extra condition I don't want included. That would look like: 

task 	desc		conds 					weights
pixar 	faces-else	Faces Body Animal Mind Scenes	1 -1/3 0 -1/3 -1/3

TIP: it is good to have a key of your descriptions that are elaborated/ fleshed out, so that you will always know exactly what the point of a given condition was, especially if you use simplistic abbreviations or acronyms in your descriptions. 

