from flask import Flask, render_template, request, send_file, flash, redirect, url_for, make_response
import fitz  # PyMuPDF
import re
import os
import tempfile
import zipfile
import io
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Change this!

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "files" not in request.files:
            flash("No files selected")
            return redirect(request.url)
        files = request.files.getlist("files")
        if not files or all(file.filename == "" for file in files):
            flash("No files selected")
            return redirect(request.url)

        # Validate all files are PDFs
        for file in files:
            if not file.filename.endswith(".pdf"):
                flash(f"File {file.filename} is not a PDF")
                return redirect(request.url)

        try:
            # Create a ZIP file in memory to store all annotated PDFs
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for file in files:
                    # Read the uploaded file
                    input_pdf = file.read()

                    # Create temporary input file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_in:
                        temp_in.write(input_pdf)
                        temp_in_path = temp_in.name

                    # Create a unique temporary output file
                    temp_out_fd, temp_out_path = tempfile.mkstemp(suffix=".pdf")
                    os.close(temp_out_fd)

                    # Process the PDF
                    annotate_pdf_with_links(temp_in_path, temp_out_path)

                    # Get the original filename and prepend 'annotated_'
                    original_filename = os.path.splitext(file.filename)[0]  # Remove extension
                    zip_filename = f"annotated_{original_filename}.pdf"

                    # Add the processed file to the ZIP with the new filename
                    zip_file.write(temp_out_path, zip_filename)

                    # Clean up temporary files
                    if os.path.exists(temp_in_path):
                        os.unlink(temp_in_path)
                    if os.path.exists(temp_out_path):
                        os.unlink(temp_out_path)

            # Send the ZIP file to the user
            zip_buffer.seek(0)
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name="annotated_files.zip",
                mimetype="application/zip"
            )

        except Exception as e:
            flash(f"Error: {str(e)}")
            return redirect(request.url)

    return render_template("index.html")

def annotate_pdf_with_links(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    url_pattern = re.compile(
        r'(?:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|'  # Emails
        r'(?:https?://|www\.)[^\s]+)',                        # HTTP/HTTPS or www
        re.IGNORECASE
    )
    all_links = []
    for page in doc:
        # Collect explicit links
        links = page.get_links()
        for link in links:
            if "uri" in link:
                rect = fitz.Rect(link["from"])
                all_links.append({"page": page, "rect": rect, "url": link["uri"], "type": "explicit"})

        # Collect plain text URLs
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"]
                        matches = list(url_pattern.finditer(text))
                        if not matches:
                            continue
                        char_width = (span["bbox"][2] - span["bbox"][0]) / len(text) if len(text) > 0 else 0
                        for match in matches:
                            url = match.group()
                            start_idx = match.start()
                            end_idx = match.end()
                            url_x0 = span["bbox"][0] + start_idx * char_width
                            url_x1 = span["bbox"][0] + end_idx * char_width
                            url_y0 = span["bbox"][1]
                            url_y1 = span["bbox"][3]
                            url_rect = fitz.Rect(url_x0, url_y0, url_x1, url_y1)
                            all_links.append({"page": page, "rect": url_rect, "url": url, "type": "plain"})

    # Draw red boxes and textboxes with arrows
    for link_info in all_links:
        page = link_info["page"]
        rect = link_info["rect"]
        url = link_info["url"]
        page.draw_rect(rect, color=(1, 0, 0), width=1)
        x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
        textbox_x0, textbox_y0, textbox_x1, textbox_y1 = x1 + 10, y0, x1 + 250, y0 + 20
        if textbox_x1 > page.rect.width:
            textbox_x0, textbox_y0, textbox_x1, textbox_y1 = x0, y1 + 10, x0 + 250, y1 + 30
        textbox_rect = fitz.Rect(textbox_x0, textbox_y0, textbox_x1, textbox_y1)
        page.insert_textbox(textbox_rect, url, fontsize=8, color=(0, 0, 0), fill=(1, 0, 0), align=0)
        start = (x1, (y0 + y1) / 2) if textbox_x0 > x1 else ((x0 + x1) / 2, y1)
        end = (textbox_x0, (textbox_y0 + textbox_y1) / 2) if textbox_x0 > x1 else ((textbox_x0 + textbox_x1) / 2, textbox_y0)
        page.draw_line(start, end, color=(1, 0, 0), width=0.5)

    doc.save(output_pdf)
    doc.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
