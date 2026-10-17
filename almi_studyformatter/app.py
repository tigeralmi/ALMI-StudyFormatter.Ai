from flask import Flask, render_template, request, send_file, jsonify, session
from io import BytesIO
from xhtml2pdf import pisa
import html

app = Flask(__name__)
app.secret_key = "almi_super_secret_admin_key_change_in_production"

# Mock Database for Users & Coins (Admin Override Enabled)
USERS_DB = {
    "admin@almi.ai": {
        "password": "adminpassword123",
        "coins": 99999,  # Unlimited master admin coins
        "is_admin": True,
        "plan": "Virtual School Master"
    },
    "student@university.edu": {
        "password": "password123",
        "coins": 70,      # Standard user starting coin balance
        "is_admin": False,
        "plan": "Free"
    }
}


@app.route('/')
def index():
    if 'user' not in session:
        session['user'] = 'admin@almi.ai'
        session['is_admin'] = True

    current_email = session['user']
    user_data = USERS_DB.get(current_email, USERS_DB["admin@almi.ai"])
    return render_template('index.html', user=user_data)


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or request.form
    email = data.get('email')
    password = data.get('password')

    if email in USERS_DB and USERS_DB[email]['password'] == password:
        session['user'] = email
        session['is_admin'] = USERS_DB[email]['is_admin']
        return jsonify({
            "success": True, 
            "message": "Logged in successfully!",
            "coins": USERS_DB[email]['coins'],
            "is_admin": USERS_DB[email]['is_admin']
        })
    
    return jsonify({"success": False, "message": "Invalid email or password."}), 401


@app.route('/api/user-status', methods=['GET'])
def user_status():
    current_email = session.get('user', 'admin@almi.ai')
    user = USERS_DB.get(current_email, USERS_DB["admin@almi.ai"])
    return jsonify({
        "email": current_email,
        "coins": user['coins'],
        "is_admin": user['is_admin'],
        "plan": user['plan']
    })


def parse_content_to_html(content):
    """
    Parses user note inputs (Markdown headings, bullet points, callouts)
    into structured HTML elements with rich CSS styling.
    """
    html_output = ""
    lines = content.split('\n')
    
    in_list = False

    for line in lines:
        line_str = line.strip()
        
        # Empty space line
        if not line_str:
            if in_list:
                html_output += "</ul>"
                in_list = False
            html_output += '<div style="margin-bottom: 6px;"></div>'
            continue

        # Close list if non-list item appears
        if in_list and not line_str.startswith('- ') and not line_str.startswith('* '):
            html_output += "</ul>"
            in_list = False

        # Heading 1 (# Header)
        if line_str.startswith('# '):
            heading_text = html.escape(line_str[2:].strip())
            html_output += f'''
                <div style="margin-top: 18px; margin-bottom: 10px; border-left: 5px solid #2563EB; padding-left: 10px; background-color: #F0F5FF; padding-top: 6px; padding-bottom: 6px; border-radius: 0 4px 4px 0;">
                    <h2 style="color: #1E3A8A; font-size: 15px; margin: 0; font-family: Helvetica, Arial, sans-serif; font-weight: bold;">{heading_text}</h2>
                </div>
            '''

        # Heading 2 (## Subheader)
        elif line_str.startswith('## '):
            subheading_text = html.escape(line_str[3:].strip())
            html_output += f'''
                <h3 style="color: #0D9488; font-size: 13px; margin-top: 14px; margin-bottom: 6px; font-weight: bold; border-bottom: 1px solid #CCFBF1; padding-bottom: 4px;">{subheading_text}</h3>
            '''

        # Amber Callout Box (Note: ...)
        elif line_str.lower().startswith('note:'):
            note_text = html.escape(line_str[5:].strip())
            html_output += f'''
                <div style="background-color: #FFFBEB; border: 1px solid #FCD34D; border-left: 5px solid #D97706; padding: 10px 12px; margin: 12px 0; border-radius: 4px;">
                    <div style="color: #B45309; font-weight: bold; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px;">Important Note</div>
                    <div style="color: #78350F; font-size: 11px; line-height: 1.5;">{note_text}</div>
                </div>
            '''

        # Info Box (Tip: / Info: ...)
        elif line_str.lower().startswith('tip:') or line_str.lower().startswith('info:'):
            prefix = "PRO TIP" if line_str.lower().startswith('tip:') else "INFORMATION"
            info_text = html.escape(line_str[4:].strip())
            html_output += f'''
                <div style="background-color: #EFF6FF; border: 1px solid #93C5FD; border-left: 5px solid #3B82F6; padding: 10px 12px; margin: 12px 0; border-radius: 4px;">
                    <div style="color: #1D4ED8; font-weight: bold; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px;">{prefix}</div>
                    <div style="color: #1E40AF; font-size: 11px; line-height: 1.5;">{info_text}</div>
                </div>
            '''

        # Bullet List Items (- or *)
        elif line_str.startswith('- ') or line_str.startswith('* '):
            if not in_list:
                html_output += '<ul style="margin: 6px 0 10px 20px; padding: 0; color: #334155; font-size: 11px;">'
                in_list = True
            item_text = html.escape(line_str[2:].strip())
            html_output += f'<li style="margin-bottom: 4px; line-height: 1.5;">{item_text}</li>'

        # Regular Body Paragraph
        else:
            para_text = html.escape(line_str)
            html_output += f'''
                <p style="color: #334155; font-size: 11px; line-height: 1.6; margin: 0 0 8px 0;">{para_text}</p>
            '''

    if in_list:
        html_output += "</ul>"

    return html_output


