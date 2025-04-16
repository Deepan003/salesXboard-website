from flask import Flask, render_template, request, redirect, send_file, session
import pandas as pd
import matplotlib.pyplot as plt
import os
from io import BytesIO
from flask_mail import Mail, Message
from xhtml2pdf import pisa
import base64
import uuid
import glob

app = Flask(__name__)
app.secret_key = 'super_secret_key_123'  # Needed for Flask session

# Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'salesxboardteam@gmail.com'
app.config['MAIL_PASSWORD'] = 'jxid vptl slwf uwyq'
app.config['MAIL_DEFAULT_SENDER'] = 'salesxboardteam@gmail.com'

mail = Mail(app)

UPLOAD_FOLDER = 'static/uploads'
CHART_FOLDER = 'static/charts'
REPORT_PATH = 'static/SalesXboard_Report.pdf'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHART_FOLDER, exist_ok=True)

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/loading')
def loading():
    return render_template('loading.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/processing', methods=['POST'])
def processing():
    name = request.form['name']
    email = request.form['email']
    company = request.form['company']
    file = request.files['csv_file']

    # Save file with unique name
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(file_path)

    # Store all in session
    session['name'] = name
    session['email'] = email
    session['company'] = company
    session['csv_filename'] = unique_filename

    return render_template('processing.html')  # 5-sec video page

@app.route('/analyze')
def analyze():
    name = session.get('name')
    email = session.get('email')
    company = session.get('company')
    filename = session.get('csv_filename')
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    df = pd.read_csv(file_path)
    df['Date'] = pd.to_datetime(df['Date'])

    # Product Summary
    top_products = df.groupby('Product')['Quantity'].sum().sort_values(ascending=False)
    summary_html = ""
    for i, (product, qty) in enumerate(top_products.items()):
        if i == 0:
            summary_html += f"<p>• <strong>{product}</strong> was the top-performing product with {qty} units sold.</p>"
        elif i <= 2:
            summary_html += f"<p>• <strong>{product}</strong> performed well with {qty} units sold.</p>"
        elif i >= len(top_products) - 2:
            summary_html += f"<p>• <strong>{product}</strong> had poor performance with only {qty} units sold.</p>"
        else:
            summary_html += f"<p>• <strong>{product}</strong> had average performance.</p>"

    # Save charts
    chart_files = []
    def save_chart(fig, name):
        path = os.path.join(CHART_FOLDER, f"{name}.png")
        fig.savefig(path, bbox_inches='tight')
        plt.close(fig)
        chart_files.append(path)

    save_chart(df.groupby('Date')['Price'].sum().plot(kind='line', title='Monthly Revenue').get_figure(), 'revenue')
    save_chart(top_products.head(5).plot(kind='bar', title='Top Products').get_figure(), 'products')
    save_chart(df['Region'].value_counts().plot(kind='pie', autopct='%1.1f%%', title='Sales by Region').get_figure(), 'region')
    save_chart(df.groupby('Category')['Quantity'].sum().plot(kind='bar', title='Category-wise Sales').get_figure(), 'category')
    df['Weekday'] = df['Date'].dt.day_name()
    save_chart(df.groupby('Weekday')['Quantity'].sum().reindex(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']).plot(kind='bar', title='Sales by Weekday').get_figure(), 'weekday')

    # Convert to base64
    charts_base64 = {}
    for path in chart_files:
        key = os.path.basename(path).split('.')[0]
        with open(path, 'rb') as image_file:
            charts_base64[key] = base64.b64encode(image_file.read()).decode('utf-8')

    # Render PDF
    rendered = render_template('pdf_template.html',
                               name=name,
                               company=company,
                               summary=summary_html,
                               charts=charts_base64)

    try:
        with open(REPORT_PATH, 'wb') as f:
            result = pisa.CreatePDF(BytesIO(rendered.encode('utf-8')), dest=f)
        if not result.err:
            with open(REPORT_PATH, 'rb') as f:
                pdf_data = f.read()
            msg = Message(subject="Your SalesXboard Report", recipients=[email])
            msg.body = f"Hi {name},\n\nYour SalesXboard report is attached.\n\nRegards,\nSalesXboard Team"
            msg.attach("SalesXboard_Report.pdf", "application/pdf", pdf_data)
            mail.send(msg)
    except Exception as e:
        print("❌ Error in PDF/email:", e)

    # ✅ CLEANUP: Remove uploaded file and chart images after use
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        for f in glob.glob(os.path.join(CHART_FOLDER, "*.png")):
            os.remove(f)
    except Exception as cleanup_error:
        print("⚠️ Cleanup warning:", cleanup_error)

    return render_template('result.html',
                           product_summary_html=summary_html,
                           charts=charts_base64)

@app.route('/download_report')
def download_report():
    try:
        return send_file(REPORT_PATH, as_attachment=True)
    except Exception as e:
        return f"Error: {e}"

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)
