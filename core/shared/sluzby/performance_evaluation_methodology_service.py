from dataclasses import dataclass

RELIABILITY_LOW = "low"
RELIABILITY_MEDIUM = "medium"
RELIABILITY_HIGH = "high"

RATING_GREEN = "green"
RATING_YELLOW = "yellow"
RATING_RED = "red"

SEVERITY_LEVEL_LOW = "nizka"
SEVERITY_LEVEL_MEDIUM = "stredni"
SEVERITY_LEVEL_HIGH = "vysoka"
SEVERITY_LEVEL_CRITICAL = "kriticka"

SEVERITY_WEIGHTS: dict[str, int] = {
    SEVERITY_LEVEL_LOW: 1,
    SEVERITY_LEVEL_MEDIUM: 3,
    SEVERITY_LEVEL_HIGH: 7,
    SEVERITY_LEVEL_CRITICAL: 15,
}

SEVERITY_LABELS: dict[str, str] = {
    SEVERITY_LEVEL_LOW: "Nízká",
    SEVERITY_LEVEL_MEDIUM: "Střední",
    SEVERITY_LEVEL_HIGH: "Vysoká",
    SEVERITY_LEVEL_CRITICAL: "Kritická",
}

EVALUATION_CRITERIA: tuple[tuple[str, str], ...] = (
    ("Podíl nevyhovujících bodů", "40 %"),
    ("Závažnost zjištění", "30 %"),
    ("Plnění opatření", "20 %"),
    ("Opakované problémy", "10 %"),
)

DECISION_RULES: tuple[str, ...] = (
    "Kritická otevřená závada po termínu → celkové hodnocení nemůže být lepší než červené.",
    "Vysoká otevřená závada po termínu → celkové hodnocení nemůže být lepší než žluté.",
    "Vyšší počet kontrolních aktivit může přinést vyšší počet zjištění. "
    "Proto jsou používány normalizované ukazatele (například počet neshod na jednu kontrolní aktivitu).",
    "Opakované problémy zhoršují hodnocení systému.",
    "Splnění opatření v termínu zlepšuje hodnocení systému.",
)

NONCOMPLIANCE_RED_THRESHOLD = 15.0
NONCOMPLIANCE_GREEN_THRESHOLD = 5.0
OVERDUE_MEASURES_RED_THRESHOLD = 3

INDICATOR_EXPLANATIONS: dict[str, str] = {
    "noncompliance": (
        "Udává, jak velká část kontrolních bodů nevyhověla. "
        "Překročení 15 % obvykle vede ke červenému hodnocení."
    ),
    "weighted_score": (
        "Součet bodů podle závažnosti zjištění "
        "(nízká 1, střední 3, vysoká 7, kritická 15). "
        "Vyšší skóre signalizuje závažnější rizika."
    ),
    "overdue_measures": (
        "Počet otevřených opatření po stanoveném termínu. "
        "Každé opožděné opatření oslabuje efektivitu nápravy."
    ),
    "repeated_problems": (
        "Problémy evidované ve více kontrolních aktivitách. "
        "Opakování naznačuje systémový charakter nedostatku."
    ),
    "activities_count": (
        "Vyšší počet kontrolních aktivit obvykle vede k vyššímu počtu zjištění. "
        "Proto jsou používány normalizované ukazatele."
    ),
    "control_points_count": (
        "Rozsah hodnocených kontrolních bodů ovlivňuje spolehlivost závěru. "
        "Větší vzorek posiluje reprezentativnost výsledku."
    ),
}


@dataclass(frozen=True)
class PerformanceEvaluationSignals:
    """Vstupní signály pro metodiku – bez vazby na konkrétní modul."""

    activities_count: int
    control_points_count: int
    workplaces_covered_count: int
    workplaces_total_count: int
    noncompliance_percent: float
    weighted_severity_score: int
    score_per_activity: float | None
    measures_open: int
    measures_closed: int
    open_critical_overdue: int
    open_high_overdue: int
    open_critical_count: int
    high_severity_count: int
    repeated_problems_count: int
    overdue_measures_count: int
    rating_level: str
    rating_headline: str
    comparison_summary: str = ""


@dataclass(frozen=True)
class PerformanceEvaluationReliability:
    level: str
    label: str
    explanation: str

    def to_placeholders(self) -> dict[str, str]:
        return {
            "spolehlivost_hodnoceni": self.label,
            "spolehlivost_hodnoceni_text": f"Spolehlivost hodnocení: {self.label}",
            "spolehlivost_hodnoceni_vysvetleni": self.explanation,
        }


