# Example Course

Welcome to the example course website built with Automata!

## Homeworks

${ elements.listing({
    "collection": "homeworks",
    "columns": [
        {
            "heading": "Assignment",
            "cell_content": "Homework {{ publication.metadata.number }}"
        },
        {
            "heading": "Files",
            "cell_content": "[Problems]({{ publication.artifacts['homework.txt'].path }})",
            "requires": {
                "artifacts": ["homework.txt"]
            }
        }
    ]
}) }

## Lectures

${ elements.listing({
    "collection": "lectures",
    "columns": [
        {
            "heading": "Lecture",
            "cell_content": "Lecture {{ publication.metadata.number }} &mdash; {{ publication.metadata.topic }}"
        },
        {
            "heading": "Files",
            "cell_content": "[Slides]({{ publication.artifacts['slides.txt'].path }})",
            "requires": {
                "artifacts": ["slides.txt"]
            }
        }
    ]
}) }
