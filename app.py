import os
import uuid
import logging
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, abort, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from docx import Document
from docx.shared import Pt
import mimetypes

# ----- Paths (Render-safe) -----
# Use /tmp on Render (ephemeral but writable). Falls back to project dir if running locally.
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_FOLDER", "/tmp/uploads"))
RESULTS_DIR = Path(os.getenv("RESULTS_FOLDER", "/tmp/results"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ----- Logging -----
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("resume-enhancer")

# ----- App -----
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["RESULTS_FOLDER"] = str(RESULTS_DIR)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB

# Allow your GH Pages site + localhost for dev
CORS(app, resources={
    r"/*": {"origins": [
        "https://sahilchhina.github.io",
        "http://localhost:3000",
        "http://localhost:5173"
    ]}
})

@app.get("/")
def health():
    return jsonify({"ok": True}), 200

def _convert_to_pdf_via_soffice(src_docx: Path, out_dir: Path) -> Path | None:
    """Return Path to PDF if converted, otherwise None."""
    try:
        cmd = [
            "soffice", "--headless",
            "--convert-to", "pdf",
            "--outdir", str(out_dir),
            str(src_docx)
        ]
        log.info("Running: %s", " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            log.warning("soffice non-zero exit: %s\nSTDERR: %s", res.returncode, res.stderr[:400])
            return None
        pdf_path = out_dir / src_docx.with_suffix(".pdf").name
        return pdf_path if pdf_path.exists() else None
    except FileNotFoundError:
        log.warning("LibreOffice 'soffice' not found; skipping PDF conversion.")
        return None
    except Exception as e:
        log.warning("PDF conversion failed: %s", e)
        return None

@app.route("/enhance", methods=["POST", "OPTIONS"])
def enhance():
    if request.method == "OPTIONS":
        return ("", 204)

    log.info("---- /enhance hit ----")
    log.info("CT: %s", request.content_type)
    log.info("Files: %s", list(request.files.keys()))
    log.info("Form:  %s", list(request.form.keys()))

    # Accept common key variants
    file = (request.files.get("resume")
            or request.files.get("file")
            or request.files.get("upload"))
    jd = (request.form.get("jobDescription")
          or request.form.get("job_description")
          or request.form.get("jobdescription")
          or request.form.get("description")
          or "").strip()

    if not file or not file.filename:
        return jsonify({"status": "error", "message": "Missing 'resume' file"}), 400
    if not jd:
        return jsonify({"status": "error", "message": "Missing or empty 'jobDescription'"}), 400

    # Save upload
    in_name = secure_filename(f"{uuid.uuid4()}.docx")
    in_path = UPLOAD_DIR / in_name
    file.save(in_path)
    log.info("Saved upload -> %s", in_path)

    # Open original & capture basic font
    try:
        original_doc = Document(str(in_path))
    except Exception as e:
        log.exception("Failed to open DOCX")
        return jsonify({"status": "error", "message": f"Failed to open DOCX: {e}"}), 500

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

    # Build a simple enhanced doc (placeholder logic)
    enhanced_doc = Document()
    run = enhanced_doc.add_paragraph().add_run("Enhanced Resume Skills:\n" + jd)
    run.font.name = font_name
    run.font.size = Pt(font_size_pt)

    # Save enhanced DOCX
    out_name = secure_filename(f"{uuid.uuid4()}_enhanced.docx")
    out_path = RESULTS_DIR / out_name
    enhanced_doc.save(str(out_path))
    log.info("Saved result DOCX -> %s", out_path)

    # Convert to PDF if possible
    pdf_path = _convert_to_pdf_via_soffice(out_path, RESULTS_DIR)
    pdf_url_abs = url_for("serve_result", fname=pdf_path.name, _external=True) if pdf_path else None

    # IMPORTANT: return **absolute** URLs so the browser hits Render, not GitHub Pages
    docx_url_abs = url_for("serve_result", fname=out_name, _external=True)

    resp = {
        "status": "success",
        "docx_url": docx_url_abs,
        "pdf_url": pdf_url_abs,
        "message": "PDF not generated on this host." if not pdf_url_abs else None
    }
    return jsonify(resp), 200

# Serve generated results
@app.route("/results/<path:fname>")
def serve_result(fname):
    fp = RESULTS_DIR / fname
    if not fp.exists():
        abort(404)
    ext = fp.suffix.lower()
    if ext == ".docx":
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        # Force download so users don’t try to render in-browser
        return send_from_directory(str(RESULTS_DIR), fname, as_attachment=True, mimetype=mimetype)
    elif ext == ".pdf":
        return send_from_directory(str(RESULTS_DIR), fname, as_attachment=False, mimetype="application/pdf")
    else:
        return send_from_directory(str(RESULTS_DIR), fname, as_attachment=True)

# Optional: explicit uploads serving (mainly for debugging)
@app.route("/uploads/<path:fname>")
def serve_upload(fname):
    fp = UPLOAD_DIR / fname
    if not fp.exists():
        abort(404)
    mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return send_from_directory(str(UPLOAD_DIR), fname, as_attachment=True, mimetype=mimetype)

# Graceful "preview" endpoint so frontend doesn't 404
@app.get("/preview")
def preview_disabled():
    return jsonify({"status": "disabled", "message": "PDF preview is disabled on this deployment."}), 501

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
