import os
import uuid
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from docx import Document
from docx.shared import Pt

# --------- Logging ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("resume-enhancer")

# --------- Folders ----------
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# --------- App ----------
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["RESULTS_FOLDER"] = RESULTS_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB

CORS(app, resources={r"/*": {"origins": ["https://sahilchhina.github.io", "http://localhost:3000"]}})

# --------- Health ----------
@app.get("/")
def health():
    return jsonify({"ok": True}), 200

# --------- Enhance ----------
@app.route("/enhance", methods=["POST", "OPTIONS"])
def enhance():
    if request.method == "OPTIONS":
        return ("", 204)

    log.info("---- /enhance hit ----")
    log.info("Content-Type: %s", request.content_type)
    log.info("Content-Length: %s", request.content_length)
    log.info("Files keys: %s", list(request.files.keys()))
    log.info("Form keys:  %s", list(request.form.keys()))

    # Accept common variants for both fields
    file = (
        request.files.get("resume")
        or request.files.get("file")
        or request.files.get("upload")
    )
    jd = (
        request.form.get("jobDescription")
        or request.form.get("job_description")
        or request.form.get("jobdescription")
        or request.form.get("description")
        or ""
    ).strip()

    if not file:
        msg = "Missing 'resume' file in form-data (key: resume)"
        log.warning(msg)
        return jsonify({"status": "error", "message": msg}), 400

    if not file.filename:
        msg = "No selected file"
        log.warning(msg)
        return jsonify({"status": "error", "message": msg}), 400

    if not jd:
        msg = "Missing or empty job description (expected 'jobDescription')"
        log.warning(msg)
        return jsonify({"status": "error", "message": msg}), 400

    # Save upload
    resume_filename = secure_filename(f"{uuid.uuid4()}.docx")
    resume_path = os.path.join(app.config["UPLOAD_FOLDER"], resume_filename)
    file.save(resume_path)
    log.info("Saved upload -> %s", resume_path)

    # Read original resume
    try:
        original_doc = Document(resume_path)
    except Exception as e:
        log.exception("Failed to open DOCX")
        return jsonify({"status": "error", "message": f"Failed to open DOCX: {e}"}), 500

    # Borrow font if present
    font_name = "Times New Roman"
    font_size_pt = 11
    try:
        if original_doc.paragraphs and original_doc.paragraphs[0].runs:
            r0 = original_doc.paragraphs[0].runs[0]
            if r0.font.name:
                font_name = r0.font.name
            if r0.font.size:
                font_size_pt = int(r0.font.size.pt)
    except Exception:
        pass

    # Make simple enhanced doc
    enhanced_doc = Document()
    run = enhanced_doc.add_paragraph().add_run("Enhanced Resume Skills:\n" + jd)
    run.font.name = font_name
    run.font.size = Pt(font_size_pt)

    # Save result
    enhanced_docx_filename = secure_filename(f"{uuid.uuid4()}_enhanced.docx")
    enhanced_docx_path = os.path.join(app.config["RESULTS_FOLDER"], enhanced_docx_filename)
    enhanced_doc.save(enhanced_docx_path)
    log.info("Saved result DOCX -> %s", enhanced_docx_path)

    # Return JSON (skip PDF on Linux)
    resp = {
        "status": "success",
        "docx_url": f"/results/{enhanced_docx_filename}",
        "message": "PDF not generated on this host; download DOCX instead."
    }
    log.info("Success -> %s", resp)
    return jsonify(resp), 200

# --------- Static files ----------
@app.route("/results/<path:filename>")
def download_result(filename):
    return send_from_directory(app.config["RESULTS_FOLDER"], filename, as_attachment=False)

@app.route("/uploads/<path:filename>")
def download_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)

# --------- Entrypoint ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
