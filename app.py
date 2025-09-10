import os
import uuid
import logging
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_file, abort, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from docx import Document
from docx.shared import Pt

# ---------- Paths (Render-safe) ----------
UPLOAD_DIR = Path(os.getenv("UPLOAD_FOLDER", "/tmp/uploads"))
RESULTS_DIR = Path(os.getenv("RESULTS_FOLDER", "/tmp/results"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------- App ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("resume-enhancer")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB

# Allow your GH Pages + localhost dev
CORS(app, resources={r"/*": {"origins": [
    "https://sahilchhina.github.io",
    "http://localhost:3000",
    "http://localhost:5173"
]}})

@app.get("/")
def health():
    return jsonify({"ok": True}), 200

@app.get("/ls")
def list_results():
    # Debug endpoint: list files & sizes on server
    items = []
    for p in sorted(RESULTS_DIR.glob("*")):
        items.append({"name": p.name, "bytes": p.stat().st_size})
    return jsonify({"results": items}), 200

def _convert_to_pdf_via_soffice(src_docx: Path, out_dir: Path) -> Path | None:
    """Convert DOCX -> PDF using LibreOffice; return PDF path or None."""
    try:
        cmd = [
            "soffice", "--headless",
            "--convert-to", "pdf",
            "--outdir", str(out_dir),
            str(src_docx)
        ]
        log.info("Running: %s", " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            log.warning("soffice exit=%s stderr=%s", res.returncode, res.stderr[:400])
            return None
        pdf_path = out_dir / (src_docx.stem + ".pdf")
        return pdf_path if pdf_path.exists() else None
    except FileNotFoundError:
        log.warning("LibreOffice not found.")
        return None
    except Exception as e:
        log.warning("PDF conversion failed: %s", e)
        return None

@app.route("/enhance", methods=["POST", "OPTIONS"])
def enhance():
    if request.method == "OPTIONS":
        return ("", 204)

    # Accept common key variants
    file = request.files.get("resume") or request.files.get("file") or request.files.get("upload")
    jd = (request.form.get("jobDescription")
          or request.form.get("job_description")
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
    log.info("Saved upload -> %s (%d bytes)", in_path, in_path.stat().st_size)

    # Open original to pick up font
    try:
        original_doc = Document(str(in_path))
    except Exception as e:
        log.exception("Failed to open uploaded DOCX")
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

    # Build enhanced doc (placeholder)
    enhanced = Document()
    r = enhanced.add_paragraph().add_run("Enhanced Resume Skills:\n" + jd)
    r.font.name = font_name
    r.font.size = Pt(font_size_pt)

    out_name = secure_filename(f"{uuid.uuid4()}_enhanced.docx")
    out_path = RESULTS_DIR / out_name
    enhanced.save(str(out_path))
    log.info("Saved result DOCX -> %s (%d bytes)", out_path, out_path.stat().st_size)

    # Try PDF
    pdf_path = _convert_to_pdf_via_soffice(out_path, RESULTS_DIR)
    pdf_url = url_for("serve_result", fname=pdf_path.name, _external=True) if pdf_path else None

    # Absolute URL for docx
    docx_url = url_for("serve_result", fname=out_name, _external=True)

    return jsonify({
        "status": "success",
        "docx_url": docx_url,
        "pdf_url": pdf_url,
        "message": None if pdf_url else "PDF preview disabled on this deployment."
    }), 200

@app.get("/results/<path:fname>")
def serve_result(fname):
    fp = RESULTS_DIR / fname
    if not fp.exists():
        abort(404)

    # For DOCX: force download with correct headers; for PDF: inline
    if fp.suffix.lower() == ".docx":
        return send_file(
            fp,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=fname
        )
    if fp.suffix.lower() == ".pdf":
        return send_file(fp, mimetype="application/pdf", as_attachment=False)
    # Fallback
    return send_file(fp, as_attachment=True, download_name=fname)

@app.get("/preview")
def preview_disabled():
    # kept to avoid 404s from old frontends; real preview happens via pdf_url
    return jsonify({"status": "disabled", "message": "Use pdf_url returned by /enhance."}), 501

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
