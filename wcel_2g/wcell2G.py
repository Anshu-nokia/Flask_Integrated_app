__author__ = "Najmul"

import pandas as pd
from openpyxl import load_workbook
from sqlalchemy import create_engine, text
from openpyxl.utils import get_column_letter
import time
from datetime import datetime, timedelta
from openpyxl.utils import FORMULAE
import sys



# Get the current date and time
now = datetime.now()
today = datetime.now().date()
print(today)
last_day = today - timedelta(days=1)
last_day_date = last_day.strftime('%d-%b-%y')
last_day_month = last_day.strftime('%d-%b')




start_time = time.time()
engine = create_engine('postgresql://postgres:12345@10.133.132.90:5432/cno_prod')
conn = engine.connect()
# Define the SQL query to select the maximum index number
sql_query = text(f"SELECT * FROM \"{'ZM_2G_BBHnew'}\" WHERE \"{'Date'}\"  >= CURRENT_DATE - INTERVAL '1 day' AND \"{'Date'}\"  < CURRENT_DATE;")
df = pd.read_sql(sql_query, conn)
print(df.head(3).to_string(), df['Date'].unique())

###checking Database data and tracker lastdate
df_chk = pd.read_excel(r"/home/CNO_Server/scripts/Wcell_2G_Tracker/ZM_2G_WCL.xlsm", index_col=False, sheet_name="CSSR", skiprows=4)
column_name = df_chk.columns[36]
column_name = pd.to_datetime(column_name)
column_name = column_name.strftime('%d-%b-%y')
if df.empty or column_name == last_day_date:
    print("DataFrame is empty or Tracker already updated. Exiting...")
    sys.exit()  # This will terminate the program

existing_file_path = r"/home/CNO_Server/scripts/Wcell_2G_Tracker/ZM_2G_WCL.xlsm"
df.rename(columns={'Element3': 'Cell ID'}, inplace=True)
# df['Cell ID'] = df['Cell ID'].str.upper()
df['Cell ID'] = df['Cell ID'].astype(str)
#-----loading workbook----------------
wb_existing = load_workbook(existing_file_path, read_only=False, keep_vba=True, keep_links=True)
#-------creating Dict key = counter, value = sheet name
sheet_dict = {'CSSR': 'CSSR',
              'TCH_DROP': 'TCH_Drop',
              'SDCCH_DROP': 'SDCCH_Drop',
              'SDCCH_BLOCKING': 'SDCCH_Cong',
              'TCH_BLOCKING_USER_PERCEIVED': 'TCH_Cong',
              'NETWORK_AVAILABILTY' : 'RNA_BBH'}
