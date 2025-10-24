# app.py
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import fitz  # PyMuPDF
import re
import os
import tempfile
import zipfile
import io
from bs4 import BeautifulSoup
from weasyprint import HTML

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
    # Parse the HTML content
    soup = BeautifulSoup(html_content, 'html.parser')

    # First, generate a PDF from the HTML using WeasyPrint
    temp_pdf_path = tempfile.mktemp(suffix=".pdf")
    HTML(string=str(soup)).write_pdf(temp_pdf_path)

    # Open the generated PDF with PyMuPDF
    doc = fitz.open(temp_pdf_path)

    # Add margin for annotations
    margin_width = 150
    for page in doc:
        page_rect = page.rect
        original_width = page_rect.width
        original_height = page_rect.height

        # Expand the page dimensions to include the margin
        new_width = original_width + margin_width
        new_rect = fitz.Rect(0, 0, new_width, original_height)

        # Set both media box and crop box to the new dimensions
        page.set_mediabox(new_rect)
        page.set_cropbox(new_rect)

    # Find all links and tags in the HTML
    all_elements = []

    # Find links
    for a_tag in soup.find_all('a'):
        if a_tag.has_attr('href'):
            all_elements.append({
                'type': 'link',
                'text': a_tag.text.strip(),
                'url': a_tag['href']
            })

    # Find template tags (like {{customText[...]}})
    template_pattern = re.compile(r'\{\{.*?\}\}')
    for match in template_pattern.finditer(str(soup)):
        template_tag = match.group()
        all_elements.append({
            'type': 'template',
            'text': template_tag
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
    url_vertical_positions = {}  # Track vertical positions for URLs in the margin per page

    # Process each page
    for page_num in range(len(doc)):
        page = doc[page_num]

        # Initialize vertical position for this page if not already set
        if page_num not in url_vertical_positions:
            url_vertical_positions[page_num] = 50

        # Process all elements and add annotations to the margin
        for element in all_elements:
            # Calculate position for the textbox in the right margin
            original_width = page.rect.width - margin_width
            textbox_x0 = original_width + 10
            textbox_x1 = original_width + margin_width - 10
            textbox_y0 = url_vertical_positions[page_num]

            # Create the annotation text
            if element['type'] == 'link':
                text = f"Link: {element['text']} → {element['url']}"
            elif element['type'] == 'template':
                text = f"Template: {element['text']}"
            else:
                text = f"Tag: <{element['tag_name']}>: {element['text']}"

            # Adjust font size based on text length
            fontsize = 7 if len(text) > 60 else 9
            textbox_height = max(20, 10 + (len(text) // 25) * 5)
            textbox_y1 = textbox_y0 + textbox_height

            # Create a rectangle for the textbox in the margin
            textbox_rect = fitz.Rect(textbox_x0, textbox_y0, textbox_x1, textbox_y1)

            # Insert a textbox with the element info in the margin
            page.insert_textbox(
                textbox_rect,
                text,
                fontsize=fontsize,
                color=(0, 0, 0),
                align=0
            )

            # Draw a light gray rectangle around the textbox for better visibility
            page.draw_rect(textbox_rect, color=(0.8, 0.8, 0.8), width=0.5)

            # Update vertical position for next element on this page
            url_vertical_positions[page_num] = textbox_y1 + 8

            # If we're running out of vertical space, create a new page
            if url_vertical_positions[page_num] > page.rect.height - 60:
                # Add a continuation marker
                continuation_rect = fitz.Rect(
                    textbox_x0, page.rect.height - 50,
                    textbox_x1, page.rect.height - 30
                )
                page.insert_textbox(
                    continuation_rect,
                    "(continued on next page)...",
                    fontsize=8,
                    color=(0.5, 0.5, 0.5),
                    align=1
                )

                # Create a new page with the same dimensions
                new_page = doc.new_page(width=page.rect.width, height=page.rect.height)
                new_page.set_mediabox(page.rect)
                new_page.set_cropbox(page.rect)
                url_vertical_positions[len(doc) - 1] = 50  # Update for the new page

    # Save the annotated PDF
    doc.saveIncr()
    doc.close()

    # Clean up the temporary PDF
    if os.path.exists(temp_pdf_path):
        os.unlink(temp_pdf_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
