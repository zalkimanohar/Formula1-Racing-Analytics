# Presenter script - group presentation (10 minutes + 5 minutes Q&A)

Speaking pace assumed: 130 words per minute. Time budget per slide below; rehearse once with a timer. Present from the PDF, or install the fonts in report/assets/fonts before opening the PowerPoint.

| # | Slide | Presenter | Budget | Words | Est. at pace |
|---|---|---|---|---|---|
| 1 | Title | All (opened by Chirag Adhikari) | 18 s | 42 | 19 s |
| 2 | Dataset and motivation | Chirag Adhikari | 36 s | 76 | 35 s |
| 3 | CRISP-DM and medallion | Nicolas Bonilla | 36 s | 72 | 33 s |
| 4 | Data engineering architecture | Nicolas Bonilla | 36 s | 78 | 36 s |
| 5 | Spark medallion and star schema | Chirag Adhikari | 32 s | 76 | 35 s |
| 6 | FAIR assessment | Chirag Adhikari | 41 s | 86 | 40 s |
| 7 | Licences and identifiers | Chirag Adhikari | 41 s | 100 | 46 s |
| 8 | Disguised nulls | Manohar Zalki | 36 s | 72 | 33 s |
| 9 | Duplicates vs shared drives | Manohar Zalki | 36 s | 75 | 35 s |
| 10 | Eras, outliers and impact | Manohar Zalki | 36 s | 75 | 35 s |
| 11 | Order of operations | Nicolas Bonilla | 36 s | 72 | 33 s |
| 12 | Validation and resolution | Nicolas Bonilla | 36 s | 65 | 30 s |
| 13 | Property graph and small world | Manohar Zalki | 36 s | 72 | 33 s |
| 14 | Communities by era | Chirag Adhikari | 32 s | 77 | 36 s |
| 15 | Interactive dashboard | Nicolas Bonilla | 27 s | 64 | 30 s |
| 16 | Dashboard gallery | Manohar Zalki | 23 s | 56 | 26 s |
| 17 | Ask the data | Manohar Zalki | 36 s | 98 | 45 s |
| 18 | Conclusion | Nicolas Bonilla | 23 s | 77 | 36 s |
| 19 | Questions | All | 3 s | 18 | 8 s |

**Total budget:** 10 min 00 s.

| Presenter | Time budget |
|---|---|
| All | 0 min 21 s |
| Chirag Adhikari | 3 min 02 s |
| Nicolas Bonilla | 3 min 14 s |
| Manohar Zalki | 3 min 23 s |

## Script per slide

### Slide 1 - Title (All (opened by Chirag Adhikari), 18 s)

Good morning, we are Chirag Adhikari, Manohar Zalki and Nicolas Bonilla. We take 75 years of Formula 1 results from raw files to a FAIR, quality-assured dataset, a knowledge graph, a dashboard and an assistant that answers questions with evidence. Lights out.

### Slide 2 - Dataset and motivation (Chirag Adhikari, 36 s)

Our dataset is the Ergast Formula 1 database, which the group downloaded from its successor, the Jolpica API. The core table has 25,907 race results: one row for every car in every championship Grand Prix since 1950, 1,149 races in total. We chose it because it is relational, so keys and joins matter; its quality problems are real, coming from decades of rule changes and file exports; and drivers, teams and circuits form a natural network.

### Slide 3 - CRISP-DM and medallion (Nicolas Bonilla, 36 s)

We followed CRISP-DM inside a medallion layout. Bronze keeps the raw archive exactly as received, with lineage to the file and line. Silver is only written when every validation gate passes. Gold holds what people use: the FAIR record, the graph, the dashboard and the assistant. Each CRISP-DM phase has its own evidence, from the issue register to the tests and the assistant benchmark, and one command rebuilds everything with byte-identical results.

### Slide 4 - Data engineering architecture (Nicolas Bonilla, 36 s)