# Iterate over the dictionary using a for loop
for key, value in sheet_dict.items():
    sheet_name = wb_existing[value]
    print(f"Updating {value}...")
    source_columns = range(8, 38)  # Assuming (30 columns)
    target_columns = range(7, 37)  # Assuming (30 columns)
    # Find the last row in column J
    last_row = sheet_name.max_row
    print("Last_Row: ", last_row)
    df1 = pd.read_excel(existing_file_path, skiprows=4,
                        sheet_name=value)
    # print(df1.columns)
    # Remove leading and trailing whitespaces from column names
    # df1.columns = df1.columns.str.strip()
    # df1['Cell ID'] = df1['Cell ID'].str.upper()
    df1['Cell ID'] = df1['Cell ID'].astype(str)

    print("Shifting Column....")
    for row_index in range(5, last_row):
        # print("Row index: ",row_index)
        for source_col, target_col in zip(source_columns, target_columns):
            # Access source cell
            source_cell = sheet_name.cell(row=row_index, column=source_col)
            # Access target cell
            target_cell = sheet_name.cell(row=row_index, column=target_col)
            # Copy the value
            target_cell.value = source_cell.value

    # Merge based on the 'ID' column
    merged_df = pd.merge(df, df1, on='Cell ID', how='right')
    merged_df = merged_df[['Date', 'Cell ID', key]]
    column_number = 2
    # Rename the column
    merged_df.rename(columns={merged_df.columns[column_number]: last_day_date}, inplace=True)
    # merged_df.to_excel(rf"C:\WCELL\2G\\sample{key}.xlsx", index=False)
    column_data = merged_df.iloc[:, column_number].tolist()
    target_col = 'AK'  # Replace with your target column letter
    start_row = 6  # Change this to your starting row
    # Write the column data to the specified location in the Excel sheet
    column_name = merged_df.columns[column_number]
    cell = sheet_name[f'{target_col}{5}']
    cell.value = column_name
    # print(cell.value )
    for i, value in enumerate(column_data):
        cell = sheet_name[f'{target_col}{start_row + i}']
        cell.value = value

    last_row = len(df1) + 6
    # print(last_row)
    # Merge DataFrames based on 'Site Name' column
    merged_df = pd.merge(df1, df, on='Cell ID', how='right', indicator=True)
    # print(merged_df.head(2).to_string())
    # Filter rows where the merge indicator is 'left_only'
    non_matching_sites = merged_df.loc[merged_df['_merge'] == 'right_only', ['Cell ID', key]]
    ###----------------------------------------------------------------------------
    # Display the missing site names
    # print("Site names in df that are not present in df1:")
    # print(non_matching_sites.to_string())
    if non_matching_sites.empty:
        pass
    else:
        print("Updating New Cells..", non_matching_sites)
        column_numbers = [0, 1]
        target_columns = ['A', 'AK']
        for column_number, target_col in zip(column_numbers, target_columns):
            column_data = non_matching_sites.iloc[:, column_number].tolist()
            start_row = last_row  # Change this to your starting row
            for i, value in enumerate(column_data):
                cell = sheet_name[f'{target_col}{start_row + i}']
                cell.value = value
                
                

##----------for trafic and Cell Utilizations---------------

sheet_dict = {'TOTAL_TRAFFIC_ERLANGS': 'Traffic',
              'CELL_UTILIZATION': 'Cell Utilization',
              }
# Iterate over the dictionary using a for loop
for key, value in sheet_dict.items():
    sheet_name = wb_existing[value]
    print(f"Updating {value}...")
    source_columns = range(7, 37)  # Assuming (30 columns)
    target_columns = range(6, 36)  # Assuming (30 columns)
    # Find the last row in column J
    last_row = sheet_name.max_row
    print("Last_Row: ", last_row)
    if value == 'Traffic':
        df1 = pd.read_excel(existing_file_path,
                            sheet_name=value)
        start_row = 2
    elif value == 'Cell Utilization':
        df1 = pd.read_excel(existing_file_path, skiprows=1,
                            sheet_name=value)
        start_row = 3
    # print(df1.columns)
    # Remove leading and trailing whitespaces from column names
    # df1.columns = df1.columns.str.strip()
    # df1['Cell ID'] = df1['Cell ID'].str.upper()
    df1['Cell ID'] = df1['Cell ID'].astype(str)

    print("Shifting Column....")
    for row_index in range(start_row -1, last_row):
        # print("Row index: ",row_index)
        for source_col, target_col in zip(source_columns, target_columns):
            # Access source cell
            source_cell = sheet_name.cell(row=row_index, column=source_col)
            # Access target cell
            target_cell = sheet_name.cell(row=row_index, column=target_col)
            # Copy the value
            target_cell.value = source_cell.value

    # Merge based on the 'ID' column
    merged_df = pd.merge(df, df1, on='Cell ID', how='right')
    merged_df = merged_df[['Date', 'Cell ID', key]]
    column_number = 2
    # Rename the column
    merged_df.rename(columns={merged_df.columns[column_number]: last_day_month}, inplace=True)
    # merged_df.to_excel(rf"C:\wcell\zm\2g\\sample{key}.xlsx", index=False)
    column_data = merged_df.iloc[:, column_number].tolist()
    target_col = 'AJ'  # Replace with your target column letter
    # start_row = 6  # Change this to your starting row
    # Write the column data to the specified location in the Excel sheet
    column_name = merged_df.columns[column_number]
    cell = sheet_name[f'{target_col}{start_row - 1}']
    cell.value = column_name
    # print(cell.value )
    for i, value in enumerate(column_data):
        cell = sheet_name[f'{target_col}{start_row + i}']
        cell.value = value

    # last_row = len(df1) + 6
    # print(last_row)
    # Merge DataFrames based on 'Site Name' column

    merged_df = pd.merge(df1, df, on='Cell ID', how='right', indicator=True)
    # print(merged_df.head(2).to_string())
    # Filter rows where the merge indicator is 'left_only'
    non_matching_sites = merged_df.loc[merged_df['_merge'] == 'right_only', ['Cell ID', key]]
    ###----------------------------------------------------------------------------
    # Display the missing site names
    # print("Site names in df that are not present in df1:")
    # print(non_matching_sites.to_string())
    if non_matching_sites.empty:
        pass
    else:
        print("Updating New Cells..", non_matching_sites)
        column_numbers = [0, 1]
        target_columns = ['B', 'AJ']
        for column_number, target_col in zip(column_numbers, target_columns):
            column_data = non_matching_sites.iloc[:, column_number].tolist()
            start_row = last_row - 2  # Change this to your starting row
            for i, value in enumerate(column_data):
                cell = sheet_name[f'{target_col}{start_row + i}']
                cell.value = value







