# Import required libraries
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, make_response
import fitz  # PyMuPDF library for PDF manipulation
import re    # Regular expressions for pattern matching
import os    # Operating system interfaces
import tempfile  # For creating temporary files
import zipfile  # For creating ZIP archives
import io     # For in-memory file operations
from werkzeug.utils import secure_filename  # For secure file handling

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Secret key for session management (CHANGE THIS IN PRODUCTION!)

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Main route handler for the application.
    Handles both GET (display form) and POST (process files) requests.
    """
    if request.method == "POST":
        # Check if files were included in the request
        if "files" not in request.files:
            flash("No files selected")  # Show error message
            return redirect(request.url)  # Redirect back to the form

        # Get list of all uploaded files
        files = request.files.getlist("files")

        # Check if no files were selected or all files are empty
        if not files or all(file.filename == "" for file in files):
            flash("No files selected")
            return redirect(request.url)

        # Validate that all uploaded files are PDFs
        for file in files:
            if not file.filename.endswith(".pdf"):
                flash(f"File {file.filename} is not a PDF")  # Show error for non-PDF files
                return redirect(request.url)

        try:
            # Create a ZIP file in memory to store all annotated PDFs
            zip_buffer = io.BytesIO()  # Create an in-memory bytes buffer

            # Open a ZIP file in the buffer for writing
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for file in files:
                    # Read the uploaded file content into memory
                    input_pdf = file.read()

                    # Create a temporary input file on disk
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_in:
                        temp_in.write(input_pdf)  # Write the PDF content to the temp file
                        temp_in_path = temp_in.name  # Get the path to the temp file

                    # Create a unique temporary output file for the annotated PDF
                    temp_out_fd, temp_out_path = tempfile.mkstemp(suffix=".pdf")
                    os.close(temp_out_fd)  # Close the file descriptor as we only need the path

                    # Process the PDF to annotate links
                    annotate_pdf_with_links(temp_in_path, temp_out_path)

                    # Get the original filename and prepend 'annotated_'
                    original_filename = os.path.splitext(file.filename)[0]  # Remove extension
                    zip_filename = f"annotated_{original_filename}.pdf"  # Create new filename

                    # Add the processed file to the ZIP with the new filename
                    zip_file.write(temp_out_path, zip_filename)

                    # Clean up temporary files to free disk space
                    if os.path.exists(temp_in_path):
                        os.unlink(temp_in_path)  # Delete input temp file
                    if os.path.exists(temp_out_path):
                        os.unlink(temp_out_path)  # Delete output temp file

            # Prepare to send the ZIP file to the user
            zip_buffer.seek(0)  # Move to the start of the buffer

            # Send the ZIP file as a downloadable attachment
            return send_file(
                zip_buffer,
                as_attachment=True,  # Force download rather than display
                download_name="annotated_files.zip",  # Default filename for download
                mimetype="application/zip"  # Set correct MIME type
            )
        except Exception as e:
            # Handle any errors that occur during processing
            flash(f"Error: {str(e)}")  # Show error message to user
            return redirect(request.url)  # Redirect back to the form

    # For GET requests, render the upload form
    return render_template("index.html")

def annotate_pdf_with_links(input_pdf, output_pdf):
    """
    Processes a PDF file to annotate all links with red boxes and text boxes.
    Strictly follows the sequence:
    1. Add margin to the document
    2. Collect all link information (positions, URLs)
    3. Add red boxes around links
    4. Add textboxes in the margin with full URLs
    """
    # Step 1: Add margin to the document
    doc = fitz.open(input_pdf)
    margin_width = 150  # Define margin width

    # First pass: expand all pages to include margin
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

    # Step 2: Collect all link information (positions, URLs)
    all_links = []
    url_pattern = re.compile(
        r'(?:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|'  # Emails
        r'(?:https?://|www\.)[^\s,;)|]+|'                      # HTTP/HTTPS or www URLs
        r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/[^\s,;)|]+|'            # Domain paths
        r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',                      # Domains
        re.IGNORECASE
    )

    # Collect all links first without modifying the document
    for page in doc:
        # Process explicit links (clickable links)
        links = page.get_links()
        for link in links:
            if "uri" in link:
                rect = fitz.Rect(link["from"])
                all_links.append({
                    "page": page,
                    "rect": rect,
                    "url": link["uri"],
                    "type": "explicit"
                })

        # Process plain text URLs
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    line_text = ""
                    line_spans = []

                    # Collect all spans in this line
                    for span in line["spans"]:
                        line_text += span["text"]
                        line_spans.append(span)

                    # Find URL matches in this line's text
                    matches = list(url_pattern.finditer(line_text))
                    if not matches:
                        continue

                    # Calculate character positions for URL detection
                    char_positions = []
                    for span in line_spans:
                        text = span["text"]
                        if not text:
                            continue

                        char_width = (span["bbox"][2] - span["bbox"][0]) / len(text) if len(text) > 0 else 0
                        for i, char in enumerate(text):
                            char_x0 = span["bbox"][0] + i * char_width
                            char_x1 = span["bbox"][0] + (i + 1) * char_width
                            char_y0 = span["bbox"][1]
                            char_y1 = span["bbox"][3]
                            char_positions.append({
                                "char": char,
                                "rect": fitz.Rect(char_x0, char_y0, char_x1, char_y1),
                                "text_pos": len(line_text) - len(text) + i
                            })

                    # Create URL rectangles by combining character rectangles
                    for match in matches:
                        url = match.group()
                        start_idx = match.start()
                        end_idx = match.end()

                        # Find all characters that are part of this URL
                        url_rects = []
                        for pos in char_positions:
                            if start_idx <= pos["text_pos"] < end_idx:
                                url_rects.append(pos["rect"])

                        # If we found characters for this URL, combine their rectangles
                        if url_rects:
                            combined_rect = url_rects[0]
                            for rect in url_rects[1:]:
                                combined_rect = combined_rect.include_rect(rect)
                            all_links.append({
                                "page": page,
                                "rect": combined_rect,
                                "url": url,
                                "type": "plain"
                            })

    # Steps 3 & 4: Add red boxes around links and draw arrows to textboxes in the margin
    url_vertical_positions = {}  # Track vertical positions for URLs in the margin per page

    # Create a dictionary to organize links by page
    links_by_page = {}
    for link in all_links:
        page_num = link["page"].number
        if page_num not in links_by_page:
            links_by_page[page_num] = []
        links_by_page[page_num].append(link)

    # Process each page and its links
    for page_num in links_by_page:
        page = doc[page_num]  # Get the page

        # Initialize vertical position for this page if not already set
        if page_num not in url_vertical_positions:
            url_vertical_positions[page_num] = 50

        # Process all links on this page
        for link_info in links_by_page[page_num]:
            rect = link_info["rect"]
            url = link_info["url"]

            # Step 3: Draw a red box around the link
            page.draw_rect(rect, color=(1, 0, 0), width=1)

            # Step 4: Create textbox in the right margin
            original_width = page.rect.width - margin_width
            textbox_x0 = original_width + 10
            textbox_x1 = original_width + margin_width - 10
            textbox_y0 = url_vertical_positions[page_num]

            # Calculate textbox height based on URL length
            if len(url) > 50:
                fontsize = 7
                textbox_height = max(30, 10 + (len(url) // 20) * 8)
            else:
                fontsize = 9
                textbox_height = max(20, 10 + (len(url) // 25) * 6)

            textbox_y1 = textbox_y0 + textbox_height

            # Create a rectangle for the textbox in the margin
            textbox_rect = fitz.Rect(textbox_x0, textbox_y0, textbox_x1, textbox_y1)

            # Insert a textbox with the full URL in the margin
            page.insert_textbox(
                textbox_rect,
                url,
                fontsize=fontsize,
                color=(0, 0, 0),
                align=0
                # No fill parameter = transparent background
            )

            # Draw a light gray rectangle around the textbox for better visibility
            page.draw_rect(textbox_rect, color=(0.8, 0.8, 0.8), width=0.5)

            # Draw an arrow from the link to the textbox in the margin
            start = (rect.x1, (rect.y0 + rect.y1) / 2)
            end = (textbox_x0, (textbox_y0 + textbox_y1) / 2)
            page.draw_line(start, end, color=(1, 0, 0), width=0.5)

            # Update vertical position for next URL on this page
            url_vertical_positions[page_num] = textbox_y1 + 10

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
                    color=(0, 0, 0),
                    align=1
                )

                # Create a new page with the same dimensions
                new_page = doc.new_page(width=page.rect.width, height=page.rect.height)
                new_page.set_mediabox(page.rect)
                new_page.set_cropbox(page.rect)
                url_vertical_positions[page_num + 1] = 50

    # Save the annotated PDF
    doc.save(output_pdf, garbage=4)
    doc.close()



# Run the application if this script is executed directly
if __name__ == "__main__":
    # Run on all available network interfaces (0.0.0.0)
    # Use the PORT environment variable if available, otherwise default to 5000
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))