@dataclass(frozen=True)
class PerformanceEvaluationInput:
    """Vstupy pro výpočet hodnocení – bez vazby na konkrétní modul."""

    activities_count: int
    control_points_count: int
    workplaces_covered_count: int
    workplaces_total_count: int
    noncompliance_count: int
    noncompliance_percent: float
    weighted_severity_score: int
    score_per_activity: float | None
    measures_total: int
    measures_open: int
    measures_closed: int
    open_critical_overdue: int
    open_high_overdue: int
    open_critical_count: int
    critical_findings_count: int
    high_findings_count: int
    repeated_problems_count: int
    overdue_measures_count: int
    comparison_summary: str = ""


@dataclass(frozen=True)
class PerformanceRatingResult:
    level: str
    emoji: str
    headline: str


@dataclass(frozen=True)
class PerformanceEvaluationIndicator:
    key: str
    label: str
    value_text: str
    influenced: bool
    explanation: str


@dataclass(frozen=True)
class PerformanceEvaluationAppliedRule:
    label: str
    effect_text: str
    applied: bool


@dataclass(frozen=True)
class PerformanceEvaluationSimulationInput:
    activities_count: int
    control_points_count: int
    noncompliance_count: int
    overdue_measures_count: int
    critical_findings_count: int
    high_severity_count: int
    repeated_problems_count: int
    measures_open: int = 0
    measures_closed: int = 0
    workplaces_covered_count: int = 1
    workplaces_total_count: int = 1
    comparison_summary: str = ""


@dataclass(frozen=True)
class PerformanceEvaluationExplanation:
    rating: PerformanceRatingResult
    indicators: tuple[PerformanceEvaluationIndicator, ...]
    rules: tuple[PerformanceEvaluationAppliedRule, ...]
    justification: str
    reliability: PerformanceEvaluationReliability
    simulation: PerformanceEvaluationSimulationInput


@dataclass(frozen=True)
class PerformanceMethodologyContent:
    appendix_text: str
    expert_justification: str
    reliability: PerformanceEvaluationReliability

    def to_placeholders(self) -> dict[str, str]:
        values = {
            "priloha_metodika_text": self.appendix_text,
            "metodika_zduvodneni_text": self.expert_justification,
        }
        values.update(self.reliability.to_placeholders())
        return values