Here is the architecture behind it. Data move through zones: an immutable raw zone that keeps the source values and their lineage, a clean zone that is only written when every validation gate passes, and served products. Two contracts hold it together: the issue register between profiling and cleaning, and one schema module shared by cleaning and metadata. Underneath are four controls: the schema as code, one orchestrated command, automated tests, and lineage down to the source line.

### Slide 5 - Spark medallion and star schema (Chirag Adhikari, 32 s)

Next to the curated pipeline, the repository also contains the Spark implementation of the medallion idea. Every landing file is ingested into bronze, transformed in silver and modelled in gold as a star schema: one fact table of session results with race, constructor and driver dimensions. It runs in incremental batches and feeds the classic dashboard and the machine-learning prototype. Note that gold also holds sprint sessions, while the curated FAIR package covers Grands Prix only.

### Slide 6 - FAIR assessment (Chirag Adhikari, 41 s)

We measured FAIRness twice. First automatically with F-UJI, using the same metric version as the public service, on four locations of the data. The Jolpica API scores 11.5 percent and our GitHub repository 42.3. The same zip on Zenodo, deposited by our group with a DOI, scores 84.6 percent, the same total as the Kaggle mirror but far more findable. Because F-UJI only sees what is online, we also scored all 41 RDA indicators with written evidence: our package lifts maturity from 54 to 93 percent.

### Slide 7 - Licences and identifiers (Chirag Adhikari, 41 s)

Licences were the biggest gap. Ergast allowed only non-commercial use and Jolpica, where we downloaded the data, licenses it CC BY-NC-SA 4.0. Yet the Kaggle mirror claims public domain, our own repository says MIT for everything, and our Zenodo record says CC BY 4.0. Share-alike means the data must stay CC BY-NC-SA, so that is what our package declares, with MIT for code only, and the Zenodo licence will be corrected without changing the DOI. On identifiers: the raw archive has a DOI, 98.7 percent of drivers are linked to Wikidata, and the DataCite record validates against the official schema.

### Slide 8 - Disguised nulls (Manohar Zalki, 36 s)

I profiled every column of all five tables and ran 29 quality rules. The first lesson: completeness is deceptive. Only 18 cells are empty, so the table looks almost perfect. But 9,913 values only pretend to be data: the position column is filled for 9,646 drivers who did not finish, and 267 cars start from a grid slot zero that does not exist. A model would learn that a retirement is eighteenth.

### Slide 9 - Duplicates vs shared drives (Manohar Zalki, 36 s)

Uniqueness needs domain knowledge. 23 rows of the 1960 United States Grand Prix were appended twice, and 11 rows of the 1960 Italian Grand Prix are copies whose season and round were blanked. The red bar is the real problem. The blue bars are not: 172 rows share season, round and driver because in the 1950s a driver could take over a team-mate's car and be classified twice. The correct key includes the car number.

### Slide 10 - Eras, outliers and impact (Manohar Zalki, 36 s)

Some issues are not errors at all, but they still break analyses. A race win was worth 8, 9, 10, 25 or even 50 points depending on the era, so raw points are not comparable over time. All 270 statistical outliers in laps are valid Indianapolis 500 results, so we flag them instead of deleting them. For data science the impact is concrete: inflated win counts, biased prediction targets and era bias in all-time rankings.

### Slide 11 - Order of operations (Nicolas Bonilla, 36 s)

The most important design decision was the order of operations. If you remove duplicates first and repair keys afterwards, 11 duplicates survive, because their season and round were blanked. So step C02 restores the season from the file name and the round by an exact lookup in the races table, and only then does step C03 remove all 34 copies. A unit test documents both orders, and no value is ever invented.

### Slide 12 - Validation and resolution (Nicolas Bonilla, 36 s)

Every one of the 29 issues is now closed: 18 are fixed, 3 are mitigated or flagged, 5 are kept and documented, and 3 were verified as non-errors. Our rule is flag, don't delete: Indianapolis 500 rows and shared drives stay, with flags. Status went from 136 free-text values to 8 groups, and 55 validation gates must all pass before anything is published as clean.

