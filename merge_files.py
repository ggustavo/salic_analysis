import os
import pandas as pd
import csv

# Increase the field size limit
csv.field_size_limit(2147483647)

def merge_csv_files(directory, output_directory, output_filename, tipo):
    # Create output directory if it does not exist
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # List to store dataframes
    dataframes = []
    # List to store inconsistent lines
    inconsistent_rows = []

    # Loop through all files in the directory
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    header = next(reader)  # Read the header
                    num_columns = len(header)

                    valid_rows = []
                    
                    for i, row in enumerate(reader):
                        if len(row) == num_columns:
                            valid_rows.append(row)
                        else:
                            inconsistent_rows.append((filename, i + 2, row))  # Store file, line and line

                if valid_rows:
                    df = pd.DataFrame(valid_rows, columns=header)
                    dataframes.append(df)

            except pd.errors.ParserError as e:
                print(f"Error parsing {file_path}: {e}")
            except csv.Error as e:
                print(f"CSV error in file {file_path}: {e}")

    if dataframes:
        # Concatenate all dataframes
        merged_df = pd.concat(dataframes, ignore_index=True)

        # Save the concatenated dataframe to a new CSV file
        output_file_path = os.path.join(output_directory, output_filename)
        merged_df.to_csv(output_file_path, index=False, encoding='utf-8')
        print(f"Merged file created: {output_file_path}")
    else:
        print("No valid CSV files found to merge.")

    if inconsistent_rows:
        # Save inconsistent lines to a new CSV file
        inconsistent_output_path = os.path.join(output_directory, f"inconsistent_{tipo}.csv")
        with open(inconsistent_output_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Filename', 'Line Number', 'Row Data'])  # Write the header to the inconsistencies file
            for row in inconsistent_rows:
                writer.writerow(row)
        print(f"Inconsistent rows logged in: {inconsistent_output_path}")

# Main directory where CSV files are stored
main_directory = "fragmented_files"

# Output directory for merged files
output_directory = "merged_files"

# Call the merge csv files function for each data type
merge_csv_files(os.path.join(main_directory, "projetos"), output_directory, "projetos.csv", "projetos")
merge_csv_files(os.path.join(main_directory, "incentivadores"), output_directory, "incentivadores.csv", "incentivadores")
merge_csv_files(os.path.join(main_directory, "fornecedores"), output_directory, "fornecedores.csv", "fornecedores")
merge_csv_files(os.path.join(main_directory, "proponentes"), output_directory, "proponentes.csv", "proponentes")
merge_csv_files(os.path.join(main_directory, "propostas"), output_directory, "propostas.csv", "propostas")
