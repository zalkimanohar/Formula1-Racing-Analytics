"""Ask-the-data assistant: the served zone answers questions with evidence from the validated dataset.

Idea and first prototype by Manohar Zalki (Graphic-LlmRag: FastAPI + Ollama Llama 3 + hybrid vector/graph
retrieval + ML engine). This package rebuilds it on the cleaned, validated data with traceable evidence:

    reference.py     official World Champions (Wikidata, reconciled with our points)
    facts.py         entity resolution and exact facts computed with pandas, each with provenance
    graph_tools.py   team-mate network queries (shortest chains, team-mates, communities)
    podium_model.py  podium-probability model with time-based validation and a model card
    knowledge.py     document corpus + embedding index for semantic retrieval
    retrieval.py     hybrid lexical + semantic retrieval (reciprocal rank fusion)
    llm.py           local Llama 3 through the Ollama HTTP API
    engine.py        question -> evidence -> grounded answer -> figure check
    api.py           FastAPI service used by the dashboard
    evaluate.py      benchmark questions with answers computed from the data
"""
