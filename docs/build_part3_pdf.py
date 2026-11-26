"""Generate Part 3 Sinhala Guidance Booklet PDF using ReportLab + Nirmala UI."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT_PDF = Path(__file__).resolve().parent / "Agentic_AI_Booklet_Part3_Sinhala.pdf"

pdfmetrics.registerFont(TTFont("Nirmala", r"C:\Windows\Fonts\Nirmala.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("NirmalaBold", r"C:\Windows\Fonts\Nirmala.ttc", subfontIndex=1))


def build_pdf():
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title_s = ParagraphStyle("SiTitle", parent=styles["Title"], fontName="NirmalaBold", fontSize=17, leading=23, textColor=colors.HexColor("#0f172a"))
    h2_s = ParagraphStyle("SiH2", parent=styles["Heading2"], fontName="NirmalaBold", fontSize=12.5, leading=18, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#1e3a8a"))
    h3_s = ParagraphStyle("SiH3", parent=styles["Heading3"], fontName="NirmalaBold", fontSize=10.5, leading=15, spaceBefore=7, spaceAfter=3, textColor=colors.HexColor("#1e40af"))
    body_s = ParagraphStyle("SiBody", parent=styles["Normal"], fontName="Nirmala", fontSize=9.8, leading=15.5, spaceAfter=5, textColor=colors.HexColor("#1e293b"))
    code_s = ParagraphStyle("SiCode", parent=styles["Code"], fontName="Courier", fontSize=8.2, leading=11.5, backColor=colors.HexColor("#f1f5f9"), borderPadding=6, spaceAfter=6)

    story = []
    story.append(Paragraph("Governed Autonomous Invoice-to-PO Agent — කොටස 3 (2026 Enterprise Upgrade)", title_s))
    story.append(Paragraph("<b>ඉලක්කය:</b> Toy Project මට්ටමෙන් ඔබ්බට ගොස් සමාගම් හිමිකරුට සැබෑ මූල්‍ය ප්‍රතිලාභ (ROI) සහ Chief AI Engineer හට 2026 Production AI Engineering කුසලතා ඔප්පු කිරීම. (වියදම: $0 | කාලය: පැය 3)", body_s))
    story.append(Spacer(1, 6))

    story.append(Paragraph("1. Part 1 සහ Part 2 'Toy Project' එකක් ලෙස දැනෙන්නේ ඇයි?", h2_s))
    story.append(Paragraph("• <b>Cross-Thread Episodic Memory නොමැති වීම:</b> මූල්‍ය නිලධාරියා HITL හරහා approve/reject කළ තීරණ agent මතක තබා නොගත්තේය. ඊළඟ සමාන invoice එකේදී නැවත මුල සිට escalate විය.", body_s))
    story.append(Paragraph("• <b>Brittle Exact String Matching:</b> PO එකේ 'Centrifugal Pump' සහ Invoice එකේ 'Industrial Centrifugal Pump 5HP' ලෙස තිබුණහොත් හෝ line order වෙනස් වුවහොත් LINE_DESC_MISMATCH ලෙස අසමත් විය.", body_s))
    story.append(Paragraph("• <b>Regex-only ආරක්ෂාව සහ Business ROI නොමැති වීම:</b> sanitize.py හි සරල regex පමණක් තිබූ අතර, සමාගමට ඉතිරි වූ මුදල ($) පෙන්වන KPIs නොතිබුණි.", body_s))
    story.append(Paragraph("• <b>2026 සම්මතය:</b> පැරණි 2024–2025 patterns (AgentExecutor, ConversationBufferMemory, naive RetrievalQA) ඉවත් කර 2026 Neuro-Symbolic Policy + Embedded Vector Memory (sqlite-vec) + Pre-trained Guardrail Classifier භාවිතා කර ඇත.", body_s))

    story.append(Paragraph("2. External Tools, Hugging Face Models සහ Fine-Tuning තීරණය", h2_s))
    tbl_data = [
        ["තීරණය", "නිර්දේශය (100% Free)", "Senior AI Engineer හේතු දැක්වීම"],
        ["External Tools", "Groq / Gemini Free Tier + HF Inference API + sqlite-vec", "Local sqlite-vec නිසා Pinecone/Weaviate වැනි ගෙවන vector DB අවශ්‍ය නොවේ."],
        ["Hugging Face Models", "protectai/deberta-v3-base-prompt-injection-v2\nBAAI/bge-small-en-v1.5", "DeBERTa Guardrail model මගින් prompt injection හඳුනාගනී; BGE-small මගින් semantic matching කරයි."],
        ["Fine-Tuning (පැය 3)?", "එපා (DO NOT Fine-Tune)", "පැය 3කින් LoRA fine-tuning කිරීමෙන් overfitting සහ tool-calling බිඳ වැටීම සිදුවේ. Episodic Memory + Structured Output ඊට වඩා නිවැරදියි."],
    ]
    t = Table(tbl_data, colWidths=[34 * mm, 58 * mm, 84 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "NirmalaBold"),
        ("FONTNAME", (0, 1), (-1, -1), "Nirmala"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))

    story.append(Paragraph("3. විශේෂාංගය 1: sqlite-vec Episodic HITL Memory & Semantic Line-Item Matching", h2_s))
    story.append(Paragraph("• <b>Semantic Line Alignment (backend/app/agent/policy.py):</b> align_lines() මගින් 384-dim embeddings cosine similarity භාවිතයෙන් invoice lines සහ PO lines order-independent ලෙස ගළපයි.", body_s))
    story.append(Paragraph("• <b>Episodic HITL Memory (backend/app/agent/memory.py, runtime.py, graph.py):</b> මූල්‍ය නිලධාරියා approve/reject කරන සෑම තීරණයක්ම sqlite-vec (memory.sqlite) හි සුරැකේ. නව invoice එකේදී top-3 precedents recall කර CaseReview UI හි පෙන්වයි.", body_s))

    story.append(Paragraph("4. විශේෂාංගය 2: Hugging Face Guardrail Classifier & Business ROI Telemetry", h2_s))
    story.append(Paragraph("• <b>Defense-in-Depth Guardrail (backend/app/mcp_server/guardrail.py, sanitize.py):</b> Structural jailbreak scorer + Hugging Face DeBERTa prompt-injection classifier මගින් indirect injections හඳුනාගෙන MCP _meta.securityFindings වෙත යවයි.", body_s))
    story.append(Paragraph("• <b>Business ROI Engine (backend/app/api/routes.py -> /api/roi & Observability.tsx):</b> Manual benchmark ($15/invoice) vs AI cost, Prevented Leakage ($), Hours Saved, සහ HITL Precedents Learned සජීවීව පෙන්වයි.", body_s))

    story.append(Paragraph("5. යාවත්කාලීන කළ ගොනු ස්ථාන (Updated File Locations)", h2_s))
    files_data = [
        ["ගොනුව (File Path)", "කාර්යභාරය"],
        ["backend/app/agent/memory.py", "sqlite-vec Episodic HITL Memory & HF/local embeddings"],
        ["backend/app/agent/policy.py", "Order-independent align_lines() semantic 3-way match"],
        ["backend/app/agent/graph.py & runtime.py", "Precedent recall & HITL precedent recording"],
        ["backend/app/mcp_server/guardrail.py & sanitize.py", "Hybrid HF DeBERTa + structural prompt-injection guardrail"],
        ["backend/app/api/routes.py & Observability.tsx", "GET /api/roi endpoint & Business ROI KPI cards"],
        ["backend/tests/test_part3.py & plan.md", "Part 3 Pytest 5ක් සහ අදියර 9 යාවත්කාලීන සැලැස්ම"],
    ]
    tf = Table(files_data, colWidths=[78 * mm, 98 * mm])
    tf.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "NirmalaBold"),
        ("FONTNAME", (0, 1), (-1, -1), "Nirmala"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tf)
    story.append(Spacer(1, 6))

    story.append(Paragraph("6. පරීක්ෂා කිරීම සහ සම්මුඛ පරීක්ෂණ Demo උපදෙස්", h2_s))
    story.append(Paragraph(
        "cd backend<br/>$env:LLM_PROVIDER='fake'; $env:GUARDRAIL_MODE='local'; $env:EMBEDDING_PROVIDER='local'<br/>"
        "..\\.venv\\Scripts\\python.exe -m pytest tests\\test_part3.py -v",
        code_s,
    ))
    story.append(Paragraph("<b>Chief AI Engineer හට:</b> Brittle string matching වෙනුවට sqlite-vec semantic alignment + episodic HITL memory සහ MCP layer හි HF DeBERTa prompt-injection guardrail පෙන්වන්න.", body_s))
    story.append(Paragraph("<b>Company Owner හට:</b> Observability -> Business ROI කොටසේ Total Business Value ($), Prevented Leakage ($), සහ Hours Saved පෙන්වන්න.", body_s))

    doc.build(story)
    print(f"Created {OUT_PDF}")


if __name__ == "__main__":
    build_pdf()
