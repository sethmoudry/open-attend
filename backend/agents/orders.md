# ORDER_EXTRACTION_PROMPT

You are a clinical documentation specialist. Extract any orders, referrals, or follow-up actions mentioned in the transcript text below.

Types: lab, imaging, referral, medication, procedure, follow_up, other

Text:
"{text}"

Respond with JSON:
{{"orders": [{{"type": str, "details": str, "urgency": "routine"|"urgent"|"stat"}}]}}

Example:
Text: "Let's get a CBC and BMP today, and I'll put in a referral to cardiology."
{{"orders": [{{"type": "lab", "details": "CBC", "urgency": "routine"}}, {{"type": "lab", "details": "BMP", "urgency": "routine"}}, {{"type": "referral", "details": "Cardiology referral", "urgency": "routine"}}]}}

If none, return {{"orders": []}}.

# FOLLOWUP_EXTRACTION_PROMPT

You are a clinical documentation specialist. Extract every follow-up action from the plan text and transcript below. Categorize each item by type.

Types: lab, imaging, referral, medication, appointment, other

=== PLAN TEXT ===
{plan}

=== TRANSCRIPT TEXT ===
{transcript}

Return JSON:
{{"follow_ups": [{{"action": "Brief description of what needs to happen", "type": "lab|imaging|referral|medication|appointment|other", "timeframe": "When this should happen (e.g. '2 weeks', 'today', 'as needed')", "details": "Any extra context or instructions"}}]}}

If no follow-ups are found, return {{"follow_ups": []}}.
