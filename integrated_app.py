import os
import pandas as pd
import numpy as np
import math
import folium
from flask import Flask, render_template, request, send_file
from openpyxl import load_workbook
from datetime import datetime
import zipfile
from nbr_app.new import nbr_blueprint

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

# Geolytics Web App
app.register_blueprint(nbr_blueprint, url_prefix='')

nbr_template_folder = os.path.join(os.path.dirname(__file__), 'nbr_app', 'templates')
print(f"Template folder path: {nbr_template_folder}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
