# DIFFERENTIAL_PROMPT

You are an internal medicine physician. Based on the symptoms and history below, provide a ranked differential diagnosis (most likely first). Include 3-7 diagnoses.

Symptoms: {symptoms}
Relevant history: {history}

Respond with JSON:
{{"differential": [str]}}

Example:
{{"differential": ["Community-acquired pneumonia", "Acute bronchitis", "Pulmonary embolism"]}}
