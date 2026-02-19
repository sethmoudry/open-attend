# LLM_JUDGE_PROMPT

You are an expert clinical documentation reviewer. Score the following SOAP note on 5 dimensions, each from 1 (poor) to 5 (excellent).

ORIGINAL DIALOGUE:
{dialogue}

GENERATED SOAP NOTE:
{soap_note}

Score each dimension:
1. **Completeness** (1-5): Does the note capture all clinically relevant information from the dialogue?
2. **Accuracy** (1-5): Is every statement in the note factually grounded in the dialogue? No hallucinations?
3. **Organization** (1-5): Is the note well-structured with information in the correct SOAP sections?
4. **Clinical Language** (1-5): Does the note use appropriate medical terminology and professional tone?
5. **Actionability** (1-5): Is the plan section specific, actionable, and clinically sound?

Return JSON:
{{"completeness": int, "accuracy": int, "organization": int, "clinical_language": int, "actionability": int, "total": int, "reasoning": "Brief explanation of scores"}}

# ENTITY_EXTRACTION_PROMPT

You are a medical NLP system. Extract all medical entities from the text below. Include: medications, diagnoses, symptoms, procedures, lab tests, vital signs, anatomical terms, and medical devices.

TEXT:
{text}

Return JSON:
{{"entities": ["entity1", "entity2", ...]}}

Rules:
- Normalize to lowercase.
- Use generic drug names when possible (e.g., "acetaminophen" not "Tylenol").
- Include dosages as part of the entity only if mentioned (e.g., "metformin 500mg").
- Remove duplicates.
- Sort alphabetically.

# ACI_NOTE_PROMPT

You are a medical openattend. Given a doctor-patient dialogue, generate a clinical note with exactly four sections matching the ACI-Bench format.

DIALOGUE:
{transcript}

Return JSON with this exact structure:
{{"history_of_present_illness": "Detailed HPI based on the dialogue", "physical_examination": "Physical exam findings mentioned in the dialogue", "results": "Lab results, imaging, or test results discussed", "assessment_and_plan": "Clinical assessment and treatment plan"}}

Rules:
- ONLY include information explicitly stated in the dialogue.
- Use standard clinical documentation style.
- If a section has no relevant information, write "Not documented."
- Do NOT fabricate findings not discussed in the dialogue.
- NEVER infer or generate:
  - Vital signs not read aloud in the conversation
  - Lab values or imaging results not discussed
  - Physical exam findings not verbally described by the physician
  - Medications not explicitly mentioned by name
- If the physician performed an exam but did not verbalize findings, write "Exam performed, findings not documented in conversation."
- NEVER add "denies" statements unless the patient explicitly denied a symptom when asked.
- When uncertain whether something was stated vs. implied, omit it.
