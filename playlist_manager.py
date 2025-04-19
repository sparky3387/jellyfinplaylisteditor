#!/usr/bin/env python3

import os
import csv
import json
import sqlite3
import subprocess
import configparser
from datetime import datetime
from os import scandir
from os.path import isfile, join, splitext
import xml.etree.cElementTree as ET
from simple_term_menu import TerminalMenu

class PlaylistManager:
    """Class to manage playlist operations and database interactions."""
    
    def __init__(self, config_file, db_file, music_location, ffprobe_path):
        self.config_file = config_file
        self.db_file = db_file
        self.music_location = music_location
        self.ffprobe_path = ffprobe_path
        self.allowed_extensions = [".mp3",".ogg",".flac",".m4a",".wma",".ape"]
        
        # Initialize the database
        self.init_database()
        
        # Get categories from database
        self.categories = self.get_categories_dict()
    
    def init_database(self):
        """Initialize SQLite database with necessary tables if they don't exist."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Create categories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
        ''')
        
        # Create folders table with foreign key relationship to categories
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            category_id INTEGER,
            user_name TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
        ''')
        
        # Create jellyfin_items table to store Jellyfin item information
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS jellyfin_items (
            id INTEGER PRIMARY KEY,
            item_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            path TEXT,
            type TEXT NOT NULL,
            parent_id TEXT,
            scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        return True
    
    def get_categories_dict(self):
        """Get categories from database as a dictionary of name: id."""
        categories = {}
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM categories')
        for row in cursor.fetchall():
            categories[row[1]] = row[0]
        conn.close()
        return categories
    
    def create_category(self):
        """Create a new category in the database."""
        print("--------Create a new playlist category--------")
        print("(Enter 'back' to return to the main menu)")
        category_name = input("Enter the new category name: ")
        
        if category_name.lower() == 'back':
            print("Returning to main menu.")
            return False
        
        if not category_name:
            print("Category name cannot be empty.")
            return False
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            # Get the highest existing ID
            cursor.execute('SELECT MAX(id) FROM categories')
            result = cursor.fetchone()
            new_id = 0 if result[0] is None else result[0] + 1
            
            # Insert the new category
            cursor.execute('INSERT INTO categories (id, name) VALUES (?, ?)', (new_id, category_name))
            conn.commit()
            print(f"Category '{category_name}' created successfully.")
            
            # Update local categories dictionary
            self.categories[category_name] = new_id
            
            return True
        except sqlite3.IntegrityError:
            print(f"Error: A category with the name '{category_name}' already exists.")
            return False
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def delete_category(self):
        """Delete a category from the database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Get all categories
        cursor.execute('SELECT id, name FROM categories ORDER BY id')
        categories = cursor.fetchall()
        
        if not categories:
            print("No categories found.")
            conn.close()
            return False
        
        # Create menu of category options
        category_menu = []
        for id, name in categories:
            category_menu.append(f"ID{id} {name}")
        category_menu.append("------ Back to Main Menu ------")
        
        print("--------Delete a playlist category---------")
        terminal_menu = TerminalMenu(category_menu, title="Select a category to delete:")
        menu_index = terminal_menu.show()
        
        if menu_index is None:
            print("No category selected.")
            conn.close()
            return False
        
        # Check if "Back to Main Menu" was selected
        if menu_index == len(categories):
            print("Returning to main menu.")
            conn.close()
            return False
        
        # Get the selected category
        selected_category_id = categories[menu_index][0]
        selected_category_name = categories[menu_index][1]
        
        # Check if there are folders assigned to this category
        cursor.execute('SELECT COUNT(*) FROM folders WHERE category_id = ?', (selected_category_id,))
        folder_count = cursor.fetchone()[0]
        
        if folder_count > 0:
            confirm = input(f"Warning: {folder_count} folders are assigned to '{selected_category_name}'. Delete anyway? (y/n): ")
            if confirm.lower() != 'y':
                print("Deletion cancelled.")
                conn.close()
                return False
        
        try:
            # Delete the category
            cursor.execute('DELETE FROM categories WHERE id = ?', (selected_category_id,))
            
            # Update associated folders to NULL or another category
            cursor.execute('UPDATE folders SET category_id = NULL WHERE category_id = ?', (selected_category_id,))
            
            conn.commit()
            print(f"Category '{selected_category_name}' deleted successfully.")
            
            # Update local categories dictionary
            if selected_category_name in self.categories:
                del self.categories[selected_category_name]
                
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def import_csv(self, username=None):
        """Import playlist categories from a CSV file."""
        print("---------Import playlist categories from CSV file---------")
        print("\nThe format is /thepath/to/your/album,5")
        print("\n5 being the id of a category")
        print("(Type 'back' to return to the main menu)")
        file_path = input("Enter the CSV file path: ")
        
        if file_path.lower() == 'back':
            print("Returning to main menu.")
            return False
        
        if not file_path:
            print("No file path provided.")
            return False
        
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' not found.")
            return False
        
        # Prompt for username if not provided
        if username is None:
            username = input("Enter username for these folders (or press Enter to skip): ")
            # If user pressed Enter without typing anything, set to None
            if not username.strip():
                username = None
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Check if user_name column exists in the folders table
        cursor.execute("PRAGMA table_info(folders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add the column if it doesn't exist
        if 'user_name' not in columns and username is not None:
            try:
                cursor.execute('ALTER TABLE folders ADD COLUMN user_name TEXT')
                print("Added user_name column to folders table")
                conn.commit()
            except sqlite3.Error as e:
                print(f"Error adding user_name column: {e}")
        
        imported_count = 0
        try:
            with open(file_path, newline='') as csvfile:
                csv_reader = csv.reader(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
                for row in csv_reader:
                    if len(row) >= 2:
                        folder_path = row[0]
                        category_id = int(row[1])
                        
                        # Check if the category exists
                        cursor.execute('SELECT id FROM categories WHERE id = ?', (category_id,))
                        if cursor.fetchone() is None:
                            print(f"Warning: Category ID {category_id} does not exist. Skipping entry.")
                            continue
                        
                        # Insert or update the folder-category mapping with username if available
                        if 'user_name' in columns and username is not None:
                            cursor.execute(
                                'INSERT OR REPLACE INTO folders (path, category_id, user_name) VALUES (?, ?, ?)',
                                (folder_path, category_id, username)
                            )
                        else:
                            cursor.execute(
                                'INSERT OR REPLACE INTO folders (path, category_id) VALUES (?, ?)',
                                (folder_path, category_id)
                            )
                        imported_count += 1
                    else:
                        print("Warning: Skipping invalid row (needs at least 2 columns)")
            
            conn.commit()
            print(f"Successfully imported {imported_count} entries from CSV.")
            if username is not None:
                print(f"All entries associated with user: '{username}'")
            return True
        except Exception as e:
            print(f"Error importing CSV: {e}")
            return False
        finally:
            conn.close()
    
    def reassign_albums(self):
        """Reassign folder paths to categories."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Get all categories
        cursor.execute('SELECT id, name FROM categories ORDER BY name')
        categories = cursor.fetchall()
        
        if not categories:
            print("No categories found. Please create categories first.")
            conn.close()
            return False
        
        # Get all music folders
        music_folders = sorted(self.getpaths(self.music_location))
        
        if not music_folders:
            print(f"No music folders found in {self.music_location}")
            conn.close()
            return False
        
        # Load existing folder-category mappings
        folders_with_categories = self.get_folders_with_categories()
        
        # Create folder menu with truncated format
        folder_menu = []
        
        PATH_WIDTH = 60  # Exact width for path column
        
        for folder in music_folders:
            relative_path = folder.replace(self.music_location, '')
            # Truncate or pad path to exactly 60 chars
            if len(relative_path) > PATH_WIDTH:
                display_path = relative_path[:PATH_WIDTH-3] + "..."
            else:
                # Space padding to exactly 60 chars
                display_path = relative_path + " " * (PATH_WIDTH - len(relative_path))
                
            if folder in folders_with_categories:
                category_name = folders_with_categories[folder]['category_name']
                # Truncate category to 30 chars max
                if len(category_name) > 30:
                    display_category = category_name[:27] + "..."
                else:
                    display_category = category_name
                folder_menu.append(f"{display_path} {display_category}")
            else:
                # ANSI red for uncategorized
                folder_menu.append(f"{display_path} Uncategorized")
        
        # Add a "Back to Main Menu" option
        folder_menu.append("------ Back to Main Menu ------")
        
        print("\nAssign paths to categories")
        
        # Start the selection loop
        current_index = 0
        while True:
            terminal_menu = TerminalMenu(
                folder_menu, 
                title="---------Select a folder to categorize:---------",
                cursor_index=current_index
            )
            menu_index = terminal_menu.show()
            
            if menu_index is None:
                print("No folder selected.")
                conn.close()
                return False
            
            # Check if "Back to Main Menu" option was selected
            if menu_index == len(music_folders):
                print("Returning to main menu.")
                conn.close()
                return False
            
            current_index = menu_index  # Save the current position
            selected_folder = music_folders[menu_index]
            relative_path = selected_folder.replace(self.music_location, '')
            
            # Show the audio files to help user categorize
            audio_files = [f.name for f in scandir(selected_folder) if f.is_file() and splitext(f.name)[1].lower() in self.allowed_extensions]
            print(f"\nFolder: \033[91m{relative_path}\033[00m")
            print(f"Contains {len(audio_files)} audio files:")
            for i, file in enumerate(sorted(audio_files[:5])):  # Show first 5 files
                print(f"  {i+1}. {file}")
            if len(audio_files) > 5:
                print(f"  ... and {len(audio_files) - 5} more files")
            
            # Create category menu
            category_menu = []
            # Find the current category if it exists
            current_category_index = None
            for i, (id, name) in enumerate(categories):
                category_menu.append(f"ID{id} {name}")
                if selected_folder in folders_with_categories and folders_with_categories[selected_folder]['category_id'] == id:
                    current_category_index = i
            
            # Display menu and get user choice with cursor on current category if applicable
            terminal_menu = TerminalMenu(
                category_menu, 
                title=f"Select a category for this folder:",
                cursor_index=current_category_index if current_category_index is not None else 0,
            )
            category_index = terminal_menu.show()
            
            if category_index is None:
                print("No category selected.")
                continue  # Go back to folder selection maintaining position
            
            # Get the selected category
            selected_category_id = categories[category_index][0]
            selected_category_name = categories[category_index][1]
            
            # Store in database
            try:
                # Check if user_name column exists in the folders table
                cursor.execute("PRAGMA table_info(folders)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'user_name' in columns:
                    # Get current user_name value if it exists
                    cursor.execute('SELECT user_name FROM folders WHERE path = ?', (selected_folder,))
                    result = cursor.fetchone()
                    user_name = result[0] if result else None
                    
                    cursor.execute(
                        'INSERT OR REPLACE INTO folders (path, category_id, user_name) VALUES (?, ?, ?)',
                        (selected_folder, selected_category_id, user_name)
                    )
                else:
                    cursor.execute(
                        'INSERT OR REPLACE INTO folders (path, category_id) VALUES (?, ?)',
                        (selected_folder, selected_category_id)
                    )
                    
                conn.commit()
                print(f"Folder '{relative_path}' assigned to category '{selected_category_name}'.")
                
                # Update the folder menu display for the current item
                # Truncate or pad path to exactly 60 chars
                if len(relative_path) > PATH_WIDTH:
                    display_path = relative_path[:PATH_WIDTH-3] + "..."
                else:
                    # Space padding to exactly 60 chars
                    display_path = relative_path + " " * (PATH_WIDTH - len(relative_path))
                    
                if len(selected_category_name) > 30:
                    display_category = selected_category_name[:27] + "..."
                else:
                    display_category = selected_category_name
                    
                folder_menu[menu_index] = f"{display_path} {display_category}"
                
                # Reload folder-category mappings
                folders_with_categories = self.get_folders_with_categories()
            except sqlite3.Error as e:
                print(f"Database error: {e}")
                conn.close()
                return False
        
        # Should never reach here as the loop continues until user exits
        conn.close()
    
    def ffprobe(self, file_path):
        """Run ffprobe on a file and return JSON output with media information."""
        command_array = [self.ffprobe_path,
                         "-v", "quiet",
                         "-print_format", "json",
                         "-show_format",
                         "-show_streams",
                         file_path]
        result = subprocess.run(command_array, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if result.returncode==0:
          return result.stdout
        else:
          return "{}"
    
    def scantree(self, path):
        """Recursively yield DirEntry objects for given directory."""
        for entry in scandir(path):
            if entry.is_dir(follow_symlinks=False):
                yield from self.scantree(entry.path)
            else:
                yield entry
    
    def getpaths(self, path):
        """Get all directory paths containing music files."""
        paths = []
        for entry in self.scantree(path):
                file_name, file_extension = splitext(entry.path)
                if file_extension.lower() in self.allowed_extensions:
                        if os.path.dirname(entry.path) not in paths:
                                paths.append(os.path.dirname(entry.path))
        return paths
    
    def getdictpaths(self, oldpath, paths):
        """Create a dictionary of paths and their music files."""
        files = {}
        for path in paths:
                newpath = path.replace(oldpath,'')
                files[newpath] = []
                for file in scandir(path):
                        if file.is_file(follow_symlinks=False):
                                file_name, file_extension = splitext(file.path)
                                if file_extension.lower() in self.allowed_extensions:
                                        files[newpath].append(file.name)
        return files
    
    def get_category_name(self, category_id):
        """Get category name from database by id."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('SELECT name FROM categories WHERE id = ?', (category_id,))
        result = cursor.fetchone()
        
        conn.close()
        if result:
            return result[0]
        return None
    
    def store_folder_category(self, folder_path, category_id, user_name=None):
        """Store folder path with associated category in database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Check if user_name column exists in the folders table
        cursor.execute("PRAGMA table_info(folders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        try:
            if 'user_name' in columns:
                cursor.execute(
                    'INSERT OR REPLACE INTO folders (path, category_id, user_name) VALUES (?, ?, ?)',
                    (folder_path, category_id, user_name)
                )
            else:
                cursor.execute(
                    'INSERT OR REPLACE INTO folders (path, category_id) VALUES (?, ?)',
                    (folder_path, category_id)
                )
            conn.commit()
            result = True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            result = False
        finally:
            conn.close()
        
        return result
    
    def get_folders_with_categories(self):
        """Get all folders with their assigned categories from database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # First check if user_name column exists
        cursor.execute("PRAGMA table_info(folders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'user_name' in columns:
            cursor.execute('''
                SELECT f.path, f.category_id, c.name, f.user_name
                FROM folders f
                JOIN categories c ON f.category_id = c.id
            ''')
        else:
            # If user_name column doesn't exist, don't include it
            cursor.execute('''
                SELECT f.path, f.category_id, c.name
                FROM folders f
                JOIN categories c ON f.category_id = c.id
            ''')
        
        result = cursor.fetchall()
        conn.close()
        
        # Convert to dictionary for easier use
        folders_dict = {}
        for row in result:
            if 'user_name' in columns and len(row) > 3:
                folders_dict[row[0]] = {"category_id": row[1], "category_name": row[2], "user_name": row[3]}
            else:
                folders_dict[row[0]] = {"category_id": row[1], "category_name": row[2], "user_name": None}
        
        return folders_dict
    
    def assign_albums(self, username=None):
        """Assign folder paths to categories."""
        # Get all music folders
        music_folders = self.getpaths(self.music_location)
        print(f"Found {len(music_folders)} music folders")

        # Load existing folder-category mappings from database
        folders_with_categories = self.get_folders_with_categories()
        print(f"Loaded {len(folders_with_categories)} folders with categories from database")

        # Prompt for username if not provided
        if username is None:
            # Check if selected_user_name exists in global scope
            if 'selected_user_name' in globals():
                username = globals()['selected_user_name']
            else:
                username_input = input("Enter username for these folders (or press Enter to skip): ")
                # If user pressed Enter without typing anything, set to None
                username = username_input.strip() if username_input.strip() else None

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Get all categories
        cursor.execute('SELECT id, name FROM categories ORDER BY name')
        categories = cursor.fetchall()
        
        if not categories:
            print("No categories found. Please create categories first.")
            conn.close()
            return False

        # For new folders not in database yet, prompt user to choose category
        albumsProcessed = None
        for folder in music_folders:
            # If folder is already in the database, skip prompting
            if folder in folders_with_categories:
                print(f"Folder already categorized: {folder} -> {folders_with_categories[folder]['category_name']}")
                continue

            # Add a marker that we processed any albums
            albumsProcessed = True
                
            # For remaining uncategorized folders, prompt user to select category
            relative_path = folder.replace(self.music_location, '')
            print(f"\nCategorizing folder: \033[91m{relative_path}\033[00m")
            
            # Show the audio files to help user categorize
            audio_files = [f.name for f in scandir(folder) if f.is_file() and splitext(f.name)[1].lower() in self.allowed_extensions]
            print(f"Contains {len(audio_files)} audio files:")
            for i, file in enumerate(sorted(audio_files[:5])):  # Show first 5 files
                print(f"  {i+1}. {file}")
            if len(audio_files) > 5:
                print(f"  ... and {len(audio_files) - 5} more files")
            
            # Create menu of category options
            category_menu = []
            for id, name in categories:
                category_menu.append(f"ID{id} {name}")
            category_menu.append("Skip")
            category_menu.append("------ Back to Main Menu ------")
            
            # Display menu and get user choice
            terminal_menu = TerminalMenu(category_menu, title="Select a category for this folder:")
            menu_index = terminal_menu.show()
            
            if menu_index is not None and menu_index < len(categories):
                # Get the selected category ID
                selected_category_id = categories[menu_index][0]
                selected_category_name = categories[menu_index][1]
                
                # Store in database with username if provided
                if self.store_folder_category(folder, selected_category_id, username):
                    msg = f"Stored folder category: {folder} -> {selected_category_name}"
                    if username:
                        msg += f" (User: {username})"
                    print(msg)
                else:
                    print(f"Failed to store folder category in database")
            elif menu_index == len(categories):
                print("Skip selected, skipping folder")
            elif menu_index == len(categories) + 1 or menu_index is None:
                print("Back to Main Menu selected, returning to main menu")
                conn.close()
                return
        
        if albumsProcessed is None:
            print("No remaining albums to process")
        
        input("Press Enter to Continue")
        conn.close()
    
    def write_playlists(self):
        """Generate XML playlists from categorized folders."""
        # Reload folder-category mappings after updates
        folders_with_categories = self.get_folders_with_categories()

        # Build playlists database
        newplaylist = {}

        # Process folders from the database
        for folder_path, folder_info in folders_with_categories.items():
            category_name = folder_info['category_name']
            
            # Process the folder's audio files
            newfiles = [newfile.name for newfile in scandir(folder_path) if splitext(newfile)[1].lower() in self.allowed_extensions]
            
            print(f"Processing folder from database: {folder_path} -> {category_name}")
            
            if category_name not in newplaylist:
                newplaylist[category_name] = {}
            if 'genres' not in newplaylist[category_name]:
                newplaylist[category_name]['genres'] = []
            if 'files' not in newplaylist[category_name]:
                newplaylist[category_name]['files'] = []
            
            for file in sorted(newfiles):
                newplaylist[category_name]['files'].append(os.path.join(folder_path, file))
                genre = None 
                tags = json.loads(self.ffprobe(os.path.join(folder_path, file)))['format']['tags']
                try:
                    genre = tags['GENRE']
                except KeyError:
                    try:
                        genre = tags['genre']
                    except KeyError:
                        pass
                if genre is not None:
                    genres = genre.split(";") 
                    newplaylist[category_name]['genres'].extend(genre for genre in genres if genre not in newplaylist[category_name]['genres'])

        print(f"Generated {len(newplaylist)} playlists")
        
        # Get playlist directory from config
        config = configparser.ConfigParser()
        config.read(self.config_file)
        playlist_directory = config['Paths'].get('playlist_directory', './playlists')
        
        # Ensure the playlist directory exists
        if not os.path.exists(playlist_directory):
            os.makedirs(playlist_directory)
        
        # Write playlist XML files
        for playlist in newplaylist.keys():
            # Create category directory if it doesn't exist
            category_dir = os.path.join(playlist_directory, playlist.replace("/", "_"))
            if not os.path.exists(category_dir):
                os.makedirs(category_dir)
            
            # Define XML file path
            NewXML = os.path.join(category_dir, "playlist.xml")
            out = open(NewXML, 'wb')
            playlistxml = ET.Element('Item')
            ET.SubElement(playlistxml, 'Added').text = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
            ET.SubElement(playlistxml, 'LockData').text = 'false'
            ET.SubElement(playlistxml, 'LocalTitle').text = f"{playlist}"
            genres = ET.SubElement(playlistxml, 'Genres')
            for genre in sorted(newplaylist[playlist]['genres']):
                ET.SubElement(genres, 'Genre').text = f"{genre}"
            # Default owner ID - should be configurable ideally
            ET.SubElement(playlistxml, 'OwnerUserId').text = f"f9dc2435d1eb43fcb7be02c060e59a52"
            playlistitems = ET.SubElement(playlistxml, 'PlaylistItems')
            for file in newplaylist[playlist]['files']:
                playlistitem = ET.SubElement(playlistitems, 'PlaylistItem')
                ET.SubElement(playlistitem, 'Path').text = f"{file}"
            ET.SubElement(playlistxml, 'PlaylistMediaType').text = 'Audio'
            tree = ET.ElementTree(playlistxml)
            ET.indent(tree, space="\t", level=0)
            out.write(b'<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n')
            tree.write(out, encoding='UTF-8', xml_declaration=False)
            out.close()
            
            print(f"Written playlist XML: {NewXML} with {len(newplaylist[playlist]['files'])} files")
        
        input("Press Enter to Continue")
    
    def prune_invalid_paths(self):
        """Prune invalid paths from the database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Get all folder paths from the database
        cursor.execute('SELECT id, path, category_id FROM folders')
        folders = cursor.fetchall()
        
        if not folders:
            print("No folders found in database.")
            conn.close()
            return False
        
        invalid_count = 0
        removed_count = 0
        
        print("\nChecking for invalid paths in database...")
        
        for folder_id, folder_path, category_id in folders:
            if not os.path.exists(folder_path):
                invalid_count += 1
                category_name = self.get_category_name(category_id) or "Unknown"
                print(f"Invalid path found: '{folder_path}' (Category: {category_name})")
                
                options = ["Yes", "No", "Skip", "Cancel"]
                terminal_menu = TerminalMenu(options, title=f"Do you want to remove this invalid entry from the database?")
                menu_index = terminal_menu.show()
                
                if menu_index == 0:  # Yes
                    try:
                        cursor.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
                        print(f"Removed invalid entry from database.")
                        removed_count += 1
                    except sqlite3.Error as e:
                        print(f"Database error: {e}")
                elif menu_index == 1:  # No
                    print(f"Keeping invalid entry in database.")
                elif menu_index == 2:  # Skip
                    print(f"Skipping this entry.")
                elif menu_index == 3 or menu_index is None:  # Cancel
                    print(f"Cancelling prune operation.")
                    conn.close()
                    return False
        
        conn.commit()
        conn.close()
        
        print(f"\nSummary: Found {invalid_count} invalid paths, removed {removed_count} entries.")
        input("Press Enter to Continue")
        return True
    
    def update_folders_user(self, username='sparks'):
        """Update all folders in the database to have the specified user_name."""
        print(f"\n---------Updating Folders User to '{username}'---------")
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            # Check if user_name column exists
            cursor.execute("PRAGMA table_info(folders)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'user_name' not in columns:
                # Add user_name column if it doesn't exist
                cursor.execute('ALTER TABLE folders ADD COLUMN user_name TEXT')
                print("Added user_name column to folders table")
            
            # Count how many rows will be updated
            cursor.execute('SELECT COUNT(*) FROM folders')
            count = cursor.fetchone()[0]
            
            # Perform the update
            cursor.execute('UPDATE folders SET user_name = ?', (username,))
            conn.commit()
            
            print(f"Successfully updated {count} folder entries to user '{username}'.")
            
            # Refresh categories after changes
            cursor.execute('SELECT id, name FROM categories')
            self.categories = {row[1]: row[0] for row in cursor.fetchall()}
            
            result = True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            result = False
        finally:
            conn.close()
        
        input("\nPress Enter to Continue")
        return result