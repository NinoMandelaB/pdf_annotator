# PDF Link Annotator

A web application for annotating links in PDF files by adding red boxes around detected links and displaying the full URL in connected text boxes.

Live application: [https://pdfannotator-production.up.railway.app/](https://pdfannotator-production.up.railway.app/)

## Features

- Process multiple PDF files simultaneously
- Detects clickable links and plain text URLs/emails
- Adds visual annotations with red boxes and connected text boxes
- Downloads all annotated files as a single ZIP archive
- Preserves original filenames with "annotated_" prefix

## Requirements

- Python 3.7+
- Flask web framework
- PyMuPDF library

## Installation and Usage

### Local Setup

1. Install dependencies:
   ```
   pip install flask pymupdf
   ```

2. Run the application:
   ```
   python app.py
   ```

3. Open your browser to:
   ```
   http://localhost:5000
   ```

4. Upload PDF files using the web interface
5. Download the annotated ZIP archive

### Deployment

The application is currently deployed on Railway.app. To deploy your own instance:

1. Create a new Railway project
2. Connect your GitHub repository
3. Railway will automatically deploy the application

### Azure Deployment:
navigate to /terraform/AzureInstallation.md

## Project Structure

```
pdf-link-annotator/
├── app.py          # Main application logic
├── templates/
│   └── index.html  # Web interface template
├── terraform/      # Terraform configuration for Azure
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── README.md   # Azure deployment instructions
└── README.md       # This file

## Configuration

Environment variables:
- `SECRET_KEY`: Flask secret key (default: "your_secret_key_here")
- `PORT`: Application port (defaults to 5000)

## Dependencies

Create a requirements.txt file with:
```
Flask==2.3.2
PyMuPDF==1.22.5
```

Install with:
```
pip install -r requirements.txt
```


