from django import template

register = template.Library()


@register.filter
def get_item(value, key):
    """
    Get an item from either:
    1. A dictionary using dictionary.get(key)
    2. A list of subject-result dictionaries where
       item["subject"]["subject_id"] matches key
    """

    if value is None:
        return None

    # Normal dictionary lookup
    if isinstance(value, dict):
        return value.get(key)

    # Subject-result list lookup
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue

            subject = item.get("subject")

            if isinstance(subject, dict):
                if subject.get("subject_id") == key:
                    return item

        return None

    return None
