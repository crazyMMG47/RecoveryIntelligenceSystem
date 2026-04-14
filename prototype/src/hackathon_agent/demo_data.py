from .schemas import CaseData


DEMO_CASE = CaseData(
    case_id="CASE_003",
    patient_summary=(
        "Daniel Lee is a 30-year-old male with persistent right knee instability "
        "and pain 8 months after revision ACL reconstruction. He wants to return "
        "to recreational basketball and normal daily function."
    ),
    clinical_notes=[
        "First ACL reconstruction was 2.5 years ago at Kaiser San Diego.",
        "Revision ACL reconstruction was 8 months ago at Kaiser San Jose.",
        "Current symptoms include pain with pivoting, stairs, and activity.",
        "Exam shows mild laxity, quadriceps weakness, and poor neuromuscular control.",
        "Current presentation is more consistent with incomplete rehabilitation than acute structural failure.",
    ],
    pt_notes=[
        "First surgery rehab lasted about 10 weeks but return-to-sport phase was not completed.",
        "Second surgery rehab lasted only 4 to 5 weeks and focused on pain control and mobility.",
        "No documented structured strengthening or neuromuscular progression after revision surgery.",
        "Current PT findings include significant quadriceps weakness, poor neuromuscular control, and fear of re-injury.",
    ],
    imaging=[
        "MRI shows intact ACL graft with mild stretching.",
        "MRI shows mild joint effusion and early cartilage degeneration.",
        "MRI shows no acute tear or displaced hardware complication.",
    ],
    policy_text=[
        "Standard PT coverage is 1 session per week without additional approval.",
        "Two sessions per week requires physician justification and utilization review.",
        "Extended PT requests should document measurable functional deficits and a clear therapy plan.",
        "Approval is stronger when the patient has not completed an appropriate structured rehabilitation course.",
        "Patient adherence history may be reviewed during approval decisions.",
    ],
)
