# Individual Reflection Log - Component B: Data Quality and Profiling

> DRAFT - personalise every [bracketed] part and rewrite in your own words before submitting.
> Target length about 500 words. Submitted individually via the course portal.

**Decisions and why.** I profiled all five tables, not only the results table, because several problems
(duplicate races, circuits without IDs, one driver under two identifiers) only exist in the reference data and
would have broken joins later. Instead of a list of observations, I built a rule-based issue register: every
finding has a dimension, a severity based on its downstream impact, evidence down to the file and line, a
root-cause hypothesis and the cleaning step that should resolve it. I also recorded the rules that passed,
because knowing what is trustworthy is as useful as knowing what is broken. The most important design decision
was to separate errors from non-errors: of 29 findings, five are documented as valid history.

**Most challenging aspect.** Deciding when an anomaly is really an error. The 172 rows that looked like
duplicates (same season, round and driver) turned out to be shared drives from the 1950s, and the seven
modern races with fewer entries than usual all matched real events, such as teams missing at the end of 2014
or a driver injured before the 2025 Spanish Grand Prix. The opposite was also true: eleven rows of the 1960
Italian Grand Prix were real duplicates, but they only became visible after I simulated restoring their blanked
keys. Measuring "disguised" missing values was another challenge: the table looks 99.9% complete, yet 9,913
values only pretend to be data. [Add your own experience.]

**Connection to the group.** The issue register was the contract with Component C: each issue names the step
that resolves it, and the pipeline measures every issue again after cleaning, which produced the before/after
table in the report. Component A used my findings as evidence for its interoperability gaps. The graph analysis
then taught me something profiling had missed: in the 1950s and 1960s "constructor" means the chassis make,
not a team, which inflates network measures - a semantic quality issue that no completeness or uniqueness rule
could detect. Our dashboard taught me a second lesson: its reliability chart showed failures vanishing after
2022, because the source stopped recording why cars retired. That became issue B29. [Describe how you worked
with your team-mates.]

**What I would do differently.** I would start by reading the source documentation for the meaning of each
field (for example "position" and "constructor") before writing rules, because semantic issues caused the
largest downstream impact. I would verify the seven short races against the official FIA classification, add
checks for temporal drift (distributions changing by era) and cross-check my rules with an automated profiling
library. [Add one personal lesson.]

[Declare honestly how you used the AI assistant in this component and which results you checked yourself.]
