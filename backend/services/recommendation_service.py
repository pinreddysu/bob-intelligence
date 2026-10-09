"""
Recommendation service — placeholder for Milestone 3.

Will implement a transparent rule engine that evaluates a story and returns:
  - mode: "bob_led" | "collaborative" | "human_led"
  - rationale: prose explanation
  - evidence: list of evidence items
  - risks: list of risk items
  - counterevidence: list of counter-evidence items
  - uncertainty_note: explicit note when historical data is absent

Interface (stable across milestones):
    RecommendationService.generate(story) -> Recommendation
"""
