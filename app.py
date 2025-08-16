import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from docx import Document
from docx.shared import Pt

# --------- Folders ----------
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# --------- App ----------
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["RESULTS_FOLDER"] = RESULTS_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB cap

# Allow your GH Pages site and localhost dev
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://sahilchhina.github.io",
            "http://localhost:3000"
        ]
    }
})

# --------- Health ----------
@app.get("/")
def health():
    return jsonify({"ok": True}), 200


# --------- Enhance ----------
@app.route("/enhance", methods=["POST"])
def enhance():
    # Basic validation
    if "resume" not in request.files or "jobDescription" not in request.form:
        return jsonify({"status": "error", "message": "Missing resume or jobDescription"}), 400

    resume = request.files["resume"]
    job_desc = request.form.get("jobDescription", "").strip()

    if resume.filename == "":
        return jsonify({"status": "error", "message": "No selected file"}), 400
    if not job_desc:
        return jsonify({"status": "error", "message": "Job description is empty"}), 400

    # Save uploaded resume
    resume_filename = secure_filename(f"{uuid.uuid4()}.docx")
    resume_path = os.path.join(app.config["UPLOAD_FOLDER"], resume_filename)
    resume.save(resume_path)

    # Read original resume with defensive checks
    try:
        original_doc = Document(resume_path)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to open DOCX: {e}"}), 500

    # Try to borrow font styling from the first run if present
    font_name = "Times New Roman"
    font_size_pt = 11
    try:
        if original_doc.paragraphs:
            p0 = original_doc.paragraphs[0]
            if p0.runs:
                r0 = p0.runs[0]
                if r0.font.name:
                    font_name = r0.font.name
                if r0.font.size:
                    font_size_pt = int(r0.font.size.pt)
    except Exception:
        pass  # fall back to defaults

    # Create a simple "enhanced" document (placeholder logic)
    enhanced_doc = Document()
    p = enhanced_doc.add_paragraph()
    run = p.add_run("Enhanced Resume Skills:\n" + job_desc)
    run.font.name = font_name
    run.font.size = Pt(font_size_pt)

    # Save enhanced DOCX
    enhanced_docx_filename = secure_filename(f"{uuid.uuid4()}_enhanced.docx")
    enhanced_docx_path = os.path.join(app.config["RESULTS_FOLDER"], enhanced_docx_filename)
    enhanced_doc.save(enhanced_docx_path)

    # Try PDF conversion (will fail on Linux/Render without LibreOffice)
    pdf_url = None
    try:
        # Optional: attempt conversion if docx2pdf is available & supported
        from docx2pdf import convert  # noqa: E402
        enhanced_pdf_path = enhanced_docx_path.replace(".docx", ".pdf")
        convert(enhanced_docx_path, enhanced_pdf_path)
        if os.path.exists(enhanced_pdf_path):
            pdf_url = f"/results/{os.path.basename(enhanced_pdf_path)}"
    except Exception as e:
        # On Render (Linux), docx2pdf typically fails — we proceed without PDF
        print(f"[warn] PDF conversion failed: {e}")

    response = {
        "status": "success",
        "docx_url": f"/results/{enhanced_docx_filename}",
    }
    if pdf_url:
        response["pdf_url"] = pdf_url
    else:
        response["message"] = "PDF preview unavailable on this host. Download the DOCX instead."

    return jsonify(response), 200


# --------- Static file serving ----------
@app.route("/results/<path:filename>")
def download_result(filename):
    return send_from_directory(app.config["RESULTS_FOLDER"], filename, as_attachment=False)


@app.route("/uploads/<path:filename>")
def download_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)


# --------- Entrypoint ----------
if __name__ == "__main__":
    # Render provides PORT; default to 10000 for local dev
    port = int(os.environ.get("PORT", "10000"))
    # Bind to 0.0.0.0 so Render can expose it publicly
    app.run(host="0.0.0.0", port=port, debug=False)
