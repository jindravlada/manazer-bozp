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


performance_evaluation_methodology_service = PerformanceEvaluationMethodologyService()
