${ elements.schedule({
    "first_week_start_date": "2025-09-22",
    "week_topics": [
        "Introduction and Basics",
        "Data Structures",
        "Algorithms I",
        "Algorithms II",
        "Dynamic Programming",
        "Graphs I",
        "Graphs II",
        "Advanced Topics",
        "Machine Learning",
        "Optimization",
        "Final Review"
    ],
    "lecture": {
        "collection": "lectures",
        "metadata_key_for_released": "date",
        "title": "Lecture",
        "resources": [
            {
                "text": "[Slides]({{ artifact.path }})",
                "key_for_parts": "slides.txt"
            }
        ]
    },
    "assignments": [
        {
            "collection": "homeworks",
            "metadata_key_for_released": "released",
            "metadata_key_for_due": "due",
            "title": "Homework",
            "resources": [
                {
                    "text": "[Problems]({{ artifact.path }})",
                    "key_for_parts": "homework.txt"
                }
            ]
        }
    ],
    "discussions": []
}) }

---

## All Homeworks

${ elements.listing({
    "collection": "homeworks",
    "columns": [
        {
            "heading": "Assignment",
            "cell_content": "Homework {{ publication.metadata.number }}"
        },
        {
            "heading": "Released",
            "cell_content": "{{ publication.metadata.released.strftime('%b %d') }}"
        },
        {
            "heading": "Due",
            "cell_content": "{{ publication.metadata.due.strftime('%b %d') }}"
        },
        {
            "heading": "Files",
            "cell_content": "[Problems]({{ publication.artifacts['homework.txt'].path }})",
            "requires": {
                "artifacts": ["homework.txt"]
            }
        }
    ],
    "numbered": true
}) }
