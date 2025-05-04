from flask import Flask, render_template, jsonify, send_file
import os
import base64
import subprocess
import tempfile
from PyPDF2 import PdfReader

app = Flask(__name__, static_folder='static', template_folder='templates')
USB_PATH = "/media/xo/AUDREY"  # Your USB path

# Route for dashboard
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# Route for USB page
@app.route('/usb')
def usb():
    return render_template('usb.html')


@app.route('/<page>')
def serve_page(page):
    if page.endswith('.html'):
        return send_from_directory('templates', page)
    return "Not found", 404

# Function to decode file path from base64
def decode_path(encoded):
    try:
        return base64.b64decode(encoded).decode('utf-8')
    except:
        return None

# Function to count pages for pdf/docx/image
def get_page_count(filepath, ext):
    try:
        if ext == 'pdf':
            reader = PdfReader(filepath)
            return len(reader.pages)

        elif ext == 'docx':
            with tempfile.TemporaryDirectory() as tmpdir:
                subprocess.run([
                    'libreoffice', '--headless', '--convert-to', 'pdf',
                    '--outdir', tmpdir, filepath
                ], check=True)

                # Look for the PDF that was just created
                for f in os.listdir(tmpdir):
                    if f.lower().endswith('.pdf'):
                        converted_pdf = os.path.join(tmpdir, f)
                        reader = PdfReader(converted_pdf)
                        return len(reader.pages)
                
                return '--'  # If PDF not found

        elif ext in ['jpg', 'jpeg', 'png']:
            return 1

    except Exception as e:
        print(f"[PageCountError] {filepath}: {e}")
        return '--'
    
    return '--'

# List supported files with page count
@app.route('/files')
def list_files():
    files = []
    if os.path.exists(USB_PATH):
        for root, _, filenames in os.walk(USB_PATH):
            for f in filenames:
                full_path = os.path.join(root, f)
                ext = f.split('.')[-1].lower()
                files.append({
                    "name": f,
                    "path": full_path,
                    "type": ext,
                    "pages": get_page_count(full_path, ext)
                })
    return jsonify(sorted(files, key=lambda x: x['name']))

# Preview file route
@app.route('/preview/<encoded>')
def preview_file(encoded):
    filepath = decode_path(encoded)
    if not filepath or not os.path.exists(filepath):
        return "File not found", 404

    ext = filepath.split('.')[-1].lower()
    
    if ext == 'pdf':
        return render_template('pdf_preview.html',
            filename=os.path.basename(filepath),
            file_url=f"/file/{encoded}"
        )
    elif ext == 'docx':
        try:
            # Generate unique filename to avoid conflicts
            output_filename = os.path.splitext(os.path.basename(filepath))[0] + '.pdf'
            output_path = os.path.join('static/temp_pdfs', output_filename)

            # Ensure temp directory exists
            os.makedirs('static/temp_pdfs', exist_ok=True)

            # Convert DOCX to PDF using LibreOffice
            try:
                subprocess.run([
                    'libreoffice', '--headless', '--convert-to', 'pdf',
                    '--outdir', 'static/temp_pdfs', filepath
                ], check=True, timeout=30)  # Added timeout
            except subprocess.TimeoutExpired:
                return render_template('conversion_error.html',
                    filename=os.path.basename(filepath),
                    error_message="Conversion timed out. Please try again."
                )
            except subprocess.CalledProcessError:
                return render_template('conversion_error.html',
                    filename=os.path.basename(filepath),
                    error_message="Failed to convert document. Please try again."
                )

            # Check if conversion succeeded
            if os.path.exists(output_path):
                return render_template('pdf_preview.html',
                    filename=os.path.basename(filepath),
                    file_url=f"/static/temp_pdfs/{output_filename}"
                )

            # If we get here, conversion failed silently
            return render_template('conversion_error.html',
                filename=os.path.basename(filepath),
                error_message="Document conversion failed. Please try again."
            )

        except Exception as e:
            print(f"Unexpected error during DOCX conversion: {str(e)}")
            return render_template('conversion_error.html',
                filename=os.path.basename(filepath),
                error_message="An unexpected error occurred. Please try again."
            )

    elif ext in ['jpg', 'jpeg', 'png']:
        return render_template('image_preview.html',
            filename=os.path.basename(filepath),
            file_url=f"/file/{encoded}"
        )
    return "Unsupported file type", 400

# Route to serve temporary converted PDFs
@app.route('/temp-pdf/<encoded>')
def serve_temp_pdf(encoded):
    # Decode base64-encoded path to get the real file path
    filepath = base64.urlsafe_b64decode(encoded).decode('utf-8')
    if not filepath or not os.path.exists(filepath):
        return "File not found", 404
    return send_file(filepath, as_attachment=False)

# Serve raw file
@app.route('/file/<encoded>')
def serve_file(encoded):
    filepath = decode_path(encoded)
    if not filepath or not os.path.exists(filepath):
        return "File not found", 404
    return send_file(filepath)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
