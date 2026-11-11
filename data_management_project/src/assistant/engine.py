"""Question -> evidence -> grounded answer -> figure check.

1. Understand: find drivers, teams, circuits, Grands Prix and seasons in the question (facts.resolve) and
   what is being asked (wins, titles, team-mates, prediction, data quality, ...), in English or Spanish.
2. Gather evidence: exact facts computed with pandas, team-mate graph queries, the podium model, and the
   best-matching knowledge documents (hybrid retrieval). Each block keeps its provenance.
3. Answer: the local language model writes the answer using only the evidence and cites the blocks [S1].
4. Check: every number in the answer is looked up in the evidence; numbers that cannot be traced are flagged.
Without a language model the evidence is still returned, with a short summary built from it.
"""
from __future__ import annotations

import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache

from src import config
from src.assistant import llm
from src.assistant.facts import Entity, Evidence, fold, store
from src.assistant.graph_tools import graph
from src.assistant.podium_model import podium_model
from src.assistant.retrieval import Retriever

MAX_BLOCKS = 5
FIRST, LAST = config.FIRST_SEASON, config.LAST_COMPLETE_SEASON
INTENTS = {
    "wins": r"\b(wins?|won|winner|victor\w*|gan\w*|triunf\w*)\b",
    "podiums": r"\b(podiums?|podios?)\b",
    "poles": r"\b(poles?|pole position)\b",
    "points": r"\b(points?|puntos?|score\w*)\b",
    "starts": r"\b(starts|races entered|grands prix entered|carreras disputadas|participaciones)\b",
    "titles": r"\b(champions?|championships?|titles?|campeon\w*|titulos?|mundiales?)\b",
    "teammates": r"\b(team ?mates?|teammates?|companer\w*|connected|conectad\w*|path|chain|cadena|separation|"
                 r"degrees?|grados?)\b",
    "predict": r"\b(chances?|probab\w*|likely|predict\w*|odds|forecast\w*|expect\w*|posibilidad\w*|pronostic\w*|"
               r"model)\b",
    "quality": r"\b(quality|issues?|problems?|clean\w*|missing|duplicat\w*|errors?|valid\w*|gates?|calidad|"
               r"problemas?|limpi\w*|duplicad\w*|faltant\w*|errores?)\b",
    "fair": r"\b(fair|metadata|doi|licen\w*|datacite|orcid|wikidata|provenance|prov|fuji|rda|metadatos?|"
            r"identifiers?|identificador\w*)\b",
    "pipeline": r"\b(pipeline|architecture|lineage|raw|bronze|silver|gold|steps?|reproduc\w*|sha|checksum|linaje|"
                r"flujo|arquitectura|source|fuente|dataset|data set|datos)\b",
    "network": r"\b(network|graph|communit\w*|central\w*|betweenness|la red|red de \w+|grafo|comunidad\w*)\b",
    "most": r"\b(most|best|top|record|highest|greatest|leaders?|mas|mejor\w*|lider\w*|maxim\w*|ranking)\b",
    "team_scope": r"\b(teams?|constructors?|equipos?|escuderias?|marcas?)\b",
    "result": r"\b(who won|winner|result\w*|ganador\w*|quien gano|resultado\w*)\b",
}
GRID_RE = re.compile(r"\b(?:p|grid|from|desde|posicion|position|slot|la|el)\s*(\d{1,2})(?:st|nd|rd|th|a|o)?\b|"
                     r"\b(\d{1,2})(?:st|nd|rd|th)\s+(?:on the grid|place|position)\b")
ISSUE_RE = re.compile(r"\bB(\d{2})\b", re.I)
NUM_RE = re.compile(r"(?<![A-Za-z\[])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(%)?")

SYSTEM = """You are the data assistant of a university Data Management project on Formula 1 results (1950-2025).
Rules:
- Use ONLY the evidence blocks. Every number, name and date in your answer must appear in them.
- After each fact, cite its block in square brackets, for example [S1].
- If the evidence does not answer the question, say clearly what is missing. Never use outside knowledge.
- Points are Grand Prix points as awarded at the time (sprint points are not included); say so if relevant.
- Probabilities come from a statistical model of past races; present them as estimates, not certainties.
- Be concise: 2 to 5 sentences, or a short list. Answer in the same language as the question."""