### Slide 13 - Property graph and small world (Manohar Zalki, 36 s)

We modelled the cleaned data as a property graph: drivers, races, constructors, circuits and countries, with results on the edges and a derived team-mate relationship. Indianapolis 500 rounds are excluded from the team-mate projection, a direct consequence of the quality analysis. The result is a small world: clustering is 0.41 against 0.014 for a random graph, yet two drivers are on average only 4.8 links apart. Fangio reaches Verstappen in 8 steps.

### Slide 14 - Communities by era (Chirag Adhikari, 32 s)

Louvain community detection finds 11 communities with a modularity of 0.70. The algorithm never sees a date, yet the large communities line up with eras, from the fifties around Stirling Moss to the present grid around Sergio Pérez. Betweenness highlights bridges between eras such as Jo Bonnier. One caveat links back to data quality: before the seventies the constructor field records the chassis make shared by private entrants, so early drivers look more connected than they were.

### Slide 15 - Interactive dashboard (Nicolas Bonilla, 27 s)

Everything we showed ends here, in an interactive dashboard that opens with one command. It reads only validated outputs, and run_all rebuilds it as its last step. It also paid back: the reliability view showed mechanical failures vanishing after 2022, which turned out to be the source no longer recording why cars retired. That became issue B29. If time allows, we open it live.

### Slide 16 - Dashboard gallery (Manohar Zalki, 23 s)

Four more views. The timing tower ranks drivers by wins or by our era-adjusted score. The grid view shows where cars finish from each starting slot, using classified positions only, which is exactly the fix for issue B11. The reliability view marks the 2023 break that became issue B29, and the globe places all seventy-seven circuits.

### Slide 17 - Ask the data (Manohar Zalki, 36 s)

The last view lets anyone question the data, in English or Spanish. It grows out of the LLM and RAG prototype from our group, rebuilt so that the language model never supplies a number. The question is parsed, the evidence is computed with pandas from the cleaned tables, with the file and raw line of every figure, plus the team-mate graph and a podium model. Llama 3 runs locally and only phrases that evidence, and every figure is checked afterwards. On 25 benchmark questions with independently computed answers, 25 were right, and it declined the question about 2030.

### Slide 18 - Conclusion (Nicolas Bonilla, 23 s)

Five lessons. Quality is contextual: outliers, duplicates and short grids were often valid history. The order of operations matters, as the 11 hidden duplicates show. The largest FAIR gaps sit around the values: identifiers, licences and provenance. Automating the evidence turns cleaning into something an examiner can verify. And a language model needs a data layer: code computes, the model only phrases. Next steps are a DOI for the curated package and reporting the source defects upstream.

### Slide 19 - Questions (All, 3 s)

Thank you. We are happy to take your questions; each of us will answer on our own component.

## Hand-over cues

- Slide 1 -> 2: All (opened by Chirag Adhikari) hands over to Chirag Adhikari for 'Dataset and motivation'.
- Slide 2 -> 3: Chirag Adhikari hands over to Nicolas Bonilla for 'CRISP-DM and medallion'.
- Slide 4 -> 5: Nicolas Bonilla hands over to Chirag Adhikari for 'Spark medallion and star schema'.
- Slide 7 -> 8: Chirag Adhikari hands over to Manohar Zalki for 'Disguised nulls'.
- Slide 10 -> 11: Manohar Zalki hands over to Nicolas Bonilla for 'Order of operations'.
- Slide 12 -> 13: Nicolas Bonilla hands over to Manohar Zalki for 'Property graph and small world'.
- Slide 13 -> 14: Manohar Zalki hands over to Chirag Adhikari for 'Communities by era'.
- Slide 14 -> 15: Chirag Adhikari hands over to Nicolas Bonilla for 'Interactive dashboard'.
- Slide 15 -> 16: Nicolas Bonilla hands over to Manohar Zalki for 'Dashboard gallery'.
- Slide 17 -> 18: Manohar Zalki hands over to Nicolas Bonilla for 'Conclusion'.
