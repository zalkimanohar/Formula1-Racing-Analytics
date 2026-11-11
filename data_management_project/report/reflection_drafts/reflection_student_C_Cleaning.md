# Individual Reflection Log - Component C: Data Cleaning and Pipeline

> DRAFT - personalise every [bracketed] part and rewrite in your own words before submitting.
> Target length about 500 words. Submitted individually via the course portal.

**Decisions and why.** I built the pipeline in Python (pandas) rather than Tableau Prep because code can be
version-controlled, reviewed and tested, and because the whole chain had to run from the original archive with
one command. Each of the twelve steps answers specific issues from Component B's register. The decision I can
defend most strongly is the order of operations: missing seasons and rounds are restored by deterministic lookup
before de-duplication, otherwise eleven duplicated rows of the 1960 Italian Grand Prix survive. I also chose
never to invent values: the grid sentinel 0 became missing plus a flag, and withdrawn entries keep a missing car
number. Valid extremes (Indianapolis 500, shared drives) are flagged instead of deleted, and every categorical
mapping is exhaustive, so an unknown value stops the pipeline rather than slipping through.

**Most challenging aspect.** Making the audit log trustworthy. The first version reported plausible-looking
numbers that were wrong: it counted two missing values as a change and compared misaligned rows after
duplicates were removed. I only noticed because the "cells changed" of the key repair step did not match
Component B's counts (it should be 5 seasons + 7 rounds = 12). Fixing it taught me that an audit log needs to be
tested like any other code. Restoring proper names from lowercase text was harder than expected too: a casing
rule handles "Circuit of the Americas" and "Pedro de la Rosa", but six names such as "AVUS" needed curated
exceptions. [Add your own experience.]

**Connection to the group.** Component B's register defined my work and my resolution table closed the loop by
re-measuring every issue after cleaning. I shared the schema module with Component A, so the metadata and data
dictionary always match the delivered columns, and Component A's Wikidata crosswalk was joined into my reference
tables. The graph model depends on my clean keys and on the is_indy500 flag, which the group used to exclude
chassis-sharing Indy entries from the team-mate network. [Describe how you coordinated with your team-mates.]

**What I would do differently.** I would write the tests for each step first, use a validation library such as
pandera or Great Expectations for the gates, and move thresholds and mappings into configuration files. I would
also define "team" explicitly instead of reusing the constructor field, and report the source defects
(duplicated blocks, identifier case) upstream to Jolpica. [Add one personal lesson.]

[Declare honestly how you used the AI assistant in this component and which results you checked yourself.]