@dataclass
class Plan:
    question: str
    entities: list[Entity]
    intents: list[str]
    issue: str | None = None
    grid: int | None = None
    notes: list[str] = field(default_factory=list)
    outside: list[int] = field(default_factory=list)   # years mentioned that the data does not cover

    def of(self, etype: str) -> list[Entity]:
        return [e for e in self.entities if e.type == etype]


class Engine:
    def __init__(self) -> None:
        t0 = time.perf_counter()
        self.store = store()
        self.graph = graph()
        self.model = podium_model()
        self.retriever = Retriever()
        self.load_seconds = round(time.perf_counter() - t0, 1)

    # ---------------------------------------------------------------- 1. understand
    def plan(self, question: str) -> Plan:
        folded = fold(question)
        no_mates = re.sub(r"\b(team ?mates?|teammates?)\b", " ", folded)   # "team-mates" is not about teams
        intents = [name for name, rx in INTENTS.items()
                   if re.search(rx, no_mates if name == "team_scope" else folded)]
        p = Plan(question, self.store.resolve(question), intents)
        m = ISSUE_RE.search(question)
        if m and 1 <= int(m.group(1)) <= 40:
            p.issue = f"B{m.group(1)}"
        g = GRID_RE.search(folded)
        if "predict" in intents:
            if g:
                p.grid = int(g.group(1) or g.group(2))
                if not 1 <= p.grid <= 26:
                    p.grid = None
            elif re.search(r"\b(pole|front of the grid|primera posicion|desde la pole)\b", folded):
                p.grid = 1
        for e in p.entities:
            if e.alternatives:
                p.notes.append(f"'{e.name}' assumed; also matches {', '.join(e.alternatives[:3])}")
        p.outside = sorted({int(y) for y in re.findall(r"\b(1[89]\d\d|20\d\d|21\d\d)\b", question)
                            if not FIRST <= int(y) <= LAST})
        return p

    # ---------------------------------------------------------------- 2. gather evidence
    def gather(self, p: Plan) -> list[Evidence]:
        s, ev = self.store, []
        drivers, teams = p.of("driver"), p.of("team")
        circuits, races, years = p.of("circuit"), p.of("race"), [int(e.id) for e in p.of("year")]
        year = years[0] if years else None
        has = set(p.intents)

        if p.outside:
            ev.append(Evidence("fact", "Coverage of the validated data", [
                f"The validated data covers the World Championship seasons {FIRST}-{LAST} only.",
                f"{', '.join(map(str, p.outside))} {'is' if len(p.outside) == 1 else 'are'} outside this range: "
                f"there are no results, champions or statistics for {'it' if len(p.outside) == 1 else 'them'} in the data."],
                {"dataset": "data/cleaned/f1_race_results_clean.csv", "sha256": s.sha["results"][:12],
                 "filter": f"season in {p.outside}", "rows": 0, "lineage": []}))
            if not drivers and not teams and not circuits and not races and not years:
                for i, e in enumerate(ev, start=1):
                    e.id = f"S{i}"
                return ev

        if p.issue:
            ev.append(s.quality_overview(p.issue))
        elif "quality" in has and not drivers and not teams:
            ev.append(s.quality_overview())
        if ("fair" in has or "pipeline" in has) and not drivers and not teams and not circuits and not races:
            ev.append(s.dataset_overview())

        if "predict" in has and drivers:
            d = drivers[0]
            last_team = s.team_name(self.model.latest.loc[d.id, "family"]) if d.id in self.model.latest.index else ""
            if d.id in self.model.latest.index:
                ev.append(self.model.explain(d.id, d.name, p.grid, last_team))

        if len(drivers) >= 2:
            ev.append(s.head_to_head(drivers[0].id, drivers[1].id))
            if "teammates" in has or "network" in has:
                ev.append(self.graph.path(drivers[0].id, drivers[1].id))
        elif len(drivers) == 1:
            d = drivers[0]
            if teams:
                ev.append(s.driver_with_team(d.id, teams[0].id))
            if year:
                ev.append(s.driver_season(d.id, year))
            if (not year and not teams) or "titles" in has or "most" in has or "predict" in has:
                ev.append(s.driver_career(d.id))
            if "teammates" in has or "network" in has:
                ev.append(self.graph.teammates(d.id))
            if circuits and "most" not in has:
                ev.append(s.circuit_profile(circuits[0].id))

        if not drivers:
            if "most" in has and ("teammates" in has or "network" in has):
                ev.append(self.graph.most_connected())
            elif "most" in has:
                metric = next((m for m in ("podiums", "poles", "points", "starts", "titles", "wins") if m in has), None)
                by = "team" if "team_scope" in has and not teams else "driver"
                if metric == "titles":
                    ev.append(s.champions_list())
                else:
                    ev.append(s.leaderboard(metric or "wins", by=by, year=year, fam=teams[0].id if teams else None,
                                            circuit=circuits[0].id if circuits else None))
                    if metric is None and by == "driver" and not year and not teams and not circuits:
                        ev.append(s.champions_list())       # "best driver": wins alone is not the whole story
            if year and (races or circuits):
                ev.append(s.race_result(year, circuit=circuits[0].id if circuits else None,
                                        race_name=races[0].id if races else None))
            elif races and "most" not in has:
                ev.append(s.event_history(races[0].id))
            elif circuits and "most" not in has:
                ev.append(s.circuit_profile(circuits[0].id))
            if teams and "most" not in has:
                ev.append(s.team_season(teams[0].id, year) if year else s.team_profile(teams[0].id))
            if year and not teams and not races and not circuits:
                ev.append(s.season_summary(year))
            if "titles" in has and not year and not teams and "most" not in has:
                ev.append(s.champions_list())
            if "network" in has and not ev:
                ev.append(self.graph.overview())
            if "teammates" in has and not ev:
                ev.append(self.graph.overview())

        # knowledge documents fill the remaining slots (never duplicating a fact block)
        covered = {f"driver:{d.id}" for d in drivers} | {f"team:{t.id}" for t in teams} | \
                  {f"circuit:{c.id}" for c in circuits} | {f"season:{y}" for y in years}
        if p.issue:
            covered.add(f"quality:{p.issue}")
        # Documents are added when the question is about the project itself, or when no fact block answered it.
        # Fact questions get no filler: shorter prompts, faster answers, less room for confusion.
        about_project = bool(has & {"quality", "fair", "pipeline"}) and not drivers and not teams and not circuits
        room = MAX_BLOCKS - len(ev) if (about_project or not ev) else 0
        if ("predict" in has and drivers) or p.issue:
            room = 0
        if room > 0:
            kinds = {"quality", "validation", "cleaning", "dictionary", "project", "model"} if about_project else None
            k = min(room, 3)
            for doc, how in self.retriever.search(p.question, k=k, kinds=kinds, exclude=covered):
                ev.append(Evidence("document", doc["title"], [doc["text"][:700]],
                                   {"dataset": doc["source"], "sha256": doc["sha"], "filter": doc["id"],
                                    "rows": 1, "lineage": [], "retrieval": how}))
        ev = ev[:MAX_BLOCKS]
        for i, e in enumerate(ev, start=1):
            e.id = f"S{i}"
        return ev

    # ---------------------------------------------------------------- 3-4. answer and check
    @staticmethod
    def language(question: str) -> str:
        q = question.lower()
        spanish = re.search(r"[¿¡ñáéíóú]|\b(cu[aá]nt[oa]s?|qui[eé]n(es)?|qu[eé]|c[oó]mo|cu[aá]l(es)?|d[oó]nde|tiene|"
                            r"gan[oó]|carreras?|equipo|piloto|temporada|campe[oó]n|podios?|victorias?|con|del|los|las)\b", q)
        return "Spanish" if spanish else "English"

    def prompt(self, question: str, evidence: list[Evidence]) -> str:
        blocks = "\n\n".join(e.to_prompt() for e in evidence)
        lang = self.language(question)
        return (f"Evidence:\n{blocks}\n\nQuestion: {question}\n\n"
                f"Write a clear, natural answer in {lang}, in full sentences, citing [S#] after each fact. "
                f"Use only the evidence above.")

    @staticmethod
    def numbers(text: str) -> list[str]:
        text = re.sub(r"\[S\d+\]", " ", text)
        out = []
        for whole, dec, pc in NUM_RE.findall(text):
            n = whole.replace(",", "") + (f".{dec}" if dec else "")
            out.append(n.rstrip("0").rstrip(".") if "." in n else n)
        return out

    def check(self, answer: str, evidence: list[Evidence], question: str) -> dict:
        known = set(self.numbers(question))
        for e in evidence:
            known |= set(self.numbers(e.title + " " + " ".join(e.lines)))
        found = self.numbers(answer)
        unverified = sorted({n for n in found if n not in known}, key=lambda x: float(x))
        cited = sorted(set(re.findall(r"\[(S\d+)\]", answer)), key=lambda x: int(x[1:]))
        return {"numbers": len(found), "verified": sum(n in known for n in found), "unverified": unverified,
                "cited": cited, "blocks": len(evidence)}

    @staticmethod
    def summary(evidence: list[Evidence]) -> str:
        if not evidence:
            return "The validated data has nothing that matches this question."
        parts = []
        for e in evidence[:3]:
            parts.append(f"**{e.title}** [{e.id}]: " + "; ".join(e.lines[:3]))
        return "\n\n".join(parts)

    def answer(self, question: str, use_llm: bool = True) -> Iterator[dict]:
        t0 = time.perf_counter()
        question = question.strip()[:500]
        p = self.plan(question)
        yield {"type": "plan", "entities": [{"type": e.type, "id": e.id, "name": e.name} for e in p.entities],
               "intents": p.intents, "notes": p.notes}
        evidence = self.gather(p)
        yield {"type": "evidence", "items": [e.to_dict() for e in evidence],
               "seconds": round(time.perf_counter() - t0, 2)}
        status = llm.status() if use_llm else {"online": False, "chat_model_ready": False}
        if not (status.get("online") and status.get("chat_model_ready")) or not evidence:
            text = self.summary(evidence)
            yield {"type": "answer", "text": text, "mode": "evidence-only",
                   "reason": "no evidence" if not evidence else "language model not available"}
            yield {"type": "check", **self.check(text, evidence, question)}
            yield {"type": "done", "seconds": round(time.perf_counter() - t0, 2), "mode": "evidence-only"}
            return
        text, stats, mode = "", {}, "llm"
        try:
            for piece in llm.chat_stream(SYSTEM, self.prompt(question, evidence)):
                if piece.get("done"):
                    stats = piece["stats"]
                else:
                    text += piece["text"]
                    yield {"type": "token", "text": piece["text"]}
        except (OSError, RuntimeError) as exc:
            text, mode = self.summary(evidence), "evidence-only"
            yield {"type": "answer", "text": text, "mode": mode, "reason": f"language model error: {exc}"}
        yield {"type": "check", **self.check(text, evidence, question)}
        yield {"type": "done", "seconds": round(time.perf_counter() - t0, 2), "mode": mode, "stats": stats}

    def ask(self, question: str, use_llm: bool = True) -> dict:
        """Non-streaming helper: the whole result as one dict."""
        out: dict = {"question": question, "answer": ""}
        for ev in self.answer(question, use_llm=use_llm):
            if ev["type"] == "token":
                out["answer"] += ev["text"]
            elif ev["type"] == "answer":
                out["answer"] = ev["text"]
                out["mode"] = ev["mode"]
            else:
                out[ev["type"]] = {k: v for k, v in ev.items() if k != "type"}
        return out


@lru_cache(maxsize=1)
def engine() -> Engine:
    return Engine()