##------------------------------------------------
###-----------Updating AP and BK Columns---------------------------------
##-------------------------------------------------

kpi_dict = {'CSSR_Fail': 'CSSR',
    'TCH_DROP_NOM': 'TCH_Drop',
            'SDCCH_DROP_NOM': 'SDCCH_Drop',
            'SDCCH_BLOCKING_NOM': 'SDCCH_Cong',
            'TCH_BLOCKING_NOM': 'TCH_Cong'}
engine = create_engine('postgresql://postgres:12345@10.133.132.90:5432/cno_prod')
conn = engine.connect()
###--------------------for CSSR temp---------------------------------------
# Define the SQL query to select the maximum index number
sql_query = text(f"SELECT * FROM \"{'ZM_2G_BBH_Temp'}\" WHERE \"{'Date'}\"  >= CURRENT_DATE - INTERVAL '14 day' AND \"{'Date'}\"  < CURRENT_DATE;")
df = pd.read_sql(sql_query, conn)
# df.to_excel(r"C:\wcell\zm\2g\\last14.xlsx", index=False)
df.rename(columns={'Element3': 'Cell ID'}, inplace=True)
df['Cell ID'] = df['Cell ID'].str.upper()
df["CSSR_Fail"] = df["TCH_ASSIG_SUCCESS_RATE_DENOM"] - df["TCH_ASSIG_SUCCESS_RATE_NOM"]
last_day_data_cssr = df[df['Date'] == df['Date'].max()]
print("Last day: ", len(last_day_data_cssr))

###--------------------CSSR temp---------------------------------------

# Define the SQL query to select the maximum index number
sql_query = text(f"SELECT * FROM \"{'ZM_2G_BBHnew'}\" WHERE \"{'Date'}\"  >= CURRENT_DATE - INTERVAL '14 day' AND \"{'Date'}\"  < CURRENT_DATE;")
df_14 = pd.read_sql(sql_query, conn)
# df_14.to_excel(r"C:\wcell\zm\2g\\last14.xlsx", index=False)
df_14.rename(columns={'Element3': 'Cell ID'}, inplace=True)
df_14['Cell ID'] = df_14['Cell ID'].str.upper()
##-----------last day---------------------
# Then you can filter the DataFrame to get data for the last day
last_day_data = df_14[df_14['Date'] == df_14['Date'].max()]
print("Last day: ", len(last_day_data))

