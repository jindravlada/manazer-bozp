import unittest

from core.shared.sluzby.performance_evaluation_methodology_service import (
    RATING_GREEN,
    RATING_RED,
    RATING_YELLOW,
    PerformanceEvaluationInput,
    PerformanceEvaluationSignals,
    PerformanceEvaluationSimulationInput,
    performance_evaluation_methodology_service,
)


def _signals(**overrides) -> PerformanceEvaluationSignals:
    defaults = {
        "activities_count": 2,
        "control_points_count": 30,
        "workplaces_covered_count": 1,
        "workplaces_total_count": 4,
        "noncompliance_percent": 12.0,
        "weighted_severity_score": 10,
        "score_per_activity": 5.0,
        "measures_open": 1,
        "measures_closed": 2,
        "open_critical_overdue": 0,
        "open_high_overdue": 0,
        "open_critical_count": 0,
        "high_severity_count": 0,
        "repeated_problems_count": 0,
        "overdue_measures_count": 0,
        "rating_level": RATING_YELLOW,
        "rating_headline": "Celkové hodnocení je žluté.",
        "comparison_summary": "",
    }
    defaults.update(overrides)
    return PerformanceEvaluationSignals(**defaults)


class PerformanceEvaluationMethodologyTestCase(unittest.TestCase):
    def test_appendix_contains_methodology_sections(self) -> None:
        content = performance_evaluation_methodology_service.build(_signals())
        text = content.appendix_text

        self.assertIn("Celkové hodnocení systému BOZP není stanoveno pouze podle počtu", text)
        self.assertIn("Kritéria hodnocení", text)
        self.assertIn("Podíl nevyhovujících bodů", text)
        self.assertIn("40 %", text)
        self.assertIn("Hodnocení závažnosti", text)
        self.assertIn("Kritická", text)
        self.assertIn("15 bodů", text)
        self.assertIn("Rozhodovací pravidla", text)
        self.assertIn("normalizované ukazatele", text)
        self.assertNotIn("prověrka", text.lower())

    def test_reliability_low_for_few_activities(self) -> None:
        content = performance_evaluation_methodology_service.build(
            _signals(activities_count=2, control_points_count=20)
        )
        self.assertEqual(content.reliability.label, "Nízká")
        self.assertIn("2 kontrolních aktivit", content.reliability.explanation)

    def test_reliability_high_for_broad_coverage(self) -> None:
        content = performance_evaluation_methodology_service.build(
            _signals(
                activities_count=20,
                control_points_count=250,
                workplaces_covered_count=5,
                workplaces_total_count=5,
            )
        )
        self.assertEqual(content.reliability.label, "Vysoká")

    def test_expert_justification_for_critical_overdue(self) -> None:
        content = performance_evaluation_methodology_service.build(
            _signals(
                open_critical_overdue=1,
                rating_level=RATING_RED,
                rating_headline="Celkové hodnocení je červené.",
            )
        )
        self.assertIn("kritická závada po termínu", content.expert_justification)
        self.assertIn("nevyhovující", content.expert_justification)

    def test_expert_justification_combines_year_over_year_improvement(self) -> None:
        content = performance_evaluation_methodology_service.build(
            _signals(
                comparison_summary=(
                    "Přestože meziročně došlo ke snížení počtu neshod na jednu kontrolní aktivitu "
                    "z 2.00 na 1.00"
                ),
                open_critical_overdue=1,
                rating_level=RATING_RED,
            )
        )
        self.assertIn("meziročně", content.expert_justification)
        self.assertIn("avšak", content.expert_justification)

    def test_placeholders_include_methodology_keys(self) -> None:
        content = performance_evaluation_methodology_service.build(_signals())
        placeholders = content.to_placeholders()

        self.assertIn("priloha_metodika_text", placeholders)
        self.assertIn("metodika_zduvodneni_text", placeholders)
        self.assertIn("spolehlivost_hodnoceni", placeholders)
        self.assertIn("spolehlivost_hodnoceni_text", placeholders)
        self.assertIn("spolehlivost_hodnoceni_vysvetleni", placeholders)
        self.assertEqual(placeholders["spolehlivost_hodnoceni_text"], "Reprezentativnost dat: Nízká")

    def test_green_rating_justification(self) -> None:
        content = performance_evaluation_methodology_service.build(
            _signals(
                noncompliance_percent=2.0,
                rating_level=RATING_GREEN,
                rating_headline="Celkové hodnocení je zelené.",
            )
        )
        self.assertIn("nízký", content.expert_justification.lower())


def _evaluation_input(**overrides) -> PerformanceEvaluationInput:
    defaults = {
        "activities_count": 5,
        "control_points_count": 100,
        "workplaces_covered_count": 2,
        "workplaces_total_count": 4,
        "noncompliance_count": 10,
        "noncompliance_percent": 10.0,
        "weighted_severity_score": 30,
        "score_per_activity": 6.0,
        "measures_total": 4,
        "measures_open": 1,
        "measures_closed": 3,
        "open_critical_overdue": 0,
        "open_high_overdue": 1,
        "open_critical_count": 0,
        "critical_findings_count": 0,
        "high_findings_count": 1,
        "repeated_problems_count": 0,
        "overdue_measures_count": 1,
        "comparison_summary": "",
    }
    defaults.update(overrides)
    return PerformanceEvaluationInput(**defaults)


class PerformanceEvaluationExplanationTestCase(unittest.TestCase):
    def test_build_explanation_contains_indicators_and_rules(self) -> None:
        explanation = performance_evaluation_methodology_service.build_explanation(
            _evaluation_input()
        )
        labels = [item.label for item in explanation.indicators]
        self.assertIn("Podíl nevyhovujících bodů", labels)
        self.assertIn("Váhové skóre zjištění", labels)
        self.assertTrue(any(rule.applied for rule in explanation.rules))
        self.assertTrue(explanation.justification)

    def test_critical_overdue_forces_red_rating(self) -> None:
        rating = performance_evaluation_methodology_service.determine_rating(
            _evaluation_input(open_critical_overdue=1, open_critical_count=1)
        )
        self.assertEqual(rating.level, RATING_RED)

    def test_simulation_recalculates_rating(self) -> None:
        baseline = performance_evaluation_methodology_service.build_explanation(
            _evaluation_input()
        )
        self.assertEqual(baseline.rating.level, RATING_YELLOW)

        simulated = performance_evaluation_methodology_service.simulate(
            PerformanceEvaluationSimulationInput(
                activities_count=5,
                control_points_count=100,
                noncompliance_count=10,
                overdue_measures_count=1,
                critical_findings_count=1,
                high_severity_count=0,
                repeated_problems_count=0,
            )
        )
        self.assertEqual(simulated.rating.level, RATING_RED)
        self.assertIn("kritická závada", simulated.justification.lower())

    def test_green_rating_for_stable_system(self) -> None:
        rating = performance_evaluation_methodology_service.determine_rating(
            _evaluation_input(
                noncompliance_count=2,
                noncompliance_percent=2.0,
                weighted_severity_score=2,
                high_findings_count=0,
                critical_findings_count=0,
                open_high_overdue=0,
                overdue_measures_count=0,
                measures_open=0,
                measures_closed=2,
            )
        )
        self.assertEqual(rating.level, RATING_GREEN)


if __name__ == "__main__":
    unittest.main()
