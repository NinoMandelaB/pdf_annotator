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
    Args:
        input_pdf (str): Path to the input PDF file
        output_pdf (str): Path to save the annotated PDF file
    """
    # Open the input PDF document
    doc = fitz.open(input_pdf)

    # Define margin width for URLs (120 points for better readability)
    margin_width = 120

    # First pass: expand all pages to include margin
    for page in doc:
        # Get current page dimensions
        page_rect = page.rect
        original_width = page_rect.width
        original_height = page_rect.height

        # Expand the page dimensions to include the margin
        new_width = original_width + margin_width
        new_rect = fitz.Rect(0, 0, new_width, original_height)

        # Set both media box and crop box to the new dimensions
        page.set_mediabox(new_rect)
        page.set_cropbox(new_rect)

    # Regular expression pattern to match URLs and email addresses
    url_pattern = re.compile(
        r'(?:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|'  # Emails: user@domain.com
        r'(?:https?://|www\.)[^\s]+)',                        # HTTP/HTTPS or www URLs
        re.IGNORECASE  # Case-insensitive matching
    )

    # List to store all links found in the document
    all_links = []

    # Second pass: find all links (now that pages are expanded)
    for page in doc:
        # --- Process explicit links (clickable links) ---
        links = page.get_links()  # Get all links on the page
        for link in links:
            if "uri" in link:  # Check if the link has a URI
                rect = fitz.Rect(link["from"])  # Get the link's rectangle coordinates
                all_links.append({"page": page, "rect": rect, "url": link["uri"], "type": "explicit"})

        # --- Process plain text URLs (non-clickable text that looks like a URL) ---
        blocks = page.get_text("dict")["blocks"]  # Get all text blocks on the page
        for block in blocks:
            if "lines" in block:  # Check if the block contains text lines
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"]
                        matches = list(url_pattern.finditer(text))  # Find all URL matches in the text
                        if not matches:  # Skip if no URLs found
                            continue

                        # Calculate the width of each character in the span
                        char_width = (span["bbox"][2] - span["bbox"][0]) / len(text) if len(text) > 0 else 0
                        for match in matches:
                            url = match.group()  # Get the matched URL text
                            start_idx = match.start()  # Start position of the URL in the text
                            end_idx = match.end()  # End position of the URL in the text

                            # Calculate the exact bounding box for the URL text
                            url_x0 = span["bbox"][0] + start_idx * char_width
                            url_x1 = span["bbox"][0] + end_idx * char_width
                            url_y0 = span["bbox"][1]
                            url_y1 = span["bbox"][3]
                            url_rect = fitz.Rect(url_x0, url_y0, url_x1, url_y1)

                            # Add the URL to our list of links to annotate
                            all_links.append({"page": page, "rect": url_rect, "url": url, "type": "plain"})

    # Third pass: annotate all found links
    url_vertical_positions = {}  # Track vertical positions for URLs in the margin per page

    for link_info in all_links:
        page = link_info["page"]  # The page containing the link
        page_num = page.number
        rect = link_info["rect"]  # The rectangle coordinates of the link
        url = link_info["url"]    # The URL text

        # Initialize vertical position for this page if not already set
        if page_num not in url_vertical_positions:
            url_vertical_positions[page_num] = 50  # Start 50 points from the top

        # Draw a red box around the link
        page.draw_rect(rect, color=(1, 0, 0), width=1)  # RGB color: red

        # Calculate position for the textbox in the right margin
        original_width = page.rect.width - margin_width  # Original width before margin was added
        textbox_x0 = original_width + 5  # 5 points padding from the edge
        textbox_x1 = original_width + margin_width - 5  # 5 points padding from the edge
        textbox_y0 = url_vertical_positions[page_num]

        # Calculate textbox height based on URL length (minimum 20 points)
        textbox_height = max(20, 8 + (len(url) // 30) * 6)  # Adjust height for long URLs
        textbox_y1 = textbox_y0 + textbox_height

        # Create a rectangle for the textbox in the margin
        textbox_rect = fitz.Rect(textbox_x0, textbox_y0, textbox_x1, textbox_y1)

        # Insert a textbox with the full URL in the margin
        page.insert_textbox(
            textbox_rect,
            url,
            fontsize=8,
            color=(0, 0, 0),  # Black text
            align=0           # Left-aligned text
        )

        # Draw a rectangle around the textbox for better visibility
        page.draw_rect(textbox_rect, color=(0.8, 0.8, 0.8), width=0.5)

        # Draw an arrow from the link to the textbox in the margin
        start = (rect.x1, (rect.y0 + rect.y1) / 2)  # Middle-right of the link
        end = (textbox_x0, (textbox_y0 + textbox_y1) / 2)  # Middle-left of the textbox
        page.draw_line(start, end, color=(1, 0, 0), width=0.5)  # Draw red arrow

        # Update vertical position for next URL on this page
        url_vertical_positions[page_num] = textbox_y1 + 8  # Add some spacing

        # If we're running out of vertical space, create a new page
        if url_vertical_positions[page_num] > page.rect.height - 50:
            # Add a continuation marker
            page.insert_textbox(
                fitz.Rect(textbox_x0, page.rect.height - 40, textbox_x1, page.rect.height - 20),
                "(continued on next page)...",
                fontsize=7,
                color=(0, 0, 0),
                align=1  # Centered text
            )

            # Create a new page with the same dimensions
            new_page = doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.set_mediabox(page.rect)
            new_page.set_cropbox(page.rect)

            # Reset vertical position for the new page
            url_vertical_positions[page_num + 1] = 50

    # Save the annotated PDF to the output path
    doc.save(output_pdf, garbage=4)  # Clean up unused objects
    doc.close()  # Close the document


# Run the application if this script is executed directly
if __name__ == "__main__":
    # Run on all available network interfaces (0.0.0.0)
    # Use the PORT environment variable if available, otherwise default to 5000
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
