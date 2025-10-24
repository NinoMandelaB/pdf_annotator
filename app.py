# app.py
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import fitz  # PyMuPDF
import re
import os
import tempfile
import zipfile
import io
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Change this in production!

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

        # Validate HTML files
        for file in files:
            if not (file.filename.endswith(".html") or file.filename.endswith(".htm")):
                flash(f"File {file.filename} is not an HTML file")
                return redirect(request.url)

        try:
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for file in files:
                    html_content = file.read().decode('utf-8')

                    # Create temporary output file
                    temp_out_fd, temp_out_path = tempfile.mkstemp(suffix=".pdf")
                    os.close(temp_out_fd)

                    # Process HTML to PDF
                    process_html_to_annotated_pdf(html_content, temp_out_path)

                    # Add to ZIP
                    original_filename = os.path.splitext(file.filename)[0]
                    zip_filename = f"annotated_{original_filename}.pdf"
                    zip_file.write(temp_out_path, zip_filename)

                    # Clean up
                    if os.path.exists(temp_out_path):
                        os.unlink(temp_out_path)

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

def process_html_to_annotated_pdf(html_content, output_pdf_path):
    """Process HTML and create annotated PDF with links and tags highlighted."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Create PDF document
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)  # A4 size

    # Add margin for annotations
    margin_width = 150
    page.set_mediabox(fitz.Rect(0, 0, 842 + margin_width, 595))
    page.set_cropbox(fitz.Rect(0, 0, 842 + margin_width, 595))

    # Insert HTML content as text
    page.insert_textbox(
        fitz.Rect(50, 50, 842 - 50, 595 - 50),
        soup.get_text(),
        fontsize=12,
        color=(0, 0, 0),
        align=0
    )

    # Find all links and tags
    all_elements = []

    # Find links
    for a_tag in soup.find_all('a'):
        if a_tag.has_attr('href'):
            all_elements.append({
                'type': 'link',
                'text': a_tag.text.strip(),
                'url': a_tag['href']
            })

    # Find other tags (customize as needed)
    for tag in soup.find_all():
        if tag.name not in ['a', 'html', 'head', 'body', 'meta', 'script', 'style']:
            all_elements.append({
                'type': 'tag',
                'tag_name': tag.name,
                'text': tag.text.strip()
            })

    # Add annotations to margin
    y_pos = 50
    for element in all_elements:
        textbox_x0 = 842 + 10
        textbox_x1 = 842 + margin_width - 10
        textbox_y0 = y_pos

        if element['type'] == 'link':
            text = f"Link: {element['text']} → {element['url']}"
        else:
            text = f"Tag: <{element['tag_name']}>: {element['text']}"

        # Adjust font size based on text length
        fontsize = 8 if len(text) > 50 else 10
        textbox_height = max(20, 10 + (len(text) // 25) * 5)
        textbox_y1 = textbox_y0 + textbox_height

        # Create annotation textbox
        textbox_rect = fitz.Rect(textbox_x0, textbox_y0, textbox_x1, textbox_y1)
        page.insert_textbox(
            textbox_rect,
            text,
            fontsize=fontsize,
            color=(0, 0, 0),
            align=0
        )

        # Add border to annotation
        page.draw_rect(textbox_rect, color=(0.8, 0.8, 0.8), width=0.5)

        y_pos = textbox_y1 + 10

        # Create new page if needed
        if y_pos > 595 - 60:
            page.insert_textbox(
                fitz.Rect(textbox_x0, 595 - 50, textbox_x1, 595 - 30),
                "(continued on next page)...",
                fontsize=8,
                color=(0.5, 0.5, 0.5),
                align=1
            )

            page = doc.new_page(width=842 + margin_width, height=595)
            page.set_mediabox(fitz.Rect(0, 0, 842 + margin_width, 595))
            page.set_cropbox(fitz.Rect(0, 0, 842 + margin_width, 595))
            y_pos = 50

    # Save PDF
    doc.save(output_pdf_path)
    doc.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
