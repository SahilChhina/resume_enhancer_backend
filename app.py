import os
import json
import boto3
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from docx import Document
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
# from docx2pdf import convert  # ❌ Not supported on Render Linux servers

# Load AWS credentials
load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Bedrock client
bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-1",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

@app.route("/", methods=["GET"])
def home():
    return "✅ AI Resume Enhancer API is running!"

@app.route("/enhance", methods=["POST"])
def enhance_resume():
    try:
        resume_file = request.files.get("resume")
        job_description = request.form.get("job_description")

        print("✅ Resume file:", resume_file)
        print("✅ Job description:", job_description)

        if not resume_file or not job_description:
            return jsonify({"error": "Missing resume file or job description."}), 400

        filename = secure_filename(resume_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        resume_file.save(filepath)

        doc = Document(filepath)
        paragraphs = list(doc.paragraphs)

        skills_start = None
        skills_end = None

        for i, para in enumerate(paragraphs):
            if 'skills' in para.text.lower():
                skills_start = i
                break

        if skills_start is None:
            return jsonify({"error": "Couldn't find a 'Skills' section in the resume."}), 400

        for j in range(skills_start + 1, len(paragraphs)):
            if paragraphs[j].text.strip().isupper():
                skills_end = j
                break
        else:
            skills_end = len(paragraphs)

        original_para = doc.paragraphs[skills_start + 1]
        original_text = original_para.text.strip()

        prompt = f"""You are a resume optimization assistant.

Here is the original 'Skills' section of a resume:
---
{original_text}
---

And here is the job description:
---
{job_description}
---

Identify new skills that align with the job posting but are not already listed. Return only the new skills, formatted as a comma-separated list. Do not repeat existing skills. Do not include commentary or explanation.
"""

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 300,
            "temperature": 0.3
        })

        response = bedrock.invoke_model(
            body=body,
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            contentType="application/json",
            accept="application/json"
        )

        result = json.loads(response["body"].read())
        print("🧠 Claude response:", result)

        enhanced_skills_text = result["content"][0]["text"].strip().rstrip(",")

        combined_text = original_text.rstrip(",") + ", " + enhanced_skills_text.lstrip(", ")
        original_para.text = combined_text

        for run in original_para.runs:
            run.font.size = original_para.runs[0].font.size
            run.font.name = original_para.runs[0].font.name

        docx_path = os.path.join(app.config['UPLOAD_FOLDER'], "enhanced_resume.docx")
        doc.save(docx_path)

        # ❌ Commented out since Render won't support docx2pdf
        # pdf_path = docx_path.replace(".docx", ".pdf")
        # convert(docx_path, pdf_path)

        return send_file(docx_path, as_attachment=True)

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/preview", methods=["GET"])
def preview_resume():
    # Since PDF conversion is disabled, just serve the .docx if needed
    docx_path = os.path.join(app.config['UPLOAD_FOLDER'], "enhanced_resume.docx")
    if os.path.exists(docx_path):
        return send_file(docx_path)
    return jsonify({"error": "Enhanced resume not found."}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
