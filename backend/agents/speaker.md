# SPEAKER_ROLE_ASSIGNMENT_PROMPT

You are analyzing a medical conversation transcript where speakers are labeled as spk_0, spk_1, etc. Based on the content and context of their speech, determine the role of each speaker.

Common roles:
- doctor: Asks clinical questions, performs exam, orders tests, prescribes medications
- patient: Reports symptoms, answers questions about their health
- parent: Accompanies patient (pediatric visits), provides history
- nurse: Takes vitals, provides clinical info, assists doctor
- interpreter: Translates between languages

Transcript:
{labeled_exchanges}

Respond with JSON:
{{"assignments": [{{"speaker_id": "spk_0", "role": "doctor", "confidence": 0.95, "reasoning": "Asks clinical questions and orders tests"}}, {{"speaker_id": "spk_1", "role": "patient", "confidence": 0.90, "reasoning": "Reports symptoms and medical history"}}]}}
