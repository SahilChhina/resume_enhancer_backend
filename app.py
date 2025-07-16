import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from docx import Document
from docx.shared import Pt
from werkzeug.utils import secure_filename
import uuid
from docx2pdf import convert

UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["RESULTS_FOLDER"] = RESULTS_FOLDER
CORS(app)


@app.route("/")
def home():
    return "Resume Enhancer Backend is Running"


@app.route("/enhance", methods=["POST"])
def enhance():
    print("Received request")

    if 'resume' not in request.files or 'jobDescription' not in request.form:
        print("Missing file or job description")
        return jsonify({"status": "error", "message": "Missing resume or job description"}), 400

    resume = request.files["resume"]
    job_desc = request.form["jobDescription"]

    if resume.filename == "":
        return jsonify({"status": "error", "message": "No selected file"}), 400

    # Save uploaded resume
    resume_filename = secure_filename(str(uuid.uuid4()) + ".docx")
    resume_path = os.path.join(app.config["UPLOAD_FOLDER"], resume_filename)
    resume.save(resume_path)

    # Read original resume
    try:
        original_doc = Document(resume_path)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to open DOCX: {str(e)}"}), 500

    # Extract the formatting of the first paragraph
    sample_paragraph = original_doc.paragraphs[0]
    font_name = sample_paragraph.runs[0].font.name if sample_paragraph.runs else "Times New Roman"
    font_size = sample_paragraph.runs[0].font.size.pt if sample_paragraph.runs[0].font.size else 11

    # Generate enhanced resume
    enhanced_doc = Document()
    p = enhanced_doc.add_paragraph()
    run = p.add_run("Enhanced Resume Skills:\n" + job_desc.strip())
    run.font.name = font_name
    run.font.size = Pt(font_size)

    # Save enhanced docx
    enhanced_docx_filename = secure_filename(str(uuid.uuid4()) + "_enhanced.docx")
    enhanced_docx_path = os.path.join(app.config["RESULTS_FOLDER"], enhanced_docx_filename)
    enhanced_doc.save(enhanced_docx_path)

    # Convert to PDF
    enhanced_pdf_path = enhanced_docx_path.replace(".docx", ".pdf")
    try:
        convert(enhanced_docx_path, enhanced_pdf_path)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to convert to PDF: {str(e)}"}), 500

    # Return download links
    return jsonify({
        "status": "success",
        "docx_url": f"/results/{enhanced_docx_filename}",
        "pdf_url": f"/results/{os.path.basename(enhanced_pdf_path)}"
    })


@app.route("/results/<path:filename>")
def download_result(filename):
    return send_from_directory(app.config["RESULTS_FOLDER"], filename, as_attachment=False)


@app.route("/uploads/<path:filename>")
def download_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)


if __name__ == "__main__":
    app.run(debug=True, port=10000)
