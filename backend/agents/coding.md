# ICD10_EXTRACTION_PROMPT

You are a certified medical coder (CPC). Extract ICD-10-CM diagnosis codes from the assessment text below. Only return codes you are confident about (confidence > 0.5). Use the most specific code available.

Assessment:
"{assessment}"

Respond with JSON:
{{"codes": [{{"code": str, "description": str, "confidence": float}}]}}

Example 1:
Assessment: "Patient presents with unstable angina. ECG shows ST changes."
{{"codes": [{{"code": "I20.0", "description": "Unstable angina", "confidence": 0.95}}]}}

Example 2:
Assessment: "Type 2 diabetes mellitus with diabetic chronic kidney disease, stage 3. Hypertension is well controlled."
{{"codes": [{{"code": "E11.22", "description": "Type 2 diabetes mellitus with diabetic chronic kidney disease", "confidence": 0.93}}, {{"code": "N18.3", "description": "Chronic kidney disease, stage 3 (moderate)", "confidence": 0.88}}, {{"code": "I10", "description": "Essential (primary) hypertension", "confidence": 0.90}}]}}

Example 3:
Assessment: "Acute upper respiratory infection, likely viral. Rule out strep pharyngitis."
{{"codes": [{{"code": "J06.9", "description": "Acute upper respiratory infection, unspecified", "confidence": 0.85}}, {{"code": "J02.9", "description": "Acute pharyngitis, unspecified", "confidence": 0.55}}]}}

If no diagnoses can be coded, return {{"codes": []}}.

# CPT_EXTRACTION_PROMPT

You are a certified medical coder (CPC). Extract CPT procedure codes from the plan text and any pending orders below. Include E/M visit level codes, procedures, labs, and imaging. Only return codes with confidence > 0.5.

Plan:
"{plan}"

Orders:
{orders}

Respond with JSON:
{{"codes": [{{"code": str, "description": str, "confidence": float}}]}}

Example 1:
Plan: "Follow up in 2 weeks. Continue current medications. Order CBC and CMP."
Orders: lab: CBC, lab: CMP
{{"codes": [{{"code": "99214", "description": "Office visit, established patient, moderate complexity", "confidence": 0.75}}, {{"code": "85025", "description": "Complete CBC with differential", "confidence": 0.90}}, {{"code": "80053", "description": "Comprehensive metabolic panel", "confidence": 0.90}}]}}

Example 2:
Plan: "Perform skin biopsy of suspicious lesion on left forearm. Send to pathology."
Orders: procedure: skin biopsy
{{"codes": [{{"code": "11102", "description": "Tangential biopsy of skin, single lesion", "confidence": 0.85}}, {{"code": "88305", "description": "Surgical pathology, gross and microscopic examination", "confidence": 0.80}}]}}

Example 3:
Plan: "New patient evaluation for chest pain. Order chest X-ray and ECG."
Orders: imaging: chest X-ray, procedure: ECG
{{"codes": [{{"code": "99203", "description": "Office visit, new patient, low complexity", "confidence": 0.70}}, {{"code": "71046", "description": "Chest X-ray, 2 views", "confidence": 0.88}}, {{"code": "93000", "description": "Electrocardiogram, routine, 12-lead", "confidence": 0.92}}]}}

If no procedures can be coded, return {{"codes": []}}.
