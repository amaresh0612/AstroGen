"""
House cluster lookup table per prediction topic.

Answers: "which houses are relevant for this topic?"
Does NOT answer: "will the event happen?" (that is promise_denial.py)
Does NOT answer: "what exact event?" (that is AI interpretation)

Based on KP standard house mapping per PRD §9.
"""
from __future__ import annotations

EVENT_HOUSES: dict[str, list[int]] = {
    "career":            [6, 10, 11],
    "promotion":         [2, 6, 10, 11],     # growth in the same service
    "job_change":        [3, 5, 9, 10, 12],  # 5/9 = 12th from 6/10 (leaving), 3 = change
    "business":          [2, 7, 10, 11],     # trade/self-employment; 7 = dealings (and partner)
    "marriage":          [2, 7, 11],
    "relationship":      [5, 7, 11],
    "children":          [5, 11],
    "property":          [4, 11],
    "travel":            [3, 9, 12],
    "travel_home":       [3, 4, 9, 12],      # journeys to/with home and family
    "foreign_settlement":[4, 9, 12],
    "wealth":            [2, 6, 10, 11],
    "expenses":          [12],               # expenditure; read against 2/11
    "education":         [4, 5, 9],
    "health":            [1, 6, 8],   # soft reference only — no diagnoses
    "spirituality":      [8, 9, 12],
}

# Houses that typically indicate denial / obstruction for the primary topic
DENIAL_HOUSES: dict[str, list[int]] = {
    "career":            [1, 4, 5, 8, 9, 12],
    "promotion":         [5, 8, 9, 12],
    "job_change":        [2, 6, 11],         # continuity in the present service
    "business":          [6, 8, 12],
    "travel_home":       [1, 7, 8],
    "expenses":          [2, 11],
    "marriage":          [1, 6, 10, 12],
    "relationship":      [1, 6, 8, 12],
    "children":          [1, 4, 8],
    "property":          [3, 6, 8, 12],
    "travel":            [1, 2, 7, 8],
    "foreign_settlement":[1, 2, 7, 10],
    "wealth":            [1, 3, 8, 12],
    "education":         [1, 3, 6, 8, 12],
}


def get_topic_houses(topic: str) -> list[int]:
    """Return primary house list for a topic. Returns empty list if unknown."""
    return EVENT_HOUSES.get(topic.lower(), [])


def get_denial_houses(topic: str) -> list[int]:
    """Return denial/obstruction house list for a topic."""
    return DENIAL_HOUSES.get(topic.lower(), [])


TOPIC_LABELS: dict[str, str] = {
    "career":            "Career & Profession",
    "promotion":         "Promotion & Recognition",
    "job_change":        "Job / Employer Change",
    "business":          "Business / Self-Employment",
    "marriage":          "Marriage",
    "relationship":      "Relationship & Partnership",
    "children":          "Children",
    "property":          "Property",
    "travel":            "Travel",
    "travel_home":       "Travel Home / Family",
    "foreign_settlement":"Foreign Settlement",
    "wealth":            "Wealth & Financial Gains",
    "expenses":          "Expenses & Outflow",
    "education":         "Education & Qualification",
    "health":            "Health (Soft Reference)",
    "spirituality":      "Spirituality & Inner Life",
}

ALL_TOPICS: list[str] = list(EVENT_HOUSES.keys())
