# SALIC Analysis

This project aims to analyze data from the Brazilian government's SALIC (Sistema de Apoio às Leis de Incentivo à Cultura) system.

## Project Structure

- `dump_fragmented_files.py`: This script downloads SALIC data in CSV format, storing the data in fragmented files organized into directories.
- `merge_files.py`: This script reads the fragmented CSV files from each directory and merges them into single CSV files per data type.

## Requirements

- Python 3.12 or higher
- `virtualenv` for creating virtual environments

## Setting Up the Environment

1. **Clone the Repository:**
   - Clone the repository to your local machine:
     ```bash
     git clone https://github.com/ggustavo/salic_analysis.git
     cd salic_analysis
     ```

2. **Create a Virtual Environment:**
   - Inside the project directory, create a virtual environment:
     ```bash
     virtualenv venv
     ```

3. **Activate the Virtual Environment:**
   - Activate the virtual environment with the appropriate command for your operating system:
     - On Windows:
       ```bash
       .\venv\Scripts\activate
       ```
     - On macOS and Linux:
       ```bash
       source venv/bin/activate
       ```

4. **Install Dependencies:**
   - Install the dependencies listed in `requirements.txt`:
     ```bash
     pip install -r requirements.txt
     ```

## Running the Scripts

### dump_fragmented_files.py

This script downloads data from the SALIC system and stores it in fragmented CSV files.

1. **Run the Script:**
   - With the virtual environment activated, run the script:
     ```bash
     python dump_fragmented_files.py
     ```

2. **Script Description:**
   - The script creates a main directory `fragmented_files` to store the data.
   - Inside this directory, it creates subdirectories for each data type (`projetos`, `incentivadores`, `fornecedores`, `proponentes`, `propostas`).
   - It downloads the data in chunks of 100 records at a time, saving each chunk as a fragmented CSV file.

### merge_files.py

This script merges the fragmented CSV files from each folder into a single CSV file per data type.

1. **Run the Script:**
   - With the virtual environment activated, run the script:
     ```bash
     python merge_files.py
     ```

2. **Script Description:**
   - The script reads the fragmented CSV files from each subdirectory inside `fragmented_files`.
   - It merges all CSV files from each subdirectory into a single CSV file.
   - The resulting CSV files are saved in a directory called `merged_files`.
