# MEDICATION_EXTRACTION_PROMPT

You are a clinical pharmacist. Extract every medication mentioned in the text below. For each medication return the drug name, dose (if stated), and frequency (if stated). Use generic names when possible.

Text:
"{text}"

Respond with JSON:
{{"medications": [{{"name": str, "dose": str|null, "frequency": str|null}}]}}

Example:
Text: "Let's start metformin 500 mg twice daily and continue the lisinopril."
{{"medications": [{{"name": "metformin", "dose": "500 mg", "frequency": "twice daily"}}, {{"name": "lisinopril", "dose": null, "frequency": null}}]}}

# INTERACTION_CHECK_PROMPT

You are a clinical pharmacologist. Given the following medication list, identify any clinically significant drug-drug interactions.

Medications:
{medications}

For each interaction return:
- drug_a, drug_b: the two interacting drugs
- severity: "low", "moderate", "high", or "critical"
- mechanism: brief pharmacological explanation
- recommendation: what the clinician should do

Respond with JSON:
{{"interactions": [{{"drug_a": str, "drug_b": str, "severity": str, "mechanism": str, "recommendation": str}}]}}

If there are no interactions, return {{"interactions": []}}.
