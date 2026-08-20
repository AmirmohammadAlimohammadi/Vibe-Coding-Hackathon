from enum import StrEnum


class ExpertiseLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


DEFAULT_EXPERTISE_LEVEL = ExpertiseLevel.INTERMEDIATE
