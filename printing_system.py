import os
from datetime import datetime
import sqlite3
from paynow import Paynow

class EcoCashPayment:
    def __init__(self):
        # paynow credentials
        self.merchant_id = os.getenv('PAYNOW_MERCHANT_ID')
        self.integration_key = os.getenv('PAYNOW_INTEGRATION_KEY')
        self.base_url = os.getenv('APP_BASE_URL', 'http://localhost:5000')
        
        self.paynow = Paynow(
            self.merchant_id,
            self.integration_key,
            f"{self.base_url}/payment-complete",
            f"{self.base_url}/payment-callback"
        )
        self.paynow.debug = False

    def initiate_payment(self, phone, amount, reference, email="tafadzwawilsonsedze@gmail.com"):
        try:
            payment = self.paynow.create_payment(reference, email)
            payment.add('Document Printing', amount)

            response = self.paynow.send_mobile(payment, phone, 'ecocash')

            # Debug the actual response values
            # print("RAW RESPONSE:", response.__dict__)
            
            if not response.success:
                error = getattr(response, 'error', 'Payment initiation failed')
                raise Exception(f"Paynow Error: {error}")

            # Properly extract the redirect URL
            redirect_url = None
            
            # First try the direct attribute
            if hasattr(response, 'redirect_url') and isinstance(getattr(response, 'redirect_url'), str):
                redirect_url = response.redirect_url
            
            # Then try the data dictionary
            if not redirect_url and hasattr(response, 'data'):
                data = response.data
                if isinstance(data, dict):
                    redirect_url = data.get('browserurl') or data.get('redirecturl')
            
            # Final fallback for test transactions
            if not redirect_url and hasattr(response, 'poll_url'):
                poll_url = response.poll_url
                if poll_url and isinstance(poll_url, str) and 'CheckPayment' in poll_url:
                    guid = poll_url.split('guid=')[1]
                    redirect_url = f"https://www.paynow.co.zw/Interface/CompletePayment/?guid={guid}"
            
            # Validate the redirect URL
            if not redirect_url or not isinstance(redirect_url, str) or not redirect_url.startswith('http'):
                raise Exception(f"No valid redirect URL found. Response data: {response.__dict__}")

            # Get instructions
            instructions = "Check your phone for payment prompt"
            if hasattr(response, 'instruction') and isinstance(response.instruction, str):
                instructions = response.instruction
            elif hasattr(response, 'instructions') and isinstance(response.instructions, str):
                instructions = response.instructions

            return {
                'status': 'success',
                'redirect_url': redirect_url,
                'poll_url': response.poll_url,
                'instructions': instructions
            }


        except Exception as e:
            raise Exception(f"Payment processing failed: {str(e)}") 
