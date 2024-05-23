import pandas as pd
from openpyxl import load_workbook
from sqlalchemy import create_engine, text
from openpyxl.utils import get_column_letter
import time
from datetime import datetime, timedelta
from openpyxl.utils import FORMULAE
import sys
import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, send_file,session,jsonify,Blueprint,send_from_directory,flash,redirect,url_for,send_from_directory

app = Flask(__name__)
wcell2g_blueprint = Blueprint('wcel_2g', __name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('ADK00')

@wcell2g_blueprint.route('/wcell2g_index')
def home():
    return render_template('wcell2g_index.html')

@wcell2g_blueprint.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(directory='wcel_2g', path=filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found')
        return redirect(url_for('home'))

@wcell2g_blueprint.route('/modify', methods=['POST'])
def modify_file():
    if 'file' not in request.files:
        flash('No file part')
        return render_template('wcell2g_index.html')  # Stay on the same page
    file = request.files['file']
    expected_filename = 'ZM_2G_WCL.xlsm'
    if file.filename == '':
        flash('No selected file')
        return render_template('wcell2g_index.html')  # Stay on the same page
    if file.filename != expected_filename:
        flash('Filename is different. Please upload the correct file.')
        return render_template('wcell2g_index.html')  # Stay on the same page
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join('wcel_2g', filename))
        flash('File successfully uploaded')
        return render_template('wcell2g_index.html')