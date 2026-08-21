"""
Static Taxonomy Mapping for Hierarchical Tagging

Maps specific sub-topics/tags to their broader parent categories.
This allows the Interest Processor to credit broader categories when
a user interacts with a niche tag.
"""

TAG_HIERARCHY = {
    "m4": ["bmw", "cars"],
    "m3": ["bmw", "cars"],
    "m5": ["bmw", "cars"],
    "bmw": ["cars", "vehicles"],
    "mercedes": ["cars", "vehicles"],
    "audi": ["cars", "vehicles"],
    "porsche": ["cars", "vehicles"],
    "lamborghini": ["cars", "vehicles"],
    "comedy": ["entertainment"],
    "standup": ["comedy", "entertainment"],
    "sketch": ["comedy", "entertainment"],
    "cricket": ["sports"],
    "football": ["sports"],
    "basketball": ["sports"],
    "tennis": ["sports"],
    "vlog": ["lifestyle"],
    "fashion": ["lifestyle"],
    "makeup": ["beauty", "lifestyle"],
    "technology": ["science"],
    "programming": ["technology"],
    "python": ["programming", "technology"],
    "react": ["programming", "technology"],
}

def expand_tags(tags: list[str]) -> list[str]:
    """
    Given a list of tags, returns a new list containing the original tags
    plus all of their hierarchical parent tags, deduplicated.
    """
    expanded = set(t.lower() for t in tags)
    for tag in tags:
        lower_tag = tag.lower()
        if lower_tag in TAG_HIERARCHY:
            expanded.update(TAG_HIERARCHY[lower_tag])
    return list(expanded)
