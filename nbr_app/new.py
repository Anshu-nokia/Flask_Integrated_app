import os
import pandas as pd
import numpy as np
import math
import folium
import random
import psycopg2
from sqlalchemy import create_engine
from geopy.distance import geodesic
from flask import Flask, render_template, request, send_file,session,jsonify
from rtree import index
from werkzeug.utils import secure_filename
# from folium.plugins import Choropleth
from folium.plugins import Draw, MeasureControl, HeatMap
from flask import Blueprint

app = Flask(__name__)
nbr_blueprint = Blueprint('nbr_app', __name__, template_folder='templates', static_folder='static')

# app.secret_key = 'ADK00' 
app.secret_key = os.environ.get('ADK00')
# Create input and output folders if they don't exist
input_folder = "input"
output_folder = "output"

if not os.path.exists(input_folder):
    os.makedirs(input_folder)

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Global variables to store data and map
uploaded_data = None
generated_map = None
nbr_relations_df = None
uploaded_filename = None  # Store the uploaded file name

engine = 'postgresql://postgres:postgres@localhost:5432/postgres'
DBNMAE="postgres"
USER="postgres"
PASSWORD="postgres"
HOST="localhost"
PORT = 5432

####################################################

# Function to calculate sector vertices based on azimuth
def calculate_sector_vertices(lat, lon, radius, azimuth, angle):
    vertices = [(lat, lon)]
    for i in range(-angle // 2, angle // 2 + 1):
        x = lat + radius * math.cos(math.radians(azimuth + i))
        y = lon + radius * math.sin(math.radians(azimuth + i))
        vertices.append((x, y))
    return vertices

# Function to remove the file extension
def remove_extension(filename):
    base_name = os.path.splitext(filename)[0]
    return base_name

def connect_to_database():
    try:
        conn = psycopg2.connect(
        dbname=DBNMAE,
        user=USER,
        password=PASSWORD,
        host=HOST,
        port = PORT
        )
        return conn
    except psycopg2.Error as e:
        print("Error connecting to the database:", e)
        return None

# Function to get tables list from database 
def get_table_list():
    conn = connect_to_database()
    cur = conn.cursor()
    try:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
        table_list = [row[0] for row in cur.fetchall() if row[0].startswith("PHDB") or row[0].startswith("NBR")]
        return table_list
    finally:
        cur.close()
        conn.close()

# Function to get data from tables in database  
def get_data_from_database(table_name):
    # Establish connection to the PostgreSQL database
    conn = connect_to_database()
    cursor = conn.cursor()

    query = f"SELECT * FROM \"{table_name}\";"
    # Execute the query to fetch data
    cursor.execute(query)
    # Fetch all rows of the result
    data = cursor.fetchall()
    # Get column names from the cursor description
    col_names = [desc[0] for desc in cursor.description]
    # Close cursor and connection
    cursor.close()
    conn.close()
    return col_names, data

# Function to create RULE BOOK table in database  
def create_rule_book_table():
    # Establish a connection to the PostgreSQL database
    conn = connect_to_database()
    
    # Create a cursor object to execute SQL queries
    cursor = conn.cursor()

    # Construct the CREATE TABLE SQL query
    create_query = """
        CREATE TABLE IF NOT EXISTS "Rulebook_geolytics" (
            Type VARCHAR,
            Vendor VARCHAR,
            Tech VARCHAR,
            Sql_Table VARCHAR,
            Site_ID VARCHAR,
            Sector_ID VARCHAR,
            Latitude VARCHAR,
            Longitude VARCHAR,
            Azimuth VARCHAR,
            Bcch VARCHAR
        )
    """

    # Execute the CREATE TABLE query
    cursor.execute(create_query)
    # Commit the changes
    conn.commit()
    # Close cursor and connection
    cursor.close()
    conn.close()

# Function to insert datas into  RULE BOOK table in database  
def insert_rule(type_value, vendor_value, tech_value, site_id_value, sector_id_value, lat_value, long_value, azimuth_value, bcch_value):
    # Establish connection to the PostgreSQL database
    conn = connect_to_database()
    cursor = conn.cursor()

    # Format the Sql_Table value as 'Type_Vendor_Tech'
    sql_table_value = f"{type_value}_{vendor_value}_{tech_value}"

    # Drop and rename the table
    drop_and_rename_query = f"""
        DROP TABLE IF EXISTS "{sql_table_value}";
        ALTER TABLE "uploaded_file" RENAME TO "{sql_table_value}";
    """
    cursor.execute(drop_and_rename_query)
    conn.commit()
    
     # Check if a record with the same Type, Vendor, and Tech values already exists
    exists_query = """
        SELECT EXISTS(
            SELECT 1 FROM "Rulebook_geolytics"
            WHERE Sql_Table = %s
        )
    """
    cursor.execute(exists_query, (sql_table_value,))
    record_exists = cursor.fetchone()[0]

    # If the record exists, update it; otherwise, insert a new one
    if record_exists:
        # Update the existing record
        update_query = """
            UPDATE "Rulebook_geolytics"
            SET Site_ID = %s, Sector_ID = %s, Latitude = %s, Longitude = %s, Azimuth = %s, Bcch = %s
            WHERE Sql_Table = %s
        """
        cursor.execute(update_query, (site_id_value, sector_id_value, lat_value, long_value, azimuth_value, bcch_value, sql_table_value))
        conn.commit()
        print("Record updated successfully.")
    else:
        # Insert a new record
        insert_query = """
            INSERT INTO "Rulebook_geolytics" (Type, Vendor, Tech, Sql_Table, Site_ID, Sector_ID, Latitude, Longitude, Azimuth, Bcch)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (type_value, vendor_value, tech_value, sql_table_value, site_id_value, sector_id_value, lat_value, long_value, azimuth_value, bcch_value))
        conn.commit()
        print("New record inserted successfully.")

    # Close cursor and connection
    cursor.close()
    conn.close()


def execute_sql_query(sql_query):
    """
    Execute SQL query and return results
    """
    conn = connect_to_database()
    # Create a cursor object
    cursor = conn.cursor()
    
    try:
        # Execute the SQL query
        cursor.execute(sql_query)
        
        # Fetch all the rows from the executed query
        rows = cursor.fetchall()
        flattened_rows = [value for row in rows for value in row[4:]]
        
        return flattened_rows
    
    except Exception as e:
        # Print any exceptions that occur
        print("Error:", e)
        
    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()


def fetch_row(table_value):
    global AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID
    """
    Fetch rule book entries for a given table value
    """
    # Construct SQL query
    sql_query = f"SELECT * FROM \"Rulebook_geolytics\" WHERE lower(Sql_Table) = lower('{table_value}')"
    
    # Execute the SQL query
    rows = execute_sql_query(sql_query)
    SITE_ID, SECTOR_ID, LAT, LONG, AZIMUTH, BCCH = rows
    
    return SITE_ID, SECTOR_ID, LAT, LONG, AZIMUTH, BCCH

# TODO: Home Page
@nbr_blueprint.route('/nbr_index')
def home():
    tables = get_table_list()
    return render_template('nbr_index.html',tables=tables)

# TODO: Upload Page
@nbr_blueprint.route('/upload', methods=['GET','POST'])
def upload():
    global uploaded_data, uploaded_filename, AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID, SHEET_NAME , HEADER_ROW

    if request.method == 'POST':
        
        SHEET_NAME = request.form['sheet_name']
        HEADER_ROW = request.form['header_row'] 
        HEADER_ROW = int(HEADER_ROW) - 1

        # Check if the file is submitted
        if 'file' in request.files:
            file = request.files['file']
            if file:
                # Save the file to the input folder
                uploaded_filename = secure_filename(file.filename)
                file.save(os.path.join(input_folder, uploaded_filename))

                # Read the file into a pandas DataFrame
                # uploaded_data = pd.read_excel(os.path.join(input_folder, uploaded_filename), engine='openpyxl', sheet_name=SHEET_NAME)
                uploaded_data = pd.read_excel(os.path.join(input_folder, uploaded_filename), engine='openpyxl', sheet_name=SHEET_NAME, header=int(HEADER_ROW))

                # Get column names
                column_names = uploaded_data.columns.tolist()

                # Render the template with the updated data
                return render_template('upload_file.html', column_names=column_names)

    # If the request method is not POST or there is no file submitted, render the template without any data
    return render_template('upload_file.html', column_names=[])

# TODO: Save details
@nbr_blueprint.route('/save_details_file', methods=['POST'])
def save_details_file():
    global AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID, df, UarfcnDL, EarfcnDL

    # Handle saving details from the second popup form
    
    AZIMUTH = request.form['azi']
    BCCH = request.form['bcch']
    LAT = request.form['lat']
    LONG = request.form['long']
    SECTOR_ID = request.form['sector_id']
    SITE_ID = request.form['site_id']
    UarfcnDL = request.form['freq']
    EarfcnDL = request.form['freq']

    

    dict1 = {
        'SECTOR_ID': SECTOR_ID,
        'SITE_ID': SITE_ID,
        'AZIMUTH': AZIMUTH,
        'BCCH': BCCH,
        'LAT': LAT,
        'LONG': LONG,
        'UarfcnDL': UarfcnDL,
        'EarfcnDL': EarfcnDL

    }

    dict_df = pd.DataFrame(dict1, index=[' '])
    dict_df = dict_df.T
    dict_df_content = dict_df.to_html(classes='table table-striped', escape=False)

    # Assuming you have a DataFrame or database table where you save these details
    # Here, I assume you have a DataFrame named 'saved_details_df'

    # Append the new details to the DataFrame or database table
    saved_details_df = pd.DataFrame()  # Replace this with your actual DataFrame or table
    saved_details_df = saved_details_df._append(uploaded_data)

    # Count the number of rows affected
    num_rows_affected = len(saved_details_df) # Count the number of rows after appending

    # Render the template with the saved details and the number of rows affected
    return render_template('save_details.html', dict_df_content=dict_df_content, num_rows_affected=num_rows_affected)


# TODO: export to database Page
@nbr_blueprint.route('/export', methods=['GET', 'POST'])
def export_to_database():
    global uploaded_data, uploaded_filename, AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID, SHEET_NAME, HEADER_ROW, engine

    if request.method == 'POST':
        SHEET_NAME = request.form['sheet_name']
        HEADER_ROW = request.form['header_row']
        HEADER_ROW = int(HEADER_ROW) - 1

        # Check if the file is submitted
        if 'file' in request.files:
            file = request.files['file']
            if file:
                # Save the file to the input folder
                uploaded_filename = secure_filename(file.filename)
                file.save(os.path.join(input_folder, uploaded_filename))

                # Read the file into a pandas DataFrame
                uploaded_data = pd.read_excel(os.path.join(input_folder, uploaded_filename), engine='openpyxl', sheet_name=SHEET_NAME, header=int(HEADER_ROW))

                # Ingest the uploaded data into PostgreSQL database
                try:
                    # Establish connection to the PostgreSQL database
                    engine = create_engine(engine)
                    conn = engine.connect()

                    # Write DataFrame to PostgreSQL database
                    uploaded_data.to_sql('uploaded_file', con=engine, if_exists='replace', index=False)

                    conn.close()

                    # Get column names
                    column_names = uploaded_data.columns.tolist()

                    # Render the template with the updated data
                    return render_template('upload.html', column_names=column_names)

                except Exception as e:
                    return f"An error occurred: {str(e)}"

    return render_template('upload.html', column_names=None)

# TODO: Save details to database
@nbr_blueprint.route('/save_details', methods=['POST'])
def save_details():
    global AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID

    # Handle saving details from the second popup form
    TYPE = request.form['type']
    VENDOR = request.form['vendor']
    TECH = request.form['tech']
    AZIMUTH = request.form['azi']
    BCCH = request.form['bcch']
    LAT = request.form['lat']
    LONG = request.form['long']
    SECTOR_ID = request.form['sector_id']
    SITE_ID = request.form['site_id']

    # Creating rulebook database
    create_rule_book_table()
        
    # Insert the values into the rulebook database
    insert_rule(TYPE, VENDOR, TECH, SITE_ID, SECTOR_ID, LAT, LONG, AZIMUTH, BCCH)

    dict1 = {
        'SECTOR_ID': SECTOR_ID,
        'SITE_ID': SITE_ID,
        'AZIMUTH': AZIMUTH,
        'BCCH': BCCH,
        'LAT': LAT,
        'LONG': LONG,
    }

    dict_df = pd.DataFrame(dict1, index=[' '])
    dict_df = dict_df.T
    dict_df_content = dict_df.to_html(classes='table table-striped', escape=False)

    # Assuming you have a DataFrame or database table where you save these details
    # Here, I assume you have a DataFrame named 'saved_details_df'

    # Append the new details to the DataFrame or database table
    saved_details_df = pd.DataFrame()  # Replace this with your actual DataFrame or table
    saved_details_df = saved_details_df._append(uploaded_data)

    # Count the number of rows affected
    num_rows_affected = len(saved_details_df) # Count the number of rows after appending

    # Render the template with the saved details and the number of rows affected
    # return render_template('save_details.html', dict_df_content=dict_df_content, num_rows_affected=num_rows_affected)
    return "Your files have been saved successfully"
# Now you can use this function in your existing code

# TODO: Import Data from Database
@nbr_blueprint.route('/import', methods=['POST'])
def import_from_database():
    global uploaded_data, uploaded_filename, AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID
    if request.method == 'POST':
        
        # Get the values selected from the dropdown menus
        table_value = str(request.form['table_select'])

        # Fetch the data from the inserted table
        col_names, uploaded_data = get_data_from_database(table_value)
        
        uploaded_data = pd.DataFrame(uploaded_data, columns=col_names)

        # Fetch rule book entries for the selected table
        rule_book_entries = fetch_row(table_value)
        print(rule_book_entries)
      
        # Optionally, you can redirect the user to another page after storing the values
        return render_template('save_import_details.html', rule_book_entries=rule_book_entries)

    # Handle other HTTP methods or errors
    return 'Invalid request'


# Define custom icons for markers
icon_colors = {
    'green': 'https://leafletjs.com/examples/custom-icons/leaf-green.png',
    'blue': 'https://leafletjs.com/examples/custom-icons/leaf-blue.png',
    'red': 'https://leafletjs.com/examples/custom-icons/leaf-red.png'
}

# Define a color palette for sector polygons
color_palette = {
    'red': '#FF5733',
    'yellow': '#FFD433',
    'blue': '#33B5FF'
}

# TODO: Generate Map
@nbr_blueprint.route('/generate_map', methods=['GET', 'POST'])
def generate_map():
    global uploaded_data, AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID

    if uploaded_data is None: 
        return "Upload a file first"
    
    # Read the data from the uploaded file
    df = uploaded_data.copy()
    column_names = df.columns.tolist()
    site_ids = df[SITE_ID].unique().tolist()
    Radius = [0.001, 0.0012, 0.0014, 0.0016, 0.0018, 0.002, 0.0022, 0.0024, 0.0026, 0.0028, 0.003]
    Map_styles = ['OpenStreetMap', 'satellite']

    if request.method == 'POST':
        # Get user inputs from the form
        map_style = request.form.get('map') 
        site_id_input = str(request.form.get('site_id_1'))
        selected_col = request.form.get('selected_column')
        max_distance_km = float(request.form.get('max_distance'))
        radius = float(request.form.get('r'))
        
        #######################################################################
        # Store form data in session
        session['form_data'] = {
            'map_style': map_style,
            'site_id_input': site_id_input,
            'selected_col': selected_col,
            'max_distance_km': max_distance_km,
            'radius': radius
        }
        form_data = session.get('form_data', {})
        selected_col_default = form_data.get('selected_col', '')
        map_style_default = form_data.get('map_style', '')
        site_id_default = form_data.get('site_id_input', '')
        max_distance_default = form_data.get('max_distance_km', '')
        radius_default = form_data.get('radius',0.003)
        #######################################################################
        
        df[AZIMUTH] = pd.to_numeric(df[AZIMUTH], errors='coerce')

        # Replace NaN values (non-numeric) with 0
        df[AZIMUTH].fillna(0, inplace=True)

        # Convert the entire column to integer type
        df[AZIMUTH] = df[AZIMUTH].astype(int)

        # Filter DataFrame to get data for the specified sector ID
        sector_data = df[df[SITE_ID] == site_id_input]

        # Check if sector_data is empty
        if sector_data.empty:
            return "Site ID not found in DataFrame"

        # Get the coordinates of the specified sector
        sector_lat = sector_data.iloc[0][LAT]
        sector_lon = sector_data.iloc[0][LONG]

        # Create a Folium map centered at the coordinates of the specified sector
        if map_style == 'satellite':
            m = folium.Map(location=[sector_lat, sector_lon], zoom_start=13, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='ArcGIS')
        else:
            m = folium.Map(location=[sector_lat, sector_lon], zoom_start=13, tiles=map_style)
        
        # Add Drawing Tools control to the map
        draw = Draw(
            draw_options={ 
                'polyline': False,  # Disable drawing polylines
                'circle': True,     # Enable drawing circles
                'rectangle': True,  # Enable drawing rectangles
                'marker': False     # Disable drawing markers
            },
            edit_options={
                'poly': {
                    'allowIntersection': False  # Disable intersection for polygons
                }
            }
        )
        draw.add_to(m)

        # Add Measurement Tools control to the map
        measure_control = MeasureControl(primary_length_unit='kilometers', primary_area_unit='sqmeters')
        measure_control.add_to(m)
        
        # Create a feature group for markers
        marker_group = folium.FeatureGroup(name='Markers')

        # Create a dictionary to store feature groups for each BCCH value
        bcch_feature_groups = {}
        color_mapping = {
            bcch_value: '#' + '%06x' % random.randint(0, 0xFFFFFF) for bcch_value in df[BCCH].unique()
        }

        # Create a checkbox for each unique BCCH value
        for bcch_value in df[BCCH].unique():
            bcch_feature_groups[bcch_value] = folium.FeatureGroup(name=f'BCCH {bcch_value}')

        # Your map generation code here
        for index, row in df.iterrows():
            lat, lon = float(row[LAT]), float(row[LONG])
            azimuth = float(row[AZIMUTH])
            angle = 60  # Adjust the angle as needed

            # Calculate the distance between the current point and the specified sector
            distance = geodesic((lat, lon), (sector_lat, sector_lon)).km

            # If the distance is within the specified maximum distance, proceed with plotting
            if distance <= max_distance_km:
                # Calculate sector vertices
                vertices = calculate_sector_vertices(lat, lon, radius, azimuth, angle)
                col_value = str(row[selected_col])
                marker_color = color_mapping.get(row[BCCH], '#000000')

                # Define HTML content for marker with icon and text
                html_content = f"""
                    <div>
                        <span style="color: black;">{col_value}</span>
                    </div>
                """

                # Create a custom icon using the HTML content
                custom_icon = folium.DivIcon(html=html_content)

                # Add marker with custom icon to the marker group
                if row[SITE_ID] == site_id_input:
                    # Highlight the specified site with a different color
                    folium.Marker(location=[lat, lon], icon=folium.Icon(icon='signal', color='pink')).add_to(m)
                else:
                    # Use default marker for other sites
                    folium.Marker(location=[lat, lon], icon=custom_icon).add_to(marker_group)

                # Define popup content for both marker and polygon
                popup_content = "<div style='max-height: 200px; overflow-y: auto;'>"
                for column in uploaded_data.columns:
                    # Convert column value to string and add HTML formatting for each column value
                    column_value = str(row.get(column, ''))
                    popup_content += f"<b>{column}:</b> {column_value}<br>"
                popup_content += "</div>"

                # Create a Folium Polygon to represent the sector with the assigned color
                folium.Polygon(
                    locations=vertices,
                    color='#000000',  # Black border color of the sector
                    fill=True,
                    fill_color=marker_color,  # Fill color of the sector
                    fill_opacity=0.5,
                    weight=2,  # Border weight
                    popup=popup_content.format(**row),  # Pass the entire row to format method for dynamic content
                ).add_to(bcch_feature_groups[row[BCCH]])
        
        # Add Heatmap layer to the map
        heatmap_data = [[row[LAT], row[LONG]] for index, row in df.iterrows()]
        HeatMap(heatmap_data, radius=20, gradient={0.2: 'blue', 0.4: 'lime', 0.6: 'orange', 1: 'red'}, opacity=0.5).add_to(m)
        
        # Add marker and BCCH feature groups to the map
        marker_group.add_to(m)
        for feature_group in bcch_feature_groups.values():
            feature_group.add_to(m)
#         if selected_col_default != '':
#             choropleth = folium.Choropleth(
#                 name='Thematic Layer',
#                 columns=[SITE_ID, selected_col_default],
#                 key_on='feature.properties.SITE_ID',
#                 fill_color='BuPu',  # choose a color scheme
#                 fill_opacity=0.7,
#                 line_opacity=0.2,
#                 legend_name=selected_col_default
#             ).add_to(m)

# # Add layer control to the map with BCCH filtering options
#         folium.LayerControl(
#             collapsed=False,
#             position='topright'
#         ).add_to(m)

        
        # # Add layer control to the map with BCCH filtering options
        folium.LayerControl().add_to(m)

# Return the map
        # Check if m is a Folium map before saving
        # map_filename = f"surrounding_sites_map_{site_id_input}.html"
        # m.save(map_filename)        
        # Render the map template with the map content
        map_content = m.get_root().render()
        if uploaded_filename:
            map_download_link = f"/download_map?file={remove_extension(uploaded_filename)}"

            # Render the map template with the map content
            return render_template('generate_map.html',
                    map_content=map_content,
                    map_download_link=map_download_link,
                    column_names=column_names,
                    site_ids=site_ids,
                    Radius=Radius,
                    Map_styles=Map_styles,
                    selected_col_default=selected_col_default,
                    map_style_default=map_style_default,
                    site_id_default=site_id_default,
                    max_distance_default=max_distance_default,
                    radius_default=radius_default)
        else:
             return render_template('generate_map.html',
                    map_content=map_content,
                    column_names=column_names,
                    site_ids=site_ids,
                    Radius=Radius,
                    Map_styles=Map_styles,
                    selected_col_default=selected_col_default,
                    map_style_default=map_style_default,
                    site_id_default=site_id_default,
                    max_distance_default=max_distance_default,
                    radius_default=radius_default)
        
    # If it's a GET request or any other method, return a valid response
    return render_template('generate_map.html', column_names=column_names,site_ids=site_ids,Radius=Radius,Map_styles=Map_styles)

# TODO: Two sites Search on new page
@nbr_blueprint.route('/search_gen_map', methods=['GET', 'POST'])
def search_gen_map():
    global uploaded_data, AZIMUTH, LAT, LONG, SITE_ID

    if uploaded_data is None: 
        return "Upload a file first"
    
    # Read the data from the uploaded file
    df = uploaded_data.copy()
    site_ids = df[SITE_ID].unique().tolist()
    
    # Map_styles = ['OpenStreetMap', 'Stamen Terrain', 'Stamen Toner', 'Stamen Watercolor', 'CartoDB Positron', 'CartoDB Dark_Matter', 'satellite']

    if request.method == 'POST':
        # Get user inputs from the form
        # map_style = request.form.get('map') 
        site_data_1= str(request.form.get('site1_id'))
        site_data_2= str(request.form.get('site2_id'))

        df[AZIMUTH] = pd.to_numeric(df[AZIMUTH], errors='coerce')

        # Replace NaN values (non-numeric) with 0
        df[AZIMUTH].fillna(0, inplace=True)

        # Convert the entire column to integer type
        df[AZIMUTH] = df[AZIMUTH].astype(int)
        # selected_col = request.form.get('selected_column')
        

        site1_data = df[df[SITE_ID] == site_data_1]
        site2_data = df[df[SITE_ID] == site_data_2]


        # Get the coordinates of the selected site to center the map
        center_lat = (site1_data.iloc[0][LAT] + site2_data.iloc[0][LAT]) / 2
        center_long = (site1_data.iloc[0][LONG] + site2_data.iloc[0][LONG]) / 2
        
        # Create a Folium map centered around the selected site ID
        m = folium.Map(location=[center_lat, center_long], zoom_start=15)  # Adjust zoom level as needed

        # Add markers for each site ID on the map with tooltip showing the site ID
        folium.Marker(
            location=[site1_data.iloc[0][LAT], site1_data.iloc[0][LONG]],
            tooltip=site_data_1,
            icon=folium.Icon(icon='signal', color='pink')).add_to(m)

        folium.Marker(
            location=[site2_data.iloc[0][LAT], site2_data.iloc[0][LONG]],
            tooltip=site_data_2,
            icon=folium.Icon(icon='signal', color='pink')).add_to(m)
        draw = Draw(
            draw_options={
                'polyline': False,  # Disable drawing polylines
                'circle': True,     # Enable drawing circles
                'rectangle': True,  # Enable drawing rectangles
                'marker': False     # Disable drawing markers
            },
            edit_options={
                'poly': {
                    'allowIntersection': False  # Disable intersection for polygons
                }
            }
        )
        draw.add_to(m)

        # Add Measurement Tools control to the map
        measure_control = MeasureControl(primary_length_unit='kilometers', primary_area_unit='sqmeters')
        measure_control.add_to(m)

        bcch_feature_groups = {}
        color_mapping = {
            bcch_value: '#' + '%06x' % random.randint(0, 0xFFFFFF) for bcch_value in df[BCCH].unique()
        }

        # Create a checkbox for each unique BCCH value
        for bcch_value in df[BCCH].unique():
            bcch_feature_groups[bcch_value] = folium.FeatureGroup(name=f'BCCH {bcch_value}')

        # Your map generation code here
        for index, row in df.iterrows():
            lat, lon = float(row[LAT]), float(row[LONG])
            azimuth = float(row[AZIMUTH])
            radius = 0.001  # Adjust the radius as needed
            angle = 60  # Adjust the angle as needed
            vertices = calculate_sector_vertices(lat, lon, radius, azimuth, angle)
            marker_color = color_mapping.get(row[BCCH], '#000000')

            popup_content = "<div style='max-height: 200px; overflow-y: auto;'>"
            for column in uploaded_data.columns:
                    # Add HTML formatting for each column value
                popup_content += f"<b>{column}:</b> {{{column}}}<br>"
            popup_content += "</div>"

                # Create a Folium Polygon to represent the sector with the assigned color
            folium.Polygon(
                locations=vertices,
                color='#000000',  # Black border color of the sector
                fill=True,
                fill_color=marker_color,  # Fill color of the sector
                fill_opacity=0.5,
                weight=2,  # Border weight
                popup=popup_content.format(**row),  # Pass the entire row to format method for dynamic content
            ).add_to(bcch_feature_groups[row[BCCH]])
        # Add Heatmap layer to the map
        heatmap_data = [[row[LAT], row[LONG]] for index, row in df.iterrows()]
        HeatMap(heatmap_data, radius=20, gradient={0.2: 'blue', 0.4: 'lime', 0.6: 'orange', 1: 'red'}, opacity=0.5).add_to(m)
        # Add marker and BCCH feature groups to the map
        for feature_group in bcch_feature_groups.values():
            feature_group.add_to(m)

        # Add layer control to the map with BCCH filtering options
        folium.LayerControl().add_to(m)

        # Display the map
        map_content = m.get_root().render()
        

        # Render the map template with the map content
        return render_template('search_map.html',map_content=map_content, site_ids=site_ids)

    # If it's a GET request or any other method, return a valid response
    return render_template('search_map.html',site_ids=site_ids)


# TOD: Two sites search on BCCH Page
@nbr_blueprint.route('/search_map', methods=['POST'])
def search_map():
    global uploaded_data, AZIMUTH, LAT, LONG, SITE_ID

    if uploaded_data is None: 
        return jsonify({'error': 'Upload a file first'})

    # Read the data from the uploaded file
    df = uploaded_data.copy()
    site_ids = df[SITE_ID].unique().tolist()

    # Parse JSON data from the request
    request_data = request.json
    site_data_1 = request_data.get('site1_id')
    site_data_2 = request_data.get('site2_id')

    # Filter data for the selected site IDs
    site1_data = df[df[SITE_ID] == site_data_1]
    site2_data = df[df[SITE_ID] == site_data_2]

    # Get the coordinates of the selected site to center the map
    center_lat = (site1_data.iloc[0][LAT] + site2_data.iloc[0][LAT]) / 2
    center_long = (site1_data.iloc[0][LONG] + site2_data.iloc[0][LONG]) / 2

    # Perform map generation and processing logic here...
    # Create a Folium map centered around the selected site IDs
    # Create a Folium map centered around the selected site ID
    m = folium.Map(location=[center_lat, center_long], zoom_start=15)  # Adjust zoom level as needed

    # Add markers for each site ID on the map with tooltip showing the site ID
    folium.Marker(
        location=[site1_data.iloc[0][LAT], site1_data.iloc[0][LONG]],
        tooltip=site_data_1,
        icon=folium.Icon(icon='signal', color='pink')).add_to(m)

    folium.Marker(
        location=[site2_data.iloc[0][LAT], site2_data.iloc[0][LONG]],
        tooltip=site_data_2,
        icon=folium.Icon(icon='signal', color='pink')).add_to(m)
    draw = Draw(
        draw_options={
            'polyline': False,  # Disable drawing polylines
            'circle': True,     # Enable drawing circles
            'rectangle': True,  # Enable drawing rectangles
            'marker': False     # Disable drawing markers
        },
        edit_options={
            'poly': {
                'allowIntersection': False  # Disable intersection for polygons
            }
        }
    )
    draw.add_to(m)

    # Add Measurement Tools control to the map
    measure_control = MeasureControl(primary_length_unit='kilometers', primary_area_unit='sqmeters')
    measure_control.add_to(m)

    bcch_feature_groups = {}
    color_mapping = {
        bcch_value: '#' + '%06x' % random.randint(0, 0xFFFFFF) for bcch_value in df[BCCH].unique()
    }

    # Create a checkbox for each unique BCCH value
    for bcch_value in df[BCCH].unique():
        bcch_feature_groups[bcch_value] = folium.FeatureGroup(name=f'BCCH {bcch_value}')

    # Your map generation code here
    for index, row in df.iterrows():
        lat, lon = float(row[LAT]), float(row[LONG])
        azimuth = float(row[AZIMUTH])
        radius = 0.001  # Adjust the radius as needed
        angle = 60  # Adjust the angle as needed
        vertices = calculate_sector_vertices(lat, lon, radius, azimuth, angle)
        marker_color = color_mapping.get(row[BCCH], '#000000')

        popup_content = "<div style='max-height: 200px; overflow-y: auto;'>"
        for column in uploaded_data.columns:
                # Add HTML formatting for each column value
            popup_content += f"<b>{column}:</b> {{{column}}}<br>"
        popup_content += "</div>"

            # Create a Folium Polygon to represent the sector with the assigned color
        folium.Polygon(
            locations=vertices,
            color='#000000',  # Black border color of the sector
            fill=True,
            fill_color=marker_color,  # Fill color of the sector
            fill_opacity=0.5,
            weight=2,  # Border weight
            popup=popup_content.format(**row),  # Pass the entire row to format method for dynamic content
        ).add_to(bcch_feature_groups[row[BCCH]])
    # Add Heatmap layer to the map
    heatmap_data = [[row[LAT], row[LONG]] for index, row in df.iterrows()]
    HeatMap(heatmap_data, radius=20, gradient={0.2: 'blue', 0.4: 'lime', 0.6: 'orange', 1: 'red'}, opacity=0.5).add_to(m)
    # Add marker and BCCH feature groups to the map
    for feature_group in bcch_feature_groups.values():
        feature_group.add_to(m)

    # Add layer control to the map with BCCH filtering options
    folium.LayerControl().add_to(m)

    # # Display the map
    # map_content = m.get_root().render()
    
    # Render the map to HTML
    map_content = m._repr_html_()

    return jsonify({'map_content': map_content, 'site_ids': site_ids})

# TODO: Download Map
@nbr_blueprint.route('/download_map')
def download_map():
    try:
        filename = request.args.get('file')
        if filename:
            # Provide the option to download the generated map with the same name as the input file
            map_filename = os.path.join(output_folder, filename + "_map.html")
            return send_file(map_filename, as_attachment=True)
        else:
            return "File not found."
    except Exception as e:
        return f"An error occurred: {str(e)}"

# TODO: Plan NBR Page
@nbr_blueprint.route('/plan_nbr', methods=['GET', 'POST'])
def plan_nbr():
    global uploaded_data, nbr_relations_df, uploaded_filename
    if uploaded_data is not None:
        # Read the data from the uploaded file
        df = uploaded_data.copy()

        # Your NBR plan generation code here
        cols = df.columns.tolist()

        mmfc = df.copy()
        plan = pd.DataFrame()
        final = pd.DataFrame(columns=cols)
        result = pd.DataFrame()

        plan = pd.concat([plan, df[df['NBR Plan'] != 'Yes']])

        df3 = pd.DataFrame()

        for Cell_id, Site_id, long_a, lat_a, azi_a in zip(plan[SECTOR_ID], plan[SITE_ID], plan[LONG], plan[LAT], plan[AZIMUTH]):
            Dist = []

            for long_b, lat_b in zip(mmfc[LONG], mmfc[LAT]):
                d = 108 * (math.sqrt((long_a - long_b) ** 2 + (lat_a - lat_b) ** 2))
                Dist.append(d)

            mmfc["Distance"] = Dist
            Dist = []

            mmfc = mmfc.sort_values(by='Distance')

            StoS = []
            StoS_final = []
            StoA = []
            StoA_final = []
            StoB = []
            StoB_final = []
            Azi = []
            Grade = []

            for long_b, lat_b, azi_b in zip(mmfc[LONG], mmfc[LAT], mmfc[AZIMUTH]):
                n = math.degrees(math.atan2(lat_b - lat_a, long_b - long_a))
                StoS.append(n)

                m = -90 - int(n) if n <= -90 else 270 - int(n)
                StoS_final.append(m)

                p = 360 + (azi_b - m) if m > azi_b else azi_b - m
                StoA.append(p)

                q = 360 - p if p > 180 else p
                StoA_final.append(q)

                r = 360 + (azi_a - m) if m > azi_a else azi_a - m
                StoB.append(r)

                s = r - 180 if r > 180 else 180 - r
                StoB_final.append(s)

                t = 10 if (s + q) < 10 else s + q
                Azi.append(t)

                x = d * t
                Grade.append(x)

            mmfc["S to S"] = StoS
            mmfc["S to S Final"] = StoS_final
            mmfc["S to A"] = StoA
            mmfc["S to A Final"] = StoA_final
            mmfc["S to B"] = StoB
            mmfc["S to B Final"] = StoB_final
            mmfc["Azi"] = Azi
            mmfc["Grade"] = Grade

            StoS = []
            StoS_final = []
            StoA = []
            StoA_final = []
            StoB = []
            StoB_final = []
            Azi = []
            Grade = []

            mmfc = mmfc.sort_values (by ='Grade')

            df2 = pd.DataFrame()  # AZIMUTH,  LAT, LONG, SECTOR_ID, SITE_ID
            df2 = mmfc[[SECTOR_ID, SITE_ID, 'Distance', 'Azi', 'Grade']].copy().iloc[:25]
            df2["Cell ID(Plan)"] = Cell_id
            df2["Site ID(Plan)"] = Site_id

            df3 = pd.concat([df3, df2])

        selected_columns = ['Cell ID(Plan)', 'Site ID(Plan)', SECTOR_ID, SITE_ID, 'Distance', 'Azi', 'Grade']
        df4 = df3[selected_columns]

        # Define a list to store the NBR relations
        nbr_relations = []

        # Iterate through the DataFrame rows
        for index, row in df.iterrows():
            lat_a, lon_a = float(row[LAT]), float(row[LONG])
            azimuth_a = float(row[AZIMUTH])

            for _, neighbor_row in df.iterrows():
                lat_b, lon_b = float(neighbor_row[LAT]), float(neighbor_row[LONG])

                # Calculate the distance between cell A and cell B
                distance = 108 * (math.sqrt((lon_a - lon_b) ** 2 + (lat_a - lat_b) ** 2))

                # Calculate the azimuth difference between cell A and cell B
                azimuth_diff = abs(azimuth_a - neighbor_row[AZIMUTH])

                Grade = abs(distance * azimuth_diff)

                # Check if cell B is a neighbor of cell A based on your criteria
                # You can adjust the criteria as needed
                if distance < 10 and azimuth_diff < 30:
                    # Append the NBR relation as a dictionary
                    nbr_relations.append({
                        'Cell A ID': row[SECTOR_ID],
                        'Cell B ID': neighbor_row[SECTOR_ID],
                        'Distance': distance,
                        'Azimuth Difference': azimuth_diff,
                        'Grade': Grade
                    })

        # Convert the list of NBR relations to a DataFrame
        nbr_relations_df = pd.DataFrame(nbr_relations)

        # Provide the option to download the NBR relations with the same name as the input file
        nbr_filename = os.path.join(output_folder, f"{remove_extension(uploaded_filename)}_NBR_Relations.xlsx")
        nbr_relations_df.to_excel(nbr_filename, index=False)

        # Convert the NBR relations DataFrame to an HTML table
        nbr_download_link = "/download_nbr_relations"
        nbr_content = nbr_relations_df.to_html(classes='table table-striped', escape=False)

        # Render the NBR template with the NBR content
        return render_template('nbr_relations.html', nbr_content=nbr_content, nbr_download_link=f"/download_nbr_relations?file={remove_extension(uploaded_filename)}")
    else:
        return "Upload a file first"

# TODO: BCCH Analysis Page    
@nbr_blueprint.route('/plan_bcch', methods=['GET', 'POST'])
def calculate_distances_azimuth_and_grade():
    global uploaded_data, AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID,uploaded_filename

    if uploaded_data is not None:
        if request.method == 'POST':
        # Get form data
            AZIMUTH = request.form['azi']
            BCCH = request.form['bcch']
            LAT = request.form['lat']
            LONG = request.form['long']
            SECTOR_ID = request.form['sector_id']
            SITE_ID = request.form['site_id']

        
        # Convert the column to numeric with errors='coerce' to replace non-numeric values with NaN
        uploaded_data[AZIMUTH] = pd.to_numeric(uploaded_data[AZIMUTH], errors='coerce')

        # Replace NaN values (non-numeric) with 0
        uploaded_data[AZIMUTH].fillna(0, inplace=True)

        # Convert the entire column to integer type
        uploaded_data[AZIMUTH] = uploaded_data[AZIMUTH].astype(int)
        
        plan = uploaded_data.copy()
        
        final_dfs = []

        for _, filtered_plan in plan.groupby(BCCH):

            # filtered_plan['key'] = 0
            # cartesian_product = pd.merge(filtered_plan, filtered_plan, on='key').drop('key', axis=1)
            cartesian_product = filtered_plan.merge(filtered_plan, how='cross')
            cartesian_product = cartesian_product[(cartesian_product[SITE_ID + '_x'] != cartesian_product[SITE_ID + '_y']) & (cartesian_product[SITE_ID + '_x'] < cartesian_product[SITE_ID + '_y'])]
            
            cartesian_product['Distance'] = 108 * np.sqrt((cartesian_product[LONG + '_x'] - cartesian_product[LONG + '_y']) ** 2 + (cartesian_product[LAT + '_x'] - cartesian_product[LAT + '_y']) ** 2)

            n = np.degrees(np.arctan2(cartesian_product[LAT + '_y'] - cartesian_product[LAT + '_x'], cartesian_product[LONG + '_y'] - cartesian_product[LONG + '_x']))
            m = np.where(n <= -90, -90 - n, 270 - n)
            p = np.where(m > cartesian_product[AZIMUTH + '_y'], 360 + cartesian_product[AZIMUTH + '_y'] - m, cartesian_product[AZIMUTH + '_y'] - m)
            q = np.where(p > 180, 360 - p, p)
            r = np.where(m > cartesian_product[AZIMUTH + '_x'], 360 + cartesian_product[AZIMUTH + '_x'] - m, cartesian_product[AZIMUTH + '_x'] - m)
            s = np.where(r > 180, r - 180, 180 - r)
            t = np.where((s + q) < 10, 10, s + q)
            
            cartesian_product['Azi'] = t 
            cartesian_product['Grade'] = cartesian_product['Distance'] * t

            cartesian_product = cartesian_product[(cartesian_product['Distance'] < 35)]
            cartesian_product = cartesian_product[[BCCH+'_x', SITE_ID+'_x', SECTOR_ID+'_x', LONG+'_x', LAT+'_x', SITE_ID+'_y', SECTOR_ID+'_y', 'Azi', 'Distance', 'Grade']]
            cartesian_product = cartesian_product.rename(columns={
                BCCH + '_x': BCCH,
                SITE_ID + '_x': SITE_ID,
                SECTOR_ID + '_x': SECTOR_ID,
                LONG + '_x': LONG,
                LAT + '_x': LAT,
                SITE_ID + '_y': 'Site ID(Plan)',
                SECTOR_ID + '_y': 'Sector (Plan)'
            })
            # top_3_df = cartesian_product.groupby([BCCH])
            # print(cartesian_product)
            final_dfs.append(cartesian_product)

        # Sort the DataFrame by 'Grade'
        bcch_analysis_df = pd.concat(final_dfs, ignore_index=True).sort_values(by='Grade', ascending=True)

        bcch_analysis_df[['Azi', 'Distance', 'Grade']] = bcch_analysis_df[['Azi', 'Distance', 'Grade']].round(2)

        # Extract 100 rows from the sorted DataFrame
        bcch_df_html = bcch_analysis_df.head(100).reset_index(drop=True)
        bcch_content = bcch_df_html.to_html(classes='table table-striped', escape=False, index=False)
        
        if uploaded_filename:
            bcch_analysis_filename = os.path.join(output_folder, f"{remove_extension(uploaded_filename)}_BCCH_Analysis.xlsx")
            bcch_analysis_df.to_excel(bcch_analysis_filename, index=False)
            
            # Convert the BCCH Analysis DataFrame to an HTML table
            bcch_download_link = f"/download_bcch_analysis?file={remove_extension(uploaded_filename)}"

            # Render the BCCH template with the BCCH content
            return render_template('bcch_analysis.html', bcch_content=bcch_content, bcch_download_link=bcch_download_link)
        else:
            # Handle the case when uploaded_filename does not exist
            return render_template('bcch_analysis.html', bcch_content=bcch_content)

    else:
        return "Upload a file first"

# TODO: PCI Analysis    
@nbr_blueprint.route('/plan_PCI', methods=['GET', 'POST'])
def CalculatePCI():
    global uploaded_data, AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID,EarfcnDL

    if uploaded_data is not None:
        if request.method == 'POST':
        # Get form data
            AZIMUTH = request.form['azi']
            BCCH = request.form['bcch']
            LAT = request.form['lat']
            LONG = request.form['long']
            SECTOR_ID = request.form['sector_id']
            SITE_ID = request.form['site_id']
            EarfcnDL = request.form['freq']

    # Assuming uploaded_data is defined earlier
        uploaded_data[AZIMUTH] = pd.to_numeric(uploaded_data[AZIMUTH], errors='coerce')
        uploaded_data[AZIMUTH].fillna(0, inplace=True)
        uploaded_data[AZIMUTH] = uploaded_data[AZIMUTH].astype(int)

        plan = uploaded_data.copy()
        final_dfs_pci = []

        for _, filtered_plan in plan.groupby([BCCH]):  # Group by both PCI and EarfcnDL
            cartesian_product = filtered_plan.merge(filtered_plan, how='cross')
            cartesian_product = cartesian_product[(cartesian_product[SITE_ID + '_x'] != cartesian_product[SITE_ID + '_y']) & (cartesian_product[SITE_ID + '_x'] < cartesian_product[SITE_ID + '_y'])]

            cartesian_product['Distance'] = 108 * np.sqrt((cartesian_product[LONG + '_x'] - cartesian_product[LONG + '_y']) ** 2 + (cartesian_product[LAT + '_x'] - cartesian_product[LAT + '_y']) ** 2)

            n = np.degrees(np.arctan2(cartesian_product[LAT + '_y'] - cartesian_product[LAT + '_x'], cartesian_product[LONG + '_y'] - cartesian_product[LONG + '_x']))
            m = np.where(n <= -90, -90 - n, 270 - n)
            p = np.where(m > cartesian_product[AZIMUTH + '_y'], 360 + cartesian_product[AZIMUTH + '_y'] - m, cartesian_product[AZIMUTH + '_y'] - m)
            q = np.where(p > 180, 360 - p, p)
            r = np.where(m > cartesian_product[AZIMUTH + '_x'], 360 + cartesian_product[AZIMUTH + '_x'] - m, cartesian_product[AZIMUTH + '_x'] - m)
            s = np.where(r > 180, r - 180, 180 - r)
            t = np.where((s + q) < 10, 10, s + q)

            cartesian_product['Azi'] = t
            cartesian_product['Grade'] = cartesian_product['Distance'] * t

            cartesian_product = cartesian_product[(cartesian_product['Distance'] < 10)]
            cartesian_product = cartesian_product[[BCCH + '_x', SITE_ID + '_x', SECTOR_ID + '_x', LONG + '_x', LAT + '_x', AZIMUTH + '_x', EarfcnDL + '_x',BCCH + '_y',SITE_ID + '_y', SECTOR_ID + '_y',EarfcnDL + '_y', 'Azi', 'Distance', 'Grade']]

            # Identify conflicts based on PCI and EarfcnDL
            cartesian_product['Conflict'] = np.where((cartesian_product[BCCH + '_x'] == cartesian_product[BCCH + '_y']) & (cartesian_product[EarfcnDL + '_x'] == cartesian_product[EarfcnDL + '_y']), 'Conflict', 'No Conflict')

            # Renaming columns after merge
            cartesian_product = cartesian_product.rename(columns={
                BCCH + '_x': BCCH,
                SITE_ID + '_x': SITE_ID,
                SECTOR_ID + '_x': SECTOR_ID,
                LONG + '_x': LONG,
                LAT + '_x': LAT,
                AZIMUTH + '_x': AZIMUTH,
                SITE_ID + '_y': 'Site ID(Plan)',
                SECTOR_ID + '_y': 'Sector (Plan)',
                BCCH + '_y': 'PCI (Plan)',  # Rename the PCI column of the merged plan DataFrame
                EarfcnDL + '_x': EarfcnDL,  # Rename the EarfcnDL column of the main DataFrame
                EarfcnDL + '_y': 'EarfcnDL (Plan)'  # Rename the EarfcnDL column of the merged plan DataFrame
            })

            final_dfs_pci.append(cartesian_product)

        PCI_analysis_df = pd.concat(final_dfs_pci, ignore_index=True).sort_values(by='Grade', ascending=True)
        conflict_sites_df = PCI_analysis_df[PCI_analysis_df['Conflict'] == 'Conflict']
        conflict_sites_df_html = conflict_sites_df.head(100).reset_index(drop=True)
        pci_content = conflict_sites_df_html.to_html(classes='table table-striped', escape=False)
        return render_template('bcch_analysis.html',pci_content=pci_content, bcch_download_link=f"/download_bcch_analysis?file={remove_extension(uploaded_filename)}")
    else:
        return "Upload a file first"

# TODO: PSC Analysis    
@nbr_blueprint.route('/plan_PSC', methods=['GET', 'POST'])
def CalculatePSC():
    global uploaded_data, AZIMUTH, BCCH, LAT, LONG, SECTOR_ID, SITE_ID,UarfcnDL

    if uploaded_data is not None:
        if request.method == 'POST':
        # Get form data
            AZIMUTH = request.form['azi']
            BCCH = request.form['bcch']
            LAT = request.form['lat']
            LONG = request.form['long']
            SECTOR_ID = request.form['sector_id']
            SITE_ID = request.form['site_id']
            UarfcnDL = request.form['freq']


    # Assuming uploaded_data is defined earlier
        uploaded_data[AZIMUTH] = pd.to_numeric(uploaded_data[AZIMUTH], errors='coerce')
        uploaded_data[AZIMUTH].fillna(0, inplace=True)
        uploaded_data[AZIMUTH] = uploaded_data[AZIMUTH].astype(int)

        plan = uploaded_data.copy()
        final_dfs_pci = []

        for _, filtered_plan in plan.groupby([BCCH]):  # Group by both PCI and EarfcnDL
            cartesian_product = filtered_plan.merge(filtered_plan, how='cross')
            cartesian_product = cartesian_product[(cartesian_product[SITE_ID + '_x'] != cartesian_product[SITE_ID + '_y']) & (cartesian_product[SITE_ID + '_x'] < cartesian_product[SITE_ID + '_y'])]

            cartesian_product['Distance'] = 108 * np.sqrt((cartesian_product[LONG + '_x'] - cartesian_product[LONG + '_y']) ** 2 + (cartesian_product[LAT + '_x'] - cartesian_product[LAT + '_y']) ** 2)

            n = np.degrees(np.arctan2(cartesian_product[LAT + '_y'] - cartesian_product[LAT + '_x'], cartesian_product[LONG + '_y'] - cartesian_product[LONG + '_x']))
            m = np.where(n <= -90, -90 - n, 270 - n)
            p = np.where(m > cartesian_product[AZIMUTH + '_y'], 360 + cartesian_product[AZIMUTH + '_y'] - m, cartesian_product[AZIMUTH + '_y'] - m)
            q = np.where(p > 180, 360 - p, p)
            r = np.where(m > cartesian_product[AZIMUTH + '_x'], 360 + cartesian_product[AZIMUTH + '_x'] - m, cartesian_product[AZIMUTH + '_x'] - m)
            s = np.where(r > 180, r - 180, 180 - r)
            t = np.where((s + q) < 10, 10, s + q)

            cartesian_product['Azi'] = t
            cartesian_product['Grade'] = cartesian_product['Distance'] * t

            cartesian_product = cartesian_product[(cartesian_product['Distance'] < 10)]
            cartesian_product = cartesian_product[[BCCH + '_x', SITE_ID + '_x', SECTOR_ID + '_x', LONG + '_x', LAT + '_x', AZIMUTH + '_x', UarfcnDL + '_x',BCCH + '_y',SITE_ID + '_y', SECTOR_ID + '_y',UarfcnDL + '_y', 'Azi', 'Distance', 'Grade']]

            # Identify conflicts based on PCI and EarfcnDL
            cartesian_product['Conflict'] = np.where((cartesian_product[BCCH + '_x'] == cartesian_product[BCCH + '_y']) & (cartesian_product[UarfcnDL + '_x'] == cartesian_product[UarfcnDL + '_y']), 'Conflict', 'No Conflict')

            # Renaming columns after merge
            cartesian_product = cartesian_product.rename(columns={
                BCCH + '_x': BCCH,
                SITE_ID + '_x': SITE_ID,
                SECTOR_ID + '_x': SECTOR_ID,
                LONG + '_x': LONG,
                LAT + '_x': LAT,
                AZIMUTH + '_x': AZIMUTH,
                SITE_ID + '_y': 'Site ID(Plan)',
                SECTOR_ID + '_y': 'Sector (Plan)',
                BCCH + '_y': 'PCI (Plan)',  # Rename the PCI column of the merged plan DataFrame
                UarfcnDL + '_x': UarfcnDL,  # Rename the EarfcnDL column of the main DataFrame
                UarfcnDL + '_y': 'UarfcnDL (Plan)'  # Rename the EarfcnDL column of the merged plan DataFrame
            })

            final_dfs_pci.append(cartesian_product)

        Psc_analysis_df = pd.concat(final_dfs_pci, ignore_index=True).sort_values(by='Grade', ascending=True)
        conflict_sites_psc_df = Psc_analysis_df[Psc_analysis_df['Conflict'] == 'Conflict']
        conflict_sites_psc_df_html = conflict_sites_psc_df.head(100).reset_index(drop=True)
        psc_content = conflict_sites_psc_df_html.to_html(classes='table table-striped', escape=False)
        return render_template('bcch_analysis.html',psc_content=psc_content, bcch_download_link=f"/download_bcch_analysis?file={remove_extension(uploaded_filename)}")
    else:
        return "Upload a file first"


# TODO: Download BCCH anaysis 
@nbr_blueprint.route('/download_bcch_analysis')
def download_bcch_analysis():
    try:
        filename = request.args.get('file')
        if filename:
            # Provide the option to download the NBR relations Excel file with the same name as the input file
            bcch_analysis_filename = os.path.join(output_folder, f"{filename}_BCCH_Analysis.xlsx")
            return send_file(bcch_analysis_filename, as_attachment=True)
        else:
            return "File not found."
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Download NBR Analysis
@nbr_blueprint.route('/download_nbr_relations')
def download_nbr_relations():
    try:
        filename = request.args.get('file')
        if filename:
            # Provide the option to download the NBR relations Excel file with the same name as the input file
            nbr_filename = os.path.join(output_folder, f"{filename}_NBR_Relations.xlsx")
            return send_file(nbr_filename, as_attachment=True)
        else:
            return "File not found."
    except Exception as e:
        return f"An error occurred: {str(e)}"


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