class PrintingSystem:
    def __init__(self, app=None):
        self.ecocash = EcoCashPayment()
        self._init_db()
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """For Flask application factory pattern"""
        self.app = app
        app.printing_system = self
        
    def _init_db(self):
        """Initialize SQLite database"""
        with sqlite3.connect('print_jobs.db') as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS print_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT UNIQUE,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    pages TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    copies INTEGER NOT NULL,
                    orientation TEXT NOT NULL,
                    ecocash_number TEXT NOT NULL,
                    print_pass TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    poll_url TEXT,
                    payment_reference TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    printed_at TIMESTAMP
                )
            """)
            conn.commit()
    
    def process_print_request(self, data):
        try:
            if not data['ecocash'].startswith(('077', '078')):
                raise ValueError("Only EcoCash numbers (077/078) accepted")

            page_info = self._parse_page_selection(data['pages'], data['totalPages'])
            total_cost = round(
                float(page_info['count']) * float(data['copies']) * float(os.getenv('ECOCOST_PER_PAGE', 0.1)),
                2
            )

            reference = f"PRINT{datetime.now().strftime('%Y%m%d%H%M%S')}"

            
        
            payment_res = self.ecocash.initiate_payment(
                phone=data['ecocash'],
                amount=total_cost,
                reference=reference
            )

            # Debug the payment response
            # print("PAYMENT RESPONSE:", payment_res)
            
            if not payment_res.get('poll_url'):
                raise ValueError("Paynow did not provide a poll_url")
            
            # Validate the redirect URL exists and is a string
            redirect_url = payment_res.get('redirect_url')
            if not redirect_url or not isinstance(redirect_url, str):
                raise ValueError("Invalid redirect URL received from payment gateway")

            self._save_print_job({
                'reference': reference,
                'filename': data['filename'],
                'filepath': data['filepath'],
                'pages': ','.join(map(str, page_info['pages'])),
                'page_count': page_info['count'],
                'copies': data['copies'],
                'orientation': data['orientation'],
                'ecocash_number': data['ecocash'],
                'print_pass': data['printpass'],
                'amount': total_cost,
                'status': 'pending',
                #'poll_url': payment_res.get('poll_url')
                'poll_url': payment_res['poll_url'] 
            })

            return {
                'success': True,
                'redirect_url': redirect_url,
                'reference': reference,
                'poll_url': payment_res['poll_url'],
                'amount': "{:.2f}".format(total_cost),
                'instructions': payment_res.get('instructions', '')
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

               
    # Fix for the check_payment_status method in PrintingSystem class

    def check_payment_status(self, poll_url):
        """Check payment status using Paynow SDK"""
        try:
            # Make sure the paynow instance is initialized
            if not hasattr(self, 'ecocash') or not hasattr(self.ecocash, 'paynow'):
                raise Exception("Payment system not properly initialized")
            
            # Use the paynow SDK to check the status
            status = self.ecocash.paynow.check_transaction_status(poll_url)
            
            # Check if the status object has the expected properties
            if not hasattr(status, 'status'):
                # Log the actual response for debugging
                print(f"Unexpected response format: {status.__dict__}")
                
                # Try to extract status from different attributes
                actual_status = None
                if hasattr(status, 'data') and isinstance(status.data, dict):
                    actual_status = status.data.get('status')
                
                if not actual_status:
                    raise Exception("Could not determine payment status")
                
                # Return a standardized response
                return {
                    'status': actual_status,
                    'amount': getattr(status, 'amount', '0.00'),
                    'reference': getattr(status, 'reference', 'Unknown')
                }
            
            # Return a standardized response with all available information
            return {
                'status': status.status,
                'amount': getattr(status, 'amount', '0.00'),
                'reference': getattr(status, 'reference', 'Unknown'),
                'paid_at': getattr(status, 'paid_at', None)
            }

        except Exception as e:
            print(f"Payment status check error: {str(e)}")
            raise Exception(f"Payment check failed: {str(e)}")
        
    def _save_print_job(self, data):
        """Save print job to database"""
        with sqlite3.connect('print_jobs.db') as conn:
            conn.execute("""
                INSERT INTO print_jobs (
                    reference, filename, filepath, pages, page_count, copies,
                    orientation, ecocash_number, print_pass, amount, status, poll_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['reference'],
                data['filename'],
                data['filepath'],
                data['pages'],
                data['page_count'],
                data['copies'],
                data['orientation'],
                data['ecocash_number'],
                data['print_pass'],
                data['amount'],
                data['status'],
                data.get('poll_url')
            ))
            conn.commit()
            #return cursor.lastrowid
    
    def _update_print_job(self, reference, updates):
        """Update print job status"""
        with sqlite3.connect(DATABASE) as conn:
            set_clause = ', '.join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(reference)
            
            conn.execute(f"""
                UPDATE print_jobs SET {set_clause} WHERE reference = ?
            """, values)
            conn.commit()
    
    def execute_print_job(self, reference):
        """Actually send the document to the printer"""
        # This would be platform-specific code
        # For Linux, you might use lp or cups commands
        # For Windows, you might use win32print
        
        try:
            # Get the job details
            with sqlite3.connect(DATABASE) as conn:
                job = conn.execute("""
                    SELECT * FROM print_jobs WHERE reference = ?
                """, (reference,)).fetchone()
            
            if not job:
                raise Exception("Print job not found")
            
            # Example for Linux (using lp command)
            # You'll need to implement proper page selection and copies handling
            import subprocess
            cmd = [
                'lp',
                '-n', str(job['copies']),
                '-o', f'page-ranges={job["pages"]}',
                '-o', f'orientation-requested={job["orientation"]}',
                job['filepath']
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Print failed: {result.stderr}")
            
            # Update status
            self._update_print_job(reference, {
                'status': 'completed',
                'printed_at': datetime.now().isoformat()
            })
            
            return True
        except Exception as e:
            self._update_print_job(reference, {
                'status': f'failed: {str(e)}'
            })
            raise

    def _parse_page_selection(self, pages_input, total_pages):
        """Parse page selection string into actual page numbers"""
        try:
            pages_input = (pages_input or '').lower().strip()
            
            if not pages_input or pages_input == "all":
                pages = list(range(1, total_pages + 1))
                return {
                    'count': len(pages),
                    'pages': pages,
                    'description': 'All pages'
                }
            
            if pages_input == "odd":
                pages = [p for p in range(1, total_pages + 1) if p % 2 == 1]
                return {
                    'count': len(pages),
                    'pages': pages,
                    'description': 'Odd pages'
                }
            
            if pages_input == "even":
                pages = [p for p in range(1, total_pages + 1) if p % 2 == 0]
                return {
                    'count': len(pages),
                    'pages': pages,
                    'description': 'Even pages'
                }
            
            # Handle complex page selections (1,3,5-8, etc.)
            selected_pages = set()
            parts = pages_input.split(',')
            
            for part in parts:
                part = part.strip()
                if '-' in part:
                    start_end = part.split('-')
                    if len(start_end) == 2:
                        try:
                            start = max(1, int(start_end[0]))
                            end = min(total_pages, int(start_end[1]))
                            selected_pages.update(range(start, end + 1))
                        except ValueError:
                            continue
                else:
                    try:
                        page = int(part)
                        if 1 <= page <= total_pages:
                            selected_pages.add(page)
                    except ValueError:
                        continue
            
            if not selected_pages:
                raise ValueError("No valid pages selected")
            
            return {
                'count': len(selected_pages),
                'pages': sorted(selected_pages),
                'description': pages_input
            }
            
        except Exception as e:
            raise ValueError(f"Invalid page selection: {str(e)}")
