import mysql.connector
import mysql.connector.pooling
from mysql.connector import Error
import configparser
from tabulate import tabulate
import json
import csv
import types
import ast
from datetime import datetime
from csv import writer as wr
from decimal import Decimal
from pandas import DataFrame
import re
import os


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


def try_convert(value):
    try:
        # Try converting to int
        return int(value)
    except ValueError:
        try:
            # Try converting to float
            return float(value)
        except ValueError:
            try:
                # Try converting using ast.literal_eval
                return ast.literal_eval(value)
            except (SyntaxError, ValueError):
                # If conversion fails, return the original value
                return value


def read_db_config(filename='config_world.ini', section='mysql'):
    # Create a parser
    parser = configparser.ConfigParser()
    # Read config file
    parser.read(filename)

    # Get section, default to mysql
    db = {}
    if parser.has_section(section):
        items = parser.items(section)
        for item in items:
            db[item[0]] = item[1]
    else:
        raise Exception(f'{section} not found in the {filename} file')

    return db


def connect(filename='config_world.ini', verbose=False):
    """ Connect to MySQL database """

    db_config = read_db_config(filename)

    try:
        if verbose:
            print('Connecting to MySQL database...')
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            if verbose:
                print('Connection established.\n')
                print('--'*25 + '\n')
            return conn
    except Error as e:
        print(e)

    return None


def create_pool(config, pool_name, pool_size):
    try:
        return mysql.connector.pooling.MySQLConnectionPool(pool_name=pool_name,
                                                                pool_size=pool_size,
                                                                **config)
        print("Connection pool created successfully.")
    except Exception as e:
        print(f"Error creating connection pool: {e}")


def get_tables(conn):
    """ Retrieve the list of tables from MySQL database """
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        return tables

    except Error as e:
        print(e)

    return None


def show_tables(conn):
    # Connect to MySQL database
    if conn:
        # Get the list of tables
        tables = get_tables(conn)
        if tables:
            print("Tables in the database:")
            for table in tables:
                print(table[0])
            print('\n' + '--' * 25 + '\n')
        else:
            print("No tables found in the database.")


def get_columns(conn, table_name):
    """ Retrieve the columns of a table from MySQL database """
    try:
        cursor = conn.cursor()
        cursor.execute(f"SHOW COLUMNS FROM {table_name};")
        columns = cursor.fetchall()
        return columns
    except Error as e:
        print(e)


def show_columns(conn, table_name):
    # Connect to MySQL database
    if conn:
        # Get the list of tables
        columns = get_columns(conn, table_name)
        if columns:
            print(f"Columns in the {table_name}:")
            for column in columns:
                print(column[0])
            print('\n' + '--' * 25 + '\n')
        else:
            print("No tables found in the database.")


def section_brake():
    print("\n"+"--"*25+"\n")