class PerformanceEvaluationMethodologyService:
    def build_explanation(self, evaluation_input: PerformanceEvaluationInput) -> PerformanceEvaluationExplanation:
        rating = self.determine_rating(evaluation_input)
        signals = self._signals_from_input(evaluation_input, rating=rating)
        methodology = self.build(signals)
        indicators = self._build_indicators(evaluation_input)
        rules = self._build_applied_rules(evaluation_input, rating)
        simulation = self._input_to_simulation(evaluation_input)
        return PerformanceEvaluationExplanation(
            rating=rating,
            indicators=indicators,
            rules=rules,
            justification=methodology.expert_justification,
            reliability=methodology.reliability,
            simulation=simulation,
        )

    def simulate(self, simulation: PerformanceEvaluationSimulationInput) -> PerformanceEvaluationExplanation:
        return self.build_explanation(self._simulation_to_input(simulation))

    def determine_rating(self, evaluation_input: PerformanceEvaluationInput) -> PerformanceRatingResult:
        majority_closed = (
            evaluation_input.measures_total == 0
            or evaluation_input.measures_closed >= evaluation_input.measures_open
        )

        if evaluation_input.open_critical_overdue >= 1:
            return PerformanceRatingResult(
                level=RATING_RED,
                emoji="🔴",
                headline="Celkové hodnocení je červené kvůli kritické otevřené závadě po termínu.",
            )
        if evaluation_input.open_critical_count >= 2:
            return PerformanceRatingResult(
                level=RATING_RED,
                emoji="🔴",
                headline="Celkové hodnocení je červené kvůli více kritickým otevřeným závadám.",
            )
        if evaluation_input.noncompliance_percent > NONCOMPLIANCE_RED_THRESHOLD:
            return PerformanceRatingResult(
                level=RATING_RED,
                emoji="🔴",
                headline="Celkové hodnocení je červené kvůli vysokému podílu nevyhovujících bodů.",
            )
        if evaluation_input.overdue_measures_count >= OVERDUE_MEASURES_RED_THRESHOLD:
            return PerformanceRatingResult(
                level=RATING_RED,
                emoji="🔴",
                headline="Celkové hodnocení je červené kvůli vysokému počtu opatření po termínu.",
            )

        if (
            evaluation_input.open_critical_count == 0
            and evaluation_input.open_high_overdue == 0
            and evaluation_input.noncompliance_percent <= NONCOMPLIANCE_GREEN_THRESHOLD
            and majority_closed
            and evaluation_input.high_findings_count == 0
            and evaluation_input.critical_findings_count == 0
        ):
            return PerformanceRatingResult(
                level=RATING_GREEN,
                emoji="🟢",
                headline="Celkové hodnocení je zelené – systém BOZP je funkční a stabilní.",
            )

        return PerformanceRatingResult(
            level=RATING_YELLOW,
            emoji="🟡",
            headline="Celkové hodnocení je žluté – existují významnější nedostatky vyžadující pozornost.",
        )

    def build(self, signals: PerformanceEvaluationSignals) -> PerformanceMethodologyContent:
        reliability = self._build_reliability(signals)
        expert_justification = self._build_expert_justification(signals)
        appendix_text = self._build_appendix_text(
            signals,
            reliability=reliability,
            expert_justification=expert_justification,
        )
        return PerformanceMethodologyContent(
            appendix_text=appendix_text,
            expert_justification=expert_justification,
            reliability=reliability,
        )

    def _build_reliability(self, signals: PerformanceEvaluationSignals) -> PerformanceEvaluationReliability:
        score = 0
        if signals.activities_count >= 15:
            score += 2
        elif signals.activities_count >= 5:
            score += 1

        if signals.control_points_count >= 200:
            score += 2
        elif signals.control_points_count >= 50:
            score += 1

        if signals.workplaces_total_count > 0:
            coverage = signals.workplaces_covered_count / signals.workplaces_total_count
            if coverage >= 0.8:
                score += 2
            elif coverage >= 0.4:
                score += 1
        elif signals.workplaces_covered_count >= 3:
            score += 1

        if score >= 5:
            level = RELIABILITY_HIGH
            label = "Vysoká"
            explanation = (
                f"Hodnocení vychází z {signals.activities_count} kontrolních aktivit, "
                f"{signals.control_points_count} kontrolních bodů a pokrytí "
                f"{signals.workplaces_covered_count} pracovišť. "
                "Rozsah dat podporuje reprezentativní závěr."
            )
        elif score >= 2:
            level = RELIABILITY_MEDIUM
            label = "Střední"
            explanation = (
                f"Hodnocení vychází z {signals.activities_count} kontrolních aktivit "
                f"a {signals.control_points_count} kontrolních bodů. "
                "Závěry jsou použitelné, avšak s omezenou reprezentativitou."
            )
        else:
            level = RELIABILITY_LOW
            label = "Nízká"
            explanation = (
                f"Hodnocení vychází pouze z {signals.activities_count} kontrolních aktivit. "
                "Omezený rozsah dat snižuje reprezentativnost výsledku."
            )

        return PerformanceEvaluationReliability(level=level, label=label, explanation=explanation)

    def _build_expert_justification(self, signals: PerformanceEvaluationSignals) -> str:
        parts: list[str] = []

        if signals.comparison_summary:
            parts.append(signals.comparison_summary.rstrip("."))

        if signals.open_critical_overdue >= 1:
            parts.append(
                "zůstává otevřená kritická závada po termínu. "
                "Z tohoto důvodu je systém hodnocen jako nevyhovující"
            )
        elif signals.open_critical_count >= 2:
            parts.append(
                f"jsou evidovány {signals.open_critical_count} kritické otevřené závady, "
                "což představuje zásadní riziko pro bezpečnost práce"
            )
        elif signals.open_high_overdue >= 1:
            parts.append(
                "zůstává otevřená závada s vysokou závažností po termínu, "
                "což omezuje celkové hodnocení na úroveň vyžadující zvýšenou pozornost"
            )
        elif signals.high_severity_count >= 1 and signals.rating_level == RATING_YELLOW:
            parts.append(
                "jsou evidována zjištění s vysokou závažností, "
                "která vyžadují zvýšenou pozornost vedení"
            )
        elif signals.noncompliance_percent > 15:
            parts.append(
                f"podíl nevyhovujících bodů ({signals.noncompliance_percent:.2f} %) překračuje "
                "přijatelnou úroveň výkonnosti systému"
            )
        elif signals.overdue_measures_count >= 3:
            parts.append(
                f"je otevřeno {signals.overdue_measures_count} opatření po termínu, "
                "což oslabuje efektivitu nápravných procesů"
            )
        elif signals.repeated_problems_count:
            parts.append(
                "některé problémy se opakují v různých kontrolních aktivitách, "
                "což signalizuje systémový charakter nedostatků"
            )
        elif signals.rating_level == RATING_GREEN:
            parts.append(
                "podíl nevyhovujících bodů je nízký, závažnost zjištění nepřekračuje "
                "práh pro zásadní rizika a opatření jsou plněna včas"
            )
        else:
            parts.append(
                "hodnocení kombinuje podíl nevyhovujících bodů, váhové skóre závažnosti "
                "a stav plnění opatření"
            )

        if not parts:
            return signals.rating_headline

        if len(parts) == 1:
            text = parts[0]
            if not text[0].isupper():
                text = text[0].upper() + text[1:]
            return f"{text}."

        lead = parts[0]
        if not lead[0].isupper():
            lead = lead[0].upper() + lead[1:]
        tail = parts[1]
        return f"{lead}, avšak {tail}."

    def _build_appendix_text(
        self,
        signals: PerformanceEvaluationSignals,
        *,
        reliability: PerformanceEvaluationReliability,
        expert_justification: str,
    ) -> str:
        lines = [
            (
                "Celkové hodnocení systému BOZP není stanoveno pouze podle počtu zjištěných neshod.\n"
                "Hodnocení zohledňuje zejména:\n"
                "• podíl nevyhovujících kontrolních bodů,\n"
                "• závažnost jednotlivých zjištění,\n"
                "• stav plnění uložených opatření,\n"
                "• opakované problémy,\n"
                "• význam jednotlivých zjištění pro bezpečnost práce.\n"
                "Cílem metodiky je hodnotit skutečnou výkonnost systému BOZP, "
                "nikoli pouze počet evidovaných nedostatků."
            ),
            "",
            "Kritéria hodnocení",
            "Kritérium".ljust(34) + "Váha",
        ]
        for criterion, weight in EVALUATION_CRITERIA:
            lines.append(f"{criterion.ljust(34)}{weight}")

        lines.extend(
            [
                "",
                "Hodnocení závažnosti",
            ]
        )
        for level in (
            SEVERITY_LEVEL_LOW,
            SEVERITY_LEVEL_MEDIUM,
            SEVERITY_LEVEL_HIGH,
            SEVERITY_LEVEL_CRITICAL,
        ):
            label = SEVERITY_LABELS[level]
            points = SEVERITY_WEIGHTS[level]
            points_label = "bod" if points == 1 else "body" if 2 <= points <= 4 else "bodů"
            lines.append(f"{label.ljust(12)}{points} {points_label}")

        lines.extend(["", "Rozhodovací pravidla"])
        lines.extend(f"• {rule}" for rule in DECISION_RULES)

        lines.extend(
            [
                "",
                "Vysvětlení výsledného hodnocení tohoto období",
                expert_justification,
                "",
                f"Spolehlivost hodnocení: {reliability.label}",
                reliability.explanation,
            ]
        )
        return "\n".join(lines)

    def _signals_from_input(
        self,
        evaluation_input: PerformanceEvaluationInput,
        *,
        rating: PerformanceRatingResult,
    ) -> PerformanceEvaluationSignals:
        return PerformanceEvaluationSignals(
            activities_count=evaluation_input.activities_count,
            control_points_count=evaluation_input.control_points_count,
            workplaces_covered_count=evaluation_input.workplaces_covered_count,
            workplaces_total_count=evaluation_input.workplaces_total_count,
            noncompliance_percent=evaluation_input.noncompliance_percent,
            weighted_severity_score=evaluation_input.weighted_severity_score,
            score_per_activity=evaluation_input.score_per_activity,
            measures_open=evaluation_input.measures_open,
            measures_closed=evaluation_input.measures_closed,
            open_critical_overdue=evaluation_input.open_critical_overdue,
            open_high_overdue=evaluation_input.open_high_overdue,
            open_critical_count=evaluation_input.open_critical_count,
            high_severity_count=evaluation_input.high_findings_count,
            repeated_problems_count=evaluation_input.repeated_problems_count,
            overdue_measures_count=evaluation_input.overdue_measures_count,
            rating_level=rating.level,
            rating_headline=rating.headline,
            comparison_summary=evaluation_input.comparison_summary,
        )

    def _build_indicators(
        self,
        evaluation_input: PerformanceEvaluationInput,
    ) -> tuple[PerformanceEvaluationIndicator, ...]:
        influenced_noncompliance = (
            evaluation_input.noncompliance_percent > 0
            or evaluation_input.noncompliance_percent > NONCOMPLIANCE_RED_THRESHOLD
        )
        influenced_weighted = evaluation_input.weighted_severity_score > 0
        influenced_overdue = evaluation_input.overdue_measures_count > 0
        influenced_repeated = evaluation_input.repeated_problems_count > 0

        return (
            PerformanceEvaluationIndicator(
                key="noncompliance",
                label="Podíl nevyhovujících bodů",
                value_text=self._format_percent(evaluation_input.noncompliance_percent),
                influenced=influenced_noncompliance,
                explanation=INDICATOR_EXPLANATIONS["noncompliance"],
            ),
            PerformanceEvaluationIndicator(
                key="weighted_score",
                label="Váhové skóre zjištění",
                value_text=f"{evaluation_input.weighted_severity_score} bodů",
                influenced=influenced_weighted,
                explanation=INDICATOR_EXPLANATIONS["weighted_score"],
            ),
            PerformanceEvaluationIndicator(
                key="overdue_measures",
                label="Otevřená opatření po termínu",
                value_text=str(evaluation_input.overdue_measures_count),
                influenced=influenced_overdue,
                explanation=INDICATOR_EXPLANATIONS["overdue_measures"],
            ),
            PerformanceEvaluationIndicator(
                key="repeated_problems",
                label="Opakované problémy",
                value_text=str(evaluation_input.repeated_problems_count),
                influenced=influenced_repeated,
                explanation=INDICATOR_EXPLANATIONS["repeated_problems"],
            ),
            PerformanceEvaluationIndicator(
                key="activities_count",
                label="Počet kontrolních aktivit",
                value_text=str(evaluation_input.activities_count),
                influenced=evaluation_input.activities_count > 0,
                explanation=INDICATOR_EXPLANATIONS["activities_count"],
            ),
            PerformanceEvaluationIndicator(
                key="control_points_count",
                label="Počet kontrolních bodů",
                value_text=str(evaluation_input.control_points_count),
                influenced=evaluation_input.control_points_count > 0,
                explanation=INDICATOR_EXPLANATIONS["control_points_count"],
            ),
        )

    def _build_applied_rules(
        self,
        evaluation_input: PerformanceEvaluationInput,
        rating: PerformanceRatingResult,
    ) -> tuple[PerformanceEvaluationAppliedRule, ...]:
        return (
            PerformanceEvaluationAppliedRule(
                label="Kritická závada po termínu",
                effect_text="→ červené hodnocení",
                applied=evaluation_input.open_critical_overdue >= 1,
            ),
            PerformanceEvaluationAppliedRule(
                label="Více kritických otevřených závad",
                effect_text="→ červené hodnocení",
                applied=evaluation_input.open_critical_count >= 2,
            ),
            PerformanceEvaluationAppliedRule(
                label="Podíl nevyhovujících bodů > 15 %",
                effect_text="→ červené hodnocení",
                applied=evaluation_input.noncompliance_percent > NONCOMPLIANCE_RED_THRESHOLD,
            ),
            PerformanceEvaluationAppliedRule(
                label="3 a více opatření po termínu",
                effect_text="→ červené hodnocení",
                applied=evaluation_input.overdue_measures_count >= OVERDUE_MEASURES_RED_THRESHOLD,
            ),
            PerformanceEvaluationAppliedRule(
                label="Vysoká závada po termínu",
                effect_text="→ hodnocení maximálně žluté",
                applied=evaluation_input.open_high_overdue >= 1,
            ),
            PerformanceEvaluationAppliedRule(
                label="Normalizované ukazatele",
                effect_text="→ zlepšení oproti minulému roku",
                applied=bool(evaluation_input.comparison_summary),
            ),
            PerformanceEvaluationAppliedRule(
                label="Opakované problémy",
                effect_text="→ zhoršení hodnocení",
                applied=evaluation_input.repeated_problems_count > 0,
            ),
            PerformanceEvaluationAppliedRule(
                label="Splnění opatření v termínu",
                effect_text="→ zlepšení hodnocení",
                applied=(
                    evaluation_input.overdue_measures_count == 0
                    and evaluation_input.measures_closed > 0
                ),
            ),
        )

    def _input_to_simulation(
        self,
        evaluation_input: PerformanceEvaluationInput,
    ) -> PerformanceEvaluationSimulationInput:
        return PerformanceEvaluationSimulationInput(
            activities_count=max(0, evaluation_input.activities_count),
            control_points_count=max(0, evaluation_input.control_points_count),
            noncompliance_count=max(0, evaluation_input.noncompliance_count),
            overdue_measures_count=max(0, evaluation_input.overdue_measures_count),
            critical_findings_count=max(0, evaluation_input.critical_findings_count),
            high_severity_count=max(0, evaluation_input.high_findings_count),
            repeated_problems_count=max(0, evaluation_input.repeated_problems_count),
            measures_open=max(0, evaluation_input.measures_open),
            measures_closed=max(0, evaluation_input.measures_closed),
            workplaces_covered_count=max(0, evaluation_input.workplaces_covered_count),
            workplaces_total_count=max(1, evaluation_input.workplaces_total_count),
            comparison_summary=evaluation_input.comparison_summary,
        )

    def _simulation_to_input(
        self,
        simulation: PerformanceEvaluationSimulationInput,
    ) -> PerformanceEvaluationInput:
        activities_count = max(0, simulation.activities_count)
        control_points_count = max(0, simulation.control_points_count)
        noncompliance_count = max(0, simulation.noncompliance_count)
        critical_findings_count = max(0, simulation.critical_findings_count)
        high_severity_count = max(0, simulation.high_severity_count)
        overdue_measures_count = max(0, simulation.overdue_measures_count)

        if noncompliance_count > control_points_count and control_points_count > 0:
            noncompliance_count = control_points_count

        noncompliance_percent = (
            noncompliance_count / control_points_count * 100
            if control_points_count > 0
            else 0.0
        )
        remaining = max(0, noncompliance_count - critical_findings_count - high_severity_count)
        weighted_severity_score = (
            critical_findings_count * SEVERITY_WEIGHTS[SEVERITY_LEVEL_CRITICAL]
            + high_severity_count * SEVERITY_WEIGHTS[SEVERITY_LEVEL_HIGH]
            + remaining * SEVERITY_WEIGHTS[SEVERITY_LEVEL_MEDIUM]
        )
        score_per_activity = (
            weighted_severity_score / activities_count if activities_count > 0 else None
        )

        open_critical_overdue = (
            min(critical_findings_count, overdue_measures_count)
            if critical_findings_count > 0 and overdue_measures_count > 0
            else 0
        )
        open_high_overdue = (
            min(high_severity_count, overdue_measures_count)
            if high_severity_count > 0 and overdue_measures_count > 0
            else 0
        )

        return PerformanceEvaluationInput(
            activities_count=activities_count,
            control_points_count=control_points_count,
            workplaces_covered_count=max(0, simulation.workplaces_covered_count),
            workplaces_total_count=max(1, simulation.workplaces_total_count),
            noncompliance_count=noncompliance_count,
            noncompliance_percent=noncompliance_percent,
            weighted_severity_score=weighted_severity_score,
            score_per_activity=score_per_activity,
            measures_total=max(0, simulation.measures_open + simulation.measures_closed),
            measures_open=max(0, simulation.measures_open),
            measures_closed=max(0, simulation.measures_closed),
            open_critical_overdue=open_critical_overdue,
            open_high_overdue=open_high_overdue,
            open_critical_count=critical_findings_count,
            critical_findings_count=critical_findings_count,
            high_findings_count=high_severity_count,
            repeated_problems_count=max(0, simulation.repeated_problems_count),
            overdue_measures_count=overdue_measures_count,
            comparison_summary=simulation.comparison_summary,
        )

    @staticmethod
    def _format_percent(value: float) -> str:
        return f"{value:.2f} %".replace(".", ",")


performance_evaluation_methodology_service = PerformanceEvaluationMethodologyService()
