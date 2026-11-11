# Individual Reflection Log - Component A: FAIR Assessment and Metadata Design

> DRAFT - personalise every [bracketed] part and rewrite in your own words before submitting.
> Target length about 500 words. Submitted individually via the course portal.

**Decisions and why.** My first decision was to assess FAIRness with two complementary methods instead of
one. F-UJI gave an automated, reproducible score, but it only sees machine-readable signals that are already
online, so I also scored all 41 indicators of the RDA FAIR Data Maturity Model with written evidence. I
evaluated four locations rather than "the dataset" (F-UJI metrics v0.8): the Jolpica API we downloaded from
(11.5%), our GitHub repository (42.3%), the Kaggle mirror (84.6%) and our group's Zenodo record of the same raw
archive (84.6%). The identical zip scores 42.3% on GitHub and 84.6% with a DOI on Zenodo: the same data can be
very differently FAIR depending on where they are published. For the metadata I combined DataCite 4.5 (needed for a DOI deposit), schema.org
JSON-LD (for discoverability) and a Frictionless Data Package (to declare keys), and I added a PROV-O graph so
that provenance is machine-readable. I deliberately kept the DOI as a clearly marked placeholder: a fake DOI
would have raised the score but would have been dishonest.

**Most challenging aspect.** The licence. Jolpica licenses the data CC BY-NC-SA 4.0, the original Ergast terms
(now only available through the Wayback Machine) allowed non-commercial use, the Kaggle mirror claims CC0, and
our own repository says MIT for everything. Resolving this required reading primary sources rather than
summaries and accepting that ShareAlike constrains our own release. Scoring the RDA indicators honestly was also
harder than expected - it was tempting to give credit for things that were only planned, so "Findable" stays at
level 0 until a DOI exists. [Add your own experience: what surprised you, where you hesitated.]

**Connection to the group.** My work depended on both other components. Component B's issue register gave
me the evidence for the interoperability gaps (country abbreviations, 136 free-text status values), and
Component C's cleaned files provided the checksums, row counts and ISO codes that the metadata describes. We
shared one schema module, so the data dictionary in my metadata is generated from the same definitions that
Component C validates against. In the other direction, my Wikidata QID crosswalk was joined into the cleaned
reference tables and became node properties in the graph. [Describe how you coordinated with your team-mates.]

**What I would do differently.** I would check the licence during dataset selection in Week 1, because a
non-commercial licence changes what the dataset can be used for. I would also deposit a test version in the
Zenodo sandbox early, so that the PID-related indicators could be tested for real and the curated package
could be re-assessed with F-UJI after publication. Finally, I would publish the status vocabulary as SKOS
instead of only proposing it. [Add one personal lesson about your own way of working.]

[Declare honestly how you used the AI assistant in this component and which results you checked yourself.]