# Calculate the average for a specific column using groupby
for key, sheet in kpi_dict.items():
    ####Updating Ak---------------------------------------------------------
    if sheet == "CSSR":
        print("In CSSR")
        sheet_name = wb_existing[sheet]
        print(f"{sheet} Column AP Updating...")
        df_kpi = pd.read_excel(existing_file_path, skiprows=4,
                               sheet_name=sheet)
        avg_14 = df.groupby('Cell ID')[key].mean()
        # avg_14['Cell ID'] = avg_14['Cell ID'].str.upper()
        # avg_14.to_excel(r"C:\wcell\zm\2g\\"+key+".xlsx")
        # Merge based on the 'ID' column
        df_kpi['Cell ID'] = df_kpi['Cell ID'].astype(str)
        merged_df = pd.merge(avg_14, df_kpi, on='Cell ID', how='right')
        merged_df = merged_df[['Cell ID', key]]
        # merged_df.to_excel(rf"C:\wcell\zm\2g\\AK_{key}.xlsx", index=False)
        column_data = merged_df.iloc[:, 1].tolist()
        target_col = 'AP'  # Replace with your target column letter
        start_row = 6  # Change this to your starting row
        cell = sheet_name[f'{target_col}{5}']
        # cell.value = column_name
        # print(cell.value )
        for i, value in enumerate(column_data):
            cell = sheet_name[f'{target_col}{start_row + i}']
            cell.value = value
    else:

        sheet_name = wb_existing[sheet]
        print(f"{sheet} Column AP Updating...")
        df_kpi = pd.read_excel(existing_file_path, skiprows=4,
                            sheet_name=sheet)
        avg_14 = df_14.groupby('Cell ID')[key].mean()
        # avg_14['Cell ID'] = avg_14['Cell ID'].str.upper()
        # avg_14.to_excel(r"C:\wcell\zm\2g\\"+key+".xlsx")
        # Merge based on the 'ID' column
        df_kpi['Cell ID'] = df_kpi['Cell ID'].astype(str)
        merged_df = pd.merge(avg_14, df_kpi, on='Cell ID', how='right')
        merged_df = merged_df[['Cell ID', key]]
        # merged_df.to_excel(rf"C:\wcell\zm\2g\\AK_{key}.xlsx", index=False)
        column_data = merged_df.iloc[:, 1].tolist()
        target_col = 'AP'  # Replace with your target column letter
        start_row = 6  # Change this to your starting row
        cell = sheet_name[f'{target_col}{5}']
        # cell.value = column_name
        # print(cell.value )
        for i, value in enumerate(column_data):
            cell = sheet_name[f'{target_col}{start_row + i}']
            cell.value = value

    ####Updating BK---------------------------------------------------------

    if sheet == "CSSR":
        print("In CSSR")
        # sheet_name = wb_existing[value]
        print(f"{sheet} Column BK Updating...")
        df_kpi = pd.read_excel(existing_file_path, skiprows=4,
                               sheet_name=sheet)
        avg_14 = last_day_data_cssr.groupby('Cell ID')[key].mean()
        # avg_14['Cell ID'] = avg_14['Cell ID'].str.upper()
        # avg_14.to_excel(r"C:\wcell\zm\2g\\"+key+".xlsx")
        # Merge based on the 'ID' column
        df_kpi['Cell ID'] = df_kpi['Cell ID'].astype(str)
        merged_df = pd.merge(avg_14, df_kpi, on='Cell ID', how='right')
        merged_df = merged_df[['Cell ID', key]]
        # merged_df.to_excel(rf"C:\wcell\zm\2g\\BK_{key}.xlsx", index=False)
        column_data = merged_df.iloc[:, 1].tolist()
        target_col = 'BK'  # Replace with your target column letter
        start_row = 6  # Change this to your starting row
        cell = sheet_name[f'{target_col}{5}']
        # cell.value = column_name
        # print(cell.value )
        for i, value in enumerate(column_data):
            cell = sheet_name[f'{target_col}{start_row + i}']
            cell.value = value
    else:
        # sheet_name = wb_existing[value]
        print(f"{sheet} Column BK Updating...")
        df_kpi = pd.read_excel(existing_file_path, skiprows=4,
                            sheet_name=sheet)
        avg_14 = last_day_data.groupby('Cell ID')[key].mean()
        # avg_14['Cell ID'] = avg_14['Cell ID'].str.upper()
        # avg_14.to_excel(r"C:\wcell\zm\2g\\"+key+".xlsx")
        # Merge based on the 'ID' column
        df_kpi['Cell ID'] = df_kpi['Cell ID'].astype(str)
        merged_df = pd.merge(avg_14, df_kpi, on='Cell ID', how='right')
        merged_df = merged_df[['Cell ID', key]]
        # merged_df.to_excel(rf"C:\wcell\zm\2g\\BK_{key}.xlsx", index=False)
        column_data = merged_df.iloc[:, 1].tolist()
        target_col = 'BI'  # Replace with your target column letter
        start_row = 6  # Change this to your starting row
        cell = sheet_name[f'{target_col}{5}']
        # cell.value = column_name
        # print(cell.value )
        for i, value in enumerate(column_data):
            cell = sheet_name[f'{target_col}{start_row + i}']
            cell.value = value


                