class DataBase:

    def __init__(self, config: str, pool: bool = False, pool_size: int=1):
        """ Connects using config file """
        if not pool:
            self.conn = connect(config)
        else:
            pass


    def close(self):
        """ Closes connection """
        if self.conn.is_connected():
            self.conn.close()
            section_brake()
            print('Connection closed.')

    def get_tables(self, reset=True):
        """ Retrieve the list of tables from MySQL database """
        try:
            if reset:
                self.conn.reset_session()

            cursor = self.conn.cursor()
            cursor.execute("SHOW TABLES;")
            tables = cursor.fetchall()
            return tables

        except Error as e:
            print(e)
            return None
        finally:
            cursor.close()

    def get_columns(self, table_name, reset=True):
        """ Retrieve the columns of a table from MySQL database """
        try:
            if reset:
                self.conn.reset_session()

            cursor = self.conn.cursor()
            cursor.execute(f"SHOW COLUMNS FROM {table_name};")
            columns = cursor.fetchall()
            return columns
        except Error as e:
            print(e)
        finally:
            cursor.close()

    def show_tables(self, reset=True):
        # Connect to MySQL database
        if self.conn:
            if reset:
                self.conn.reset_session()

            # Get the list of tables
            tables = get_tables(self.conn)
            if tables:
                print("Tables in the database:")
                for table in tables:
                    print(table[0])
                print('\n' + '--' * 25 + '\n')
            else:
                print("No tables found in the database.")

    def show_columns(self, table_name, reset=True):
        # Connect to MySQL database
        if self.conn:
            if reset:
                self.conn.reset_session()

            # Get the list of tables
            columns = get_columns(self.conn, table_name)
            if columns:
                print(f"Columns in the {table_name}:")
                for column in columns:
                    print(column[0])
                print('\n' + '--' * 25 + '\n')
            else:
                print("No tables found in the database.")

    def get_table_as_dataframe(self, table_name, reset=True, set_index=True):
        try:
            cur_con = self.conn

            if reset:
                cur_con.reset_session()

            cursor = cur_con.cursor(prepared=True)
            command_str = "SELECT * FROM " + table_name
            cursor.execute(command_str)
            df = DataFrame(cursor.fetchall())  # помещаем данные в объект DataFrame
            df.columns = cursor.column_names  # из курсора можно взять имена столбцов
            if set_index:
                command_str = f"SHOW KEYS FROM {table_name} WHERE Key_name = 'PRIMARY'"
                cursor.execute(command_str)
                keys = cursor.fetchall()
                df.set_index(keys[0][4], inplace=True)
                # устанавливаем ключ, предварительно получив его имя из БД
            return df
        except Error as e:
            print(e)
        finally:
            cursor.close()

    def execute_query(self, query, data=None, verbose=False, reset=True):
        if reset:
            self.conn.reset_session()

        cursor = self.conn.cursor()
        try:
            cursor.execute(query, data)
            self.conn.commit()

            if verbose:
                section_brake()
                print("Query executed successfully")
                section_brake()
        except mysql.connector.Error as err:
            section_brake()
            print(f"Error executing query: {err}")
            section_brake()
        finally:
            cursor.close()

    def fetch_as_list(self, query, data=None, show=True, dictionary=False, reset=True):
        if reset:
            self.conn.reset_session()

        cursor = self.conn.cursor(dictionary=dictionary)
        try:
            cursor.execute(query, data)
            result = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description]
            if show:
                print(tabulate(result, headers=headers, tablefmt="pretty"))
            else:
                if dictionary:
                    return result
                else:
                    return headers, result
        except Exception as e:
            print(f"Error fetching data as list: {e}")
        finally:
            cursor.close()

    def fetch_as_dataframe(self, query, data=None, set_index=True, show=False, reset=True):  # Without set_index because it's too bad
        if reset:
            self.conn.reset_session()

        cursor = self.conn.cursor()
        try:
            cursor.execute(query, data)
            df = DataFrame(cursor.fetchall())  # помещаем данные в объект DataFrame
            df.columns = cursor.column_names  # из курсора можно взять имена столбцов
            if set_index:
                table_name_match = re.search(r'FROM\s+([^\s]+)', query, re.IGNORECASE)
                if table_name_match:
                    table_name = table_name_match.group(1)
                else:
                    raise Exception("Can't find table_name")
                command_str = f"SHOW KEYS FROM {table_name} WHERE Key_name = 'PRIMARY'"
                cursor.execute(command_str)
                keys = cursor.fetchall()
                df.set_index(keys[0][4], inplace=True)
            if show:
                print(df)
            else:
                return df
        except mysql.connector.Error as err:
            print(f"Error fetching data: {err}")
        finally:
            cursor.close()

    def save_as_csv(self, query, filename, data=None):
        headers, result = self.fetch_as_list(query, data, show=False, dictionary=False)
        if not result:
            print("No data to save.")
            return
        mode = 'a' if os.path.exists(filename) else 'w'
        with open(filename, mode, encoding="utf-8", newline='') as f:
            writer = wr(f, lineterminator='\n')
            if mode == 'w':
                writer.writerow(headers)
            for tup in result:
                writer.writerow(tup)
        print(f"Data saved to {filename}")

    def save_as_json(self, query, filename, data=None):
        result = self.fetch_as_list(query, data, show=False, dictionary=True)
        if not result:
            print("No data to save.")
            return
        with open(filename, 'w', encoding="utf-8") as f:
            json.dump(result, f, default=str, cls=DecimalEncoder, indent=4)
        print(f"Data saved to {filename}")

    def create_table(self, table_name, columns, overwrite=False, verbose=False, reset=True):
        if reset:
            self.conn.reset_session()

        if not overwrite:
            # Check if table already exists
            check_query = f"SHOW TABLES LIKE '{table_name}';"
            cursor = self.conn.cursor()
            cursor.execute(check_query)
            if cursor.fetchone():
                print(f"Table '{table_name}' already exists. Use overwrite=True to replace it.")
                cursor.close()
                return
            cursor.close()
        else:
            # Drop the table if it already exists
            drop_query = f"DROP TABLE IF EXISTS {table_name};"
            self.execute_query(drop_query, verbose=verbose)

        # Generate column definitions
        column_defs = [f"{name} {data_type}" for name, data_type in columns.items()]

        # Generate CREATE TABLE query
        create_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)});"
        self.execute_query(create_query, verbose=verbose)

    def delete_table(self, table_name, verbose=False):
        delete_query = f"DROP TABLE IF EXISTS {table_name};"
        self.execute_query(delete_query, verbose=verbose)

    def insert_data(self, table_name, data_list, verbose=False):
        if isinstance(data_list, types.GeneratorType):
            data_list = list(data_list)

        # Generate INSERT query
        columns = ', '.join(data_list[0].keys())
        values_template = ', '.join(['%s'] * len(data_list[0]))
        insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({values_template});"

        # Execute INSERT query with data values
        for data in data_list:
            self.execute_query(insert_query, tuple(data.values()), verbose=verbose)

    def update_data(self, table_name, data_list, condition_list=None, verbose=False):
        if condition_list is None:
            condition_list = [None] * len(data_list)

        try:
            for data, condition in zip(data_list, condition_list):
                # Generate UPDATE query
                set_clause = ', '.join([f"{column} = %s" for column in data.keys()])
                if condition:
                    update_query = f"UPDATE {table_name} SET {set_clause} WHERE {condition};"
                else:
                    update_query = f"UPDATE {table_name} SET {set_clause};"

                # Execute UPDATE query with data values
                self.execute_query(update_query, tuple(data.values()), verbose=verbose)
                return 1
        except TypeError:
            print("Error: Data and condition lists must be of the same length.")

    def delete_data(self, table_name, condition=None, verbose=False, backup=True):
        """
            Deletes data from the specified table in the database, optionally backing up the deleted data to a CSV file.

            This method generates a DELETE query to remove data from the specified table based on the provided condition.
            If a condition is not provided, all records from the table are deleted. Optionally, a backup of the deleted
            data can be saved to a CSV file before deletion.

            Args:
                table_name (str): The name of the table from which data will be deleted.
                condition (str, optional): The condition to apply when deleting data. If None, all records will be deleted.
                    Defaults to None.
                verbose (bool, optional): If True, prints status messages during the deletion process. Defaults to False.
                backup (bool, optional): If True, backs up the deleted data to a CSV file before deletion. Defaults to True.

            Returns:
                None
        """
        try:
            if backup:
                # Retrieve data to be deleted
                data_to_delete_query = f"SELECT * FROM {table_name} WHERE {condition}" if condition else f"SELECT * FROM {table_name}"
                data_to_delete = self.fetch_as_list(data_to_delete_query, show=False)
                if not data_to_delete[1]:
                    print("No data found for deletion.")
                    return 0

                # Write data to backup CSV file
                backup_filename = f"{table_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

                self.save_as_csv(data_to_delete_query, backup_filename)

            # Generate DELETE query
            delete_query = f"DELETE FROM {table_name}"
            if condition:
                delete_query += f" WHERE {condition}"

            # Execute DELETE query
            self.execute_query(delete_query, verbose=verbose)

            if verbose:
                print("Data deleted successfully")
            return 1
        except Exception as err:
            print(f"Error deleting data: {err}")

    def insert_data_from_file(self, table_name, file_path, primary_key, verbose=False):
        """
            Inserts data into the specified database table from a CSV or JSON file, ensuring no duplicate records are added.

            This method reads data from a CSV or JSON file, converts values to appropriate types, and inserts the data into
            the specified database table. It performs a check for duplicate records based on the primary key column, updating
            existing records if necessary.

            Args:
                table_name (str): The name of the database table to insert data into.
                file_path (str): The path to the file containing the data to insert into the database table.
                primary_key (str): The name of the primary key column in the database table.
                verbose (bool, optional): If True, prints status messages during the insertion process. Defaults to False.

            Returns:
                None
        """

        def read_csv_file(path):
            with open(path, 'r', encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Convert values to appropriate types
                    for column, value in row.items():
                        row[column] = try_convert(value)
                        if isinstance(row[column], str) and 'bytearray(b' in row[column]:
                            row[column] = row[column].replace("bytearray(b'", "").replace("')", "")
                            row[column] = bytearray(row[column].encode('utf-8'))
                    yield row

        def read_json_file(path):
            with open(path, 'r', encoding="utf-8") as file:
                data = json.load(file)
                for row in data:
                    yield row

        def insert_data_with_duplicates_check(table_name_, data_generator_, primary_key, verbose=False):
            existing_data = self.fetch_as_list(f"SELECT * FROM {table_name_}", show=False, dictionary=True)
            existing_keys = set(row[primary_key] for row in existing_data)
            max_key = max(existing_keys) if existing_keys else 0

            for row in data_generator_:
                if row[primary_key] in existing_keys:
                    existing_row = next(d for d in existing_data if d[primary_key] == row[primary_key])
                    if all(existing_row[key] == row[key] for key in row if key != primary_key):
                        if verbose:
                            print(
                            f"Skipping record with primary key {row[primary_key]} as it's identical to the existing row.")
                    else:
                        if verbose:
                            print(f"Updating record with primary key {row[primary_key]}")
                        max_key += 1
                        row[primary_key] = max_key
                        try:
                            self.insert_data(table_name_, [row], verbose=verbose)
                        except mysql.connector.Error as err:
                            print(f"Error occurred while updating record with primary key {row[primary_key]}: {err}")
                else:
                    max_key += 1
                    row[primary_key] = max_key
                    self.insert_data(table_name_, [row], verbose=verbose)

        # Determine file type
        file_extension = file_path.split('.')[-1].lower()

        # Read data from file based on file type
        if file_extension == 'csv':
            data_generator = read_csv_file(file_path)
        elif file_extension == 'json':
            data_generator = read_json_file(file_path)
        else:
            print("Unsupported file type")
            return

        # Insert data into the table
        insert_data_with_duplicates_check(table_name, data_generator, primary_key, verbose=verbose)

    def sync_table_with_file(self, table_name, file_path, primary_key, verbose=False):
        """
            Synchronizes the data in the specified database table with the data from a file.

            This method reads data from a CSV or JSON file, compares it with the existing data in the specified
            database table, and performs the necessary insertions, updates, and deletions to synchronize the data.

            Args:
                table_name (str): The name of the database table to synchronize with.
                file_path (str): The path to the file containing the data to synchronize with the database table.
                primary_key (str): The name of the primary key column in the database table.
                verbose (bool, optional): If True, prints status messages during synchronization. Defaults to False.

            Raises:
                ValueError: If the file format is unsupported (only CSV and JSON files are supported).

            Returns:
                None
        """
        try:
            # Read data from file
            if file_path.endswith('.csv'):
                with open(file_path, 'r', encoding="utf-8") as file:
                    file_data = list(csv.DictReader(file))
                    for row in file_data:
                        # Convert values to appropriate types
                        for column, value in row.items():
                            row[column] = try_convert(value)
            elif file_path.endswith('.json'):
                with open(file_path, 'r', encoding="utf-8") as file:
                    file_data = json.load(file)
            else:
                raise ValueError("Unsupported file format. Only CSV and JSON files are supported.")

            # Retrieve current data from database table
            db_data = self.fetch_as_list(f"SELECT * FROM {table_name}", show=False, dictionary=True)

            # Identify rows to be inserted, updated, and deleted
            to_insert = [row for row in file_data if row[primary_key] not in (item[primary_key] for item in db_data)]

            to_update = []
            for file_row in file_data:
                for db_row in db_data:
                    if db_row[primary_key] == file_row[primary_key]:
                        row_differs = any(file_row[key] != db_row[key] for key in file_row.keys() if key != primary_key)
                        if row_differs:
                            to_update.append(file_row)
                        break  # Exit the inner loop once a matching primary key is found

            # Remove duplicate rows from to_update (if any)
            to_update = list({row[primary_key]: row for row in to_update}.values())
            to_delete = [item for item in db_data if item[primary_key] not in (row[primary_key] for row in file_data)]
            print('To insert: ', to_insert)
            print('To update: ', to_update)
            print('To delete: ', to_delete)
            # Insert new rows
            for row in to_insert:
                self.insert_data(table_name, [row], verbose=verbose)

            # Update existing rows
            for row in to_update:
                # Extract the primary key value
                pk_value = row.pop(primary_key)
                # Update the row without the primary key column
                self.update_data(table_name, [row], [f"{primary_key} = {pk_value}"])

            # Delete rows that are not present in the file
            for item in to_delete:
                print(f"{primary_key} = {item[primary_key]}")
                self.delete_data(table_name, f"{primary_key} = {item[primary_key]}", verbose=verbose)

            if verbose:
                print("Table synchronization completed.")

        except Exception as err:
            print(f"Error synchronizing table with file: {err}")

    def call_stored_procedure(self, procedure_name, args=None, reset=True):
        if reset:
            self.conn.reset_session()
        try:
            cursor = self.conn.cursor()
            if args:
                cursor.callproc(procedure_name, args)
            else:
                cursor.callproc(procedure_name)

            result = cursor.fetchall()
            cursor.close()
            return result

        except mysql.connector.Error as e:
            print(f"Error calling stored procedure {procedure_name}: {e}")
            return None

    def write_data_to_file(self, query, filename, data=None, max_file_size_kb=200):
        try:
            # Получаем данные из БД
            headers, result = self.fetch_as_list(query, data, show=False, dictionary=False)
            if not result:
                print("No data to save.")
                return
            mode = 'a' if os.path.exists(filename) else 'w'

            with open(filename, mode, encoding="utf-8") as file:
                writer = wr(file, lineterminator='\n')
                file_size = 0
                if os.path.exists(filename):
                    # проверяем размер файла
                    initial_size = os.path.getsize(filename)
                    print(f"Initial file size of {filename}: {initial_size} bytes")
                    file_size = initial_size
                # Записываем данные в файл
                if mode == 'w':
                    writer.writerow(headers)

                for row in result:
                    line = ','.join(str(item) for item in row) + '\n'
                    # Получаем размер строки в байтах
                    line_size = len(line.encode('utf-8'))
                    # Проверяем, превышает ли размер файла максимальный размер
                    if file_size + line_size > max_file_size_kb * 1024:
                        print(f"File size limit ({max_file_size_kb} KB) reached. Stopping writing to file.")
                        break
                    # Записываем строку в файл
                    writer.writerow(row)
                    # Обновляем размер файла
                    file_size += line_size
            print(f"Data written to file {filename} successfully.")
        except Exception as e:
            print(f"Error writing data to file: {e}")

