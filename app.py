from flask import Flask, render_template, jsonify, send_file, request
import os
import base64
from PyPDF2 import PdfReader
import mammoth
from printing_system import PrintingSystem
import sqlite3
from datetime import datetime

#DATABASE = 'print_jobs.db'
DATABASE = os.path.join(os.path.dirname(__file__), 'print_jobs.db')

#app = Flask(__name__, static_folder='static', template_folder='templates')
USB_PATH = "/media/xo/AUDREY"

app = Flask(__name__, static_url_path='/static')
#app = Flask(__name__)

# Initialize printing system
printing_system = PrintingSystem(app)

@app.route('/debug-paynow', methods=['POST'])
def debug_paynow():
    try:
        payment = printing_system.ecocash.paynow.create_payment("TEST", "test@example.com")
        payment.add("Test Item", 1.00)
        response = printing_system.ecocash.paynow.send_mobile(payment, "263771234567", "ecocash")
        
        return jsonify({
            "paynow_response": str(response.__dict__),
            "poll_url": getattr(response, 'poll_url', None),
            "redirect_url": getattr(response, 'redirect_url', None)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/process-print', methods=['POST'])
def process_print():
    data = request.get_json()
    
    try:
        result = app.printing_system.process_print_request(data)
        
        if not result['success']:
            return jsonify({'success': False, 'error': result.get('error')}), 400

        # ✅ Ensure poll_url is included in response
        return jsonify({
            'success': True,
            'redirect_url': result['redirect_url'],
            'reference': result['reference'],
            'poll_url': result['poll_url'],  # CRITICAL!
            'amount': result['amount'],
            'instructions': result.get('instructions', 'Check your phone')
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/payment-callback', methods=['POST'])
def payment_callback():
    """Handle Paynow payment notifications"""
    try:
        data = request.form
        reference = data.get('reference')
        
        if not reference:
            app.logger.error("No reference in callback")
            return jsonify({'status': 'error', 'message': 'Missing reference'}), 400

        # Verify the hash
        if not printing_system.ecocash.paynow.verify_hash(data):
            app.logger.warning(f"Invalid hash for reference: {reference}")
            return jsonify({'status': 'invalid hash'}), 400

        # Prepare updates
        updates = {
            'status': data.get('status', ''),
            'payment_reference': data.get('paynowreference', ''),
            'poll_url': data.get('pollurl', '')
        }

        # Update the database
        printing_system._update_print_job(reference, updates)

        # If payment was successful, execute the print job
        if data.get('status') == 'Paid':
            try:
                printing_system.execute_print_job(reference)
                updates['status'] = 'completed'
                updates['printed_at'] = datetime.now().isoformat()
            except Exception as e:
                app.logger.error(f"Print failed for {reference}: {str(e)}")
                updates['status'] = f'print failed: {str(e)}'
            
            # Update status again after print attempt
            printing_system._update_print_job(reference, updates)

        return jsonify({'status': 'received'}), 200

    except Exception as e:
        app.logger.error(f"Callback error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/payment-complete')
def payment_complete():
    """User gets redirected here after payment"""
    reference = request.args.get('reference')
    status = request.args.get('status')
    
    return render_template('payment_complete.html',
        reference=reference,
        status=status,
        success=status == 'Paid'
    )

@app.route('/check-payment-status', methods=['POST'])
def check_payment_status():
    data = request.get_json()
    
    if not data or not data.get('poll_url'):
        return jsonify({
            'success': False,
            'error': 'Missing poll_url parameter'
        }), 400
    
    try:
        poll_url = data.get('poll_url')
        reference = data.get('reference')
        
        # Check the payment status
        result = app.printing_system.check_payment_status(poll_url)
        
        # Get more detailed information from database if available
        job_info = None
        if reference:
            with sqlite3.connect(DATABASE) as conn:
                conn.row_factory = sqlite3.Row
                job_info = conn.execute(
                    "SELECT * FROM print_jobs WHERE reference = ?", 
                    (reference,)
                ).fetchone()
        
        status_info = {
            'success': True,
            'status': result['status'],
            'amount': result['amount'],
            'paynow_reference': result['reference'],
            'job_status': job_info['status'] if job_info else None
        }
        
        print("STATUS: ", status_info)
        
        # If payment is confirmed, update the job status in the database
        if result['status'] == 'Paid' and reference:
            try:
                # Update the job status
                with sqlite3.connect(DATABASE) as conn:
                    conn.execute(
                        "UPDATE print_jobs SET status = 'paid', payment_reference = ? WHERE reference = ?",
                        (result['reference'], reference)
                    )
                    conn.commit()
                
                # Queue the print job for execution
                # This could be done asynchronously in a production environment
                try:
                    app.printing_system.execute_print_job(reference)
                    status_info['job_status'] = 'printed'
                except Exception as print_error:
                    app.logger.error(f"Print execution failed: {str(print_error)}")
                    status_info['job_status'] = f"print_failed: {str(print_error)}"
            except Exception as db_error:
                app.logger.error(f"Database update failed: {str(db_error)}")
        
        return jsonify(status_info), 200
        
    except Exception as e:
        app.logger.error(f"Payment status check error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
          
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/usb')
def usb():
    return render_template('usb.html')

@app.route('/<page>')
def serve_page(page):
    if page.endswith('.html'):
        return send_from_directory('templates', page)
    return "Not found", 404

def decode_path(encoded):
    try:
        return base64.b64decode(encoded).decode('utf-8')
    except:
        return None

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
                    "pages": "--"  # Removed slow page count
                })
    return jsonify(sorted(files, key=lambda x: x['name']))

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
            with open(filepath, "rb") as docx_file:
                result = mammoth.convert_to_html(docx_file)
                html_content = result.value
            return render_template("docx_preview.html",
                filename=os.path.basename(filepath),
                html_content=html_content)
        except Exception as e:
            return f"Error previewing DOCX: {str(e)}", 500

    elif ext in ['jpg', 'jpeg', 'png']:
        return render_template('image_preview.html',
            filename=os.path.basename(filepath),
            file_url=f"/file/{encoded}"
        )

    return "Unsupported file type", 400

@app.route('/file/<encoded>')
def serve_file(encoded):
    filepath = decode_path(encoded)
    if not filepath or not os.path.exists(filepath):
        return "File not found", 404
    return send_file(filepath)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