@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        current_email = session.get('user', 'admin@almi.ai')
        user = USERS_DB.get(current_email, USERS_DB["admin@almi.ai"])

        title = request.form.get('title', 'Untitled Study Notes').strip()
        content = request.form.get('content', '')

        COST = 10

        if not user['is_admin'] and user['coins'] < COST:
            return jsonify({"error": "Insufficient coins! Please upgrade your plan."}), 400

        if not user['is_admin']:
            user['coins'] -= COST

        # Format content body
        body_html = parse_content_to_html(content)
        safe_title = html.escape(title)

        # Full HTML Document Template styled for PDF output
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: a4 portrait;
                    margin: 18mm 15mm 20mm 15mm;
                    @frame footer {{
                        -pdf-frame-content: footer-content;
                        bottom: 8mm;
                        margin-left: 15mm;
                        margin-right: 15mm;
                        height: 10mm;
                    }}
                }}
                body {{
                    font-family: Helvetica, Arial, sans-serif;
                    color: #0F172A;
                    margin: 0;
                    padding: 0;
                }}
                .header-table {{
                    width: 100%;
                    background-color: #1E3A8A;
                    color: white;
                    padding: 10px 14px;
                    border-radius: 4px;
                    margin-bottom: 16px;
                }}
                .branding-title {{
                    font-size: 12px;
                    font-weight: bold;
                    letter-spacing: 0.5px;
                    color: #FFFFFF;
                }}
                .branding-sub {{
                    font-size: 8px;
                    color: #93C5FD;
                    text-align: right;
                }}
                .doc-title {{
                    font-size: 22px;
                    font-weight: bold;
                    color: #1E293B;
                    margin: 10px 0 6px 0;
                }}
                .divider {{
                    height: 3px;
                    background-color: #2563EB;
                    width: 100%;
                    margin-bottom: 16px;
                }}
                .footer-text {{
                    font-size: 8px;
                    color: #64748B;
                    text-align: center;
                    border-top: 1px solid #E2E8F0;
                    padding-top: 6px;
                }}
            </style>
        </head>
        <body>
            <!-- Top Branding Banner -->
            <table class="header-table">
                <tr>
                    <td class="branding-title">ALMI StudyFormatter.Ai</td>
                    <td class="branding-sub">Academic Design Engine &nbsp;|&nbsp; High-Speed Export</td>
                </tr>
            </table>

            <!-- Document Title -->
            <div class="doc-title">{safe_title}</div>
            <div class="divider"></div>

            <!-- Parsed Content Body -->
            <div style="margin-top: 10px;">
                {body_html}
            </div>

            <!-- Footer -->
            <div id="footer-content" class="footer-text">
                Generated via ALMI StudyFormatter.Ai &nbsp;|&nbsp; Professional Academic Report
            </div>
        </body>
        </html>
        """

        # Generate PDF into memory stream
        pdf_stream = BytesIO()
        pisa_status = pisa.CreatePDF(
            src=BytesIO(full_html.encode('utf-8')),
            dest=pdf_stream,
            encoding='utf-8'
        )

        if pisa_status.err:
            return jsonify({"error": "PDF rendering error encountered."}), 500

        pdf_stream.seek(0)

        # Generate safe filename
        clean_filename = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
        download_name = f"{clean_filename or 'Study_Notes'}.pdf"

        return send_file(
            pdf_stream,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/pdf'
        )

    except Exception as e:
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)