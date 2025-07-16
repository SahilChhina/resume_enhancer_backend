from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from docx import Document
from docx.shared import Pt
from docx2pdf import convert
import os
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'static'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def home():
    return '✅ AI Resume Enhancer API is running!'

@app.route('/enhance', methods=['POST'])
def enhance_resume():
    if 'resume' not in request.files or 'jobDescription' not in request.form:
        return jsonify({"status": "error", "message": "Missing file or job description"}), 400

    resume = request.files['resume']
    job_description = request.form['jobDescription']
    filename = secure_filename(resume.filename)
    original_docx_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
    resume.save(original_docx_path)

    doc = Document(original_docx_path)

    # Format matching setup
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(11)

    # Append AI-enhanced content
    doc.add_paragraph("\nAI-Generated Enhancement Based on Job Description:\n", style='Normal')
    doc.add_paragraph(job_description, style='Normal')

    enhanced_docx_filename = 'enhanced_resume.docx'
    enhanced_docx_path = os.path.join(app.config['UPLOAD_FOLDER'], enhanced_docx_filename)
    doc.save(enhanced_docx_path)

    enhanced_pdf_filename = 'enhanced_resume.pdf'
    enhanced_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], enhanced_pdf_filename)
    convert(enhanced_docx_path, enhanced_pdf_path)

    return jsonify({
        "status": "success",
        "docx_url": f"/static/{enhanced_docx_filename}",
        "pdf_url": f"/static/{enhanced_pdf_filename}"
    })

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