##-----for RNA 24 Hr----------

# Define the SQL query to select the maximum index number
sql_query = text(f"SELECT * FROM \"{'ZM_2G_All_DAILYnew'}\" WHERE \"{'Date'}\"  >= CURRENT_DATE - INTERVAL '1 day' AND \"{'Date'}\"  < CURRENT_DATE;")
df = pd.read_sql(sql_query, conn)
# print(df.head(3).to_string(), df['Date'].unique())

# existing_file_path = r"C:\WCELL\2G\\ZM_2G_WCL_20240325.xlsm"
df1 = pd.read_excel(existing_file_path, skiprows=4,
                        sheet_name='RNA_24HR')
df.rename(columns={'Element3': 'Cell ID'}, inplace=True)
df['Cell ID'] = df['Cell ID'].str.upper()
# print(df1.columns)
# Remove leading and trailing whitespaces from column names
# df1.columns = df1.columns.str.strip()
# df1['Cell ID'] = df1['Cell ID'].str.upper()
df1['Cell ID'] = df1['Cell ID'].astype(str)
sheet_name = wb_existing['RNA_24HR']
print(f"Updating {'RNA_24HR'}...")
source_columns = range(8, 38)  # Assuming (30 columns)
target_columns = range(7, 37)  # Assuming (30 columns)
# Find the last row in column J
last_row = sheet_name.max_row
print("Last_Row: ", last_row)
print("Shifting Column....")
for row_index in range(5, last_row):
    # print("Row index: ",row_index)
    for source_col, target_col in zip(source_columns, target_columns):
        # Access source cell
        source_cell = sheet_name.cell(row=row_index, column=source_col)
        # Access target cell
        target_cell = sheet_name.cell(row=row_index, column=target_col)
        # Copy the value
        target_cell.value = source_cell.value

# Merge based on the 'ID' column
merged_df = pd.merge(df, df1, on='Cell ID', how='right')
merged_df = merged_df[['Date', 'Cell ID', 'NETWORK_AVAILABILTY']]
column_number = 2
# Rename the column
merged_df.rename(columns={merged_df.columns[column_number]: last_day_date}, inplace=True)
# merged_df.to_excel(r"C:\WCELL\2G\\sample_RNA_24HR.xlsx", index=False)
column_data = merged_df.iloc[:, column_number].tolist()
target_col = 'AK'  # Replace with your target column letter
start_row = 6  # Change this to your starting row
# Write the column data to the specified location in the Excel sheet
column_name = merged_df.columns[column_number]
cell = sheet_name[f'{target_col}{5}']
cell.value = column_name
# print(cell.value )
for i, value in enumerate(column_data):
    cell = sheet_name[f'{target_col}{start_row + i}']
    cell.value = value

last_row = len(df1) + 6
# print(last_row)
# Merge DataFrames based on 'Site Name' column
merged_df = pd.merge(df1, df, on='Cell ID', how='right', indicator=True)
# Filter rows where the merge indicator is 'left_only'
non_matching_sites = merged_df.loc[merged_df['_merge'] == 'right_only', ['Cell ID', 'NETWORK_AVAILABILTY']]
###----------------------------------------------------------------------------
# Display the missing site names
# print("Site names in df that are not present in df1:")
# print(non_matching_sites.to_string())
if non_matching_sites.empty:
    pass
else:
    print("Updating New Cells..", non_matching_sites)
    column_numbers = [0, 1]
    target_columns = ['A', 'AK']
    for column_number, target_col in zip(column_numbers, target_columns):
        column_data = non_matching_sites.iloc[:, column_number].tolist()
        start_row = last_row  # Change this to your starting row
        for i, value in enumerate(column_data):
            cell = sheet_name[f'{target_col}{start_row + i}']
            cell.value = value



# Save the workbook
wb_existing.save(existing_file_path)





end_time = time.time()
print("Time: ", end_time - start_time)
sys.exit(0)
