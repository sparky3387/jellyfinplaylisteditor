#!/usr/bin/env python3

import re
import configparser
import subprocess
import csv
import json
from os import scandir
from os.path import isfile, join, splitext
import string
import random
import os
import platform
import sys
import sqlite3
from datetime import datetime
#from thefuzz import fuzz
from simple_term_menu import TerminalMenu
import xml.etree.cElementTree as ET

# Configuration file
CONFIG_FILE = "playlist_config.ini"
DB_FILE = "playlists.db"
allowedextensions = [".mp3",".crap",".ogg",".flac",".m4a",".wma",".ape"]

# Load or create configuration
def load_or_create_config():
    config = configparser.ConfigParser()
    
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE)
            print("Configuration loaded.")
        except Exception as e:
            print(f"Error loading configuration: {e}")
    
    # Exit if music directory not set
    if 'Paths' not in config or 'newpath_location' not in config['Paths']:
        print("Error: Music directory not configured in config file.")
        print(f"Please set 'newpath_location' in {CONFIG_FILE} and try again.")
        sys.exit(1)
    
    # Exit if ffprobe path not set
    if 'Paths' not in config or 'ffprobe_path' not in config['Paths']:
        print("Error: ffprobe path not configured in config file.")
        print(f"Please set 'ffprobe_path' in {CONFIG_FILE} and try again.")
        sys.exit(1)
    
    return config

# Initialize SQLite database
def init_database():
    """Initialize SQLite database with necessary tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
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
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    return True

# Load configuration
config = load_or_create_config()
newpath_location = config['Paths']['newpath_location']
ffprobe_path = config['Paths']['ffprobe_path']

# Initialize database
init_database()

# Function to create a new category
def create_category():
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
    
    conn = sqlite3.connect(DB_FILE)
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
        return True
    except sqlite3.IntegrityError:
        print(f"Error: A category with the name '{category_name}' already exists.")
        return False
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

# Function to delete a category
def delete_category():
    """Delete a category from the database."""
    conn = sqlite3.connect(DB_FILE)
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
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

# Main menu function
def import_csv():
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
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
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
                    
                    # Insert or update the folder-category mapping
                    cursor.execute(
                        'INSERT OR REPLACE INTO folders (path, category_id) VALUES (?, ?)',
                        (folder_path, category_id)
                    )
                    imported_count += 1
                else:
                    print("Warning: Skipping invalid row (needs at least 2 columns)")
        
        conn.commit()
        print(f"Successfully imported {imported_count} entries from CSV.")
        return True
    except Exception as e:
        print(f"Error importing CSV: {e}")
        return False
    finally:
        conn.close()

# Function to assign paths to categories
def reassign_albums():
    """Reassign folder paths to categories."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get all categories
    cursor.execute('SELECT id, name FROM categories ORDER BY name')
    categories = cursor.fetchall()
    
    if not categories:
        print("No categories found. Please create categories first.")
        conn.close()
        return False
    
    # Get all music folders
    music_folders = sorted(getpaths(newpath_location))
    
    if not music_folders:
        print(f"No music folders found in {newpath_location}")
        conn.close()
        return False
    
    # Load existing folder-category mappings
    folders_with_categories = get_folders_with_categories()
    
    # Create folder menu with truncated format
    folder_menu = []
    
    PATH_WIDTH = 60  # Exact width for path column
    
    for folder in music_folders:
        relative_path = folder.replace(newpath_location, '')
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
        relative_path = selected_folder.replace(newpath_location, '')
        
        # Show the audio files to help user categorize
        audio_files = [f.name for f in scandir(selected_folder) if f.is_file() and splitext(f.name)[1].lower() in allowedextensions]
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
            title=f"Select a category for this folder: {current_category_index}",
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
            folders_with_categories = get_folders_with_categories()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            conn.close()
            return False
    
    # Should never reach here as the loop continues until user exits
    conn.close()

#probe the music files to generate details for the playlist
def ffprobe(file_path):
    """Run ffprobe on a file and return JSON output with media information."""
    command_array = [ffprobe_path,
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

def scantree(path):
    """Recursively yield DirEntry objects for given directory."""
    for entry in scandir(path):
        if entry.is_dir(follow_symlinks=False):
            yield from scantree(entry.path)  # see below for Python 2.x
        else:
            yield entry
def getpaths(path):
        paths = []
        for entry in scantree(path):
                file_name, file_extension = splitext(entry.path)
                if file_extension.lower() in allowedextensions:
                        if os.path.dirname(entry.path) not in paths:
                                paths.append(os.path.dirname(entry.path))
        return paths
def getdictpaths(oldpath,paths):
        files = {}
        for path in paths:
                newpath = path.replace(oldpath,'')
                files[newpath] = []
                for file in scandir(path):
                        if file.is_file(follow_symlinks=False):
                                file_name, file_extension = splitext(file.path)
                                if file_extension.lower() in allowedextensions:
                                        files[newpath].append(file.name)
        return files

# Function to get category name by id
def get_category_name(category_id):
    """Get category name from database by id."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT name FROM categories WHERE id = ?', (category_id,))
    result = cursor.fetchone()
    
    conn.close()
    if result:
        return result[0]
    return None

# Function to store folder with category in database
def store_folder_category(folder_path, category_id):
    """Store folder path with associated category in database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
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

# Function to get all folders with categories from database
def get_folders_with_categories():
    """Get all folders with their assigned categories from database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
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
        folders_dict[row[0]] = {"category_id": row[1], "category_name": row[2]}
    
    return folders_dict

def assign_albums():
    # Get all music folders
    music_folders = getpaths(newpath_location)
    print(f"Found {len(music_folders)} music folders")

    # Load existing folder-category mappings from database
    folders_with_categories = get_folders_with_categories()
    print(f"Loaded {len(folders_with_categories)} folders with categories from database")

    """Assign folder paths to categories."""
    conn = sqlite3.connect(DB_FILE)
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
        relative_path = folder.replace(newpath_location, '')
        print(f"\nCategorizing folder: \033[91m{relative_path}\033[00m")
        
        # Show the audio files to help user categorize
        audio_files = [f.name for f in scandir(folder) if f.is_file() and splitext(f.name)[1].lower() in allowedextensions]
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
            
            # Store in database
            if store_folder_category(folder, selected_category_id):
                print(f"Stored folder category: {folder} -> {selected_category_name}")
            else:
                print(f"Failed to store folder category in database")
        elif menu_index == len(categories):
            print("Skip selected, skipping folder")
        elif menu_index == len(categories) + 1 or menu_index is None:
            print("Back to Main Menu selected, returning to main menu")
            return
    if albumsProcessed == None:
        print("No remaining albums to process")
    input("Press Enter to Continue")

def write_playlists():

    # Reload folder-category mappings after updates
    folders_with_categories = get_folders_with_categories()

    # Build playlists database
    newplaylist = {}

    # Process folders from the database
    for folder_path, folder_info in folders_with_categories.items():
        category_name = folder_info['category_name']
        
        # Process the folder's audio files
        newfiles = [newfile.name for newfile in scandir(folder_path) if splitext(newfile)[1].lower() in allowedextensions]
        
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
            tags = json.loads(ffprobe(os.path.join(folder_path, file)))['format']['tags']
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

def prune_invalid_paths():
    """Prune invalid paths from the database."""
    conn = sqlite3.connect(DB_FILE)
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
            category_name = get_category_name(category_id) or "Unknown"
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

def show_main_menu():
    """Display the main menu and handle user choices."""
    main_menu_items = [
        "[1] Create a new playlist category",
        "[2] Delete/Show a playlist category",
        "[3] Assign albums to categories",
        "[4] Reassign albums to categories",
        "[5] Import categories from CSV",
        "[6] Generate playlists",
        "[7] Prune invalid paths",
        "[8] Exit"
    ]
    
    main_menu = TerminalMenu(main_menu_items, title="--------Jellyfin Playlist Editor - Main Menu--------", clear_screen=True)
    
    while True:
        menu_index = main_menu.show()
        
        if menu_index == 0:  # Create category
            create_category()
        elif menu_index == 1:  # Delete category
            delete_category()
        elif menu_index == 2:  # Assign paths
            assign_albums()
        elif menu_index == 3:  # Assign paths
            reassign_albums()
        elif menu_index == 4:  # Import CSV
            import_csv()
        elif menu_index == 5:  # Generate playlists
            write_playlists()
        elif menu_index == 6:  # Prune invalid paths
            prune_invalid_paths()
        elif menu_index == 7 or menu_index is None:  # Exit
            print("Exiting program.")
            sys.exit(0)
        
        # Refresh categories after changes
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM categories')
        global categories
        categories = {row[1]: row[0] for row in cursor.fetchall()}
        conn.close()

# Check if script is running in interactive mode
try:
    # Show main menu before proceeding with playlist generation
    if show_main_menu():
        print("Proceeding with playlist generation...")
    else:
        sys.exit(0)
except Exception as e:
    print(f"Warning: Could not show interactive menu: {e}")
    print("Proceeding directly with playlist generation...")

newpaths=getpaths(newpath_location)
try:
    confirmmenu=["[0] Yes","[1] Missing Tracks","[2] No"]
    confirm_terminal_menu = TerminalMenu(confirmmenu,title="Is this correct?")
except Exception as e:
    print(f"Warning: Could not create terminal menu: {e}")


# Get categories from database
categories = {}
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute('SELECT id, name FROM categories')
for row in cursor.fetchall():
    categories[row[1]] = row[0]
conn.close()




# Initialize empty dictionary for CSV entries
lines = {}

# Process CSV entries first (for backward compatibility)
#for newpath, category in lines.items():
	
#    if newpath in alreadydone:
#      print(f"Already done {newpath}")
#      continue

#    if newpath in lines and lines[newpath]==1:
#       print(f"Skipping known entry......... {originalpath} {lines[originalpath]}")
#       continue
#    with open('badentries.csv', 'a', newline='') as csvfile:
#        spamwriter = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
#        print(f"Finding path {newpath}")
#        if newpath in lines:
#          if lines[newpath] != 5:
#            print(f"Skipping known entry......... {newpath} {lines[newpath]}")
#            spamwriter.writerow([newpath,lines[newpath]])
#            continue
#          if lines[newpath] == 5:
#            print(f"Checking known 'other' entry......... {newpath} {lines[newpath]}")
#        else:
#          partialbrokenpath = os.path.dirname(newpath)
#          endpartpath = os.path.basename(newpath)
#          print(f"partialpath is {partialbrokenpath}")
#          print(f"endpartpath is {endpartpath}")
#          print(os.path.join(partialbrokenpath,endpartpath))
#          brokenpaths = [ brokenpath for brokenpath,value in lines.items() if brokenpath == partialbrokenpath+endpartpath ]
#          print(brokenpaths)
#          if len(brokenpaths)>1:
#            print("React here")
#            exit(1)
#          if len(brokenpaths)==1:
#            if brokenpaths[0] in lines:
#              print(brokenpaths[0])
#              if lines[brokenpaths[0]] == 5:
#                print(f"Checking known 'other' entry......... {newpath} {lines[brokenpaths[0]]}")
#              if lines[brokenpaths[0]] != 5:
#                print(f"Skipping known entry......... {newpath} {lines[brokenpaths[0]]}")
#                spamwriter.writerow([newpath,lines[brokenpaths[0]]])
#                continue
#        newfiles = [newfile.name for newfile in scandir(newpath) if splitext(newfile)[1].lower() in allowedextensions]
#        print(newfiles)
#        print(newpath)
#        print(category)
#        print(categories.items())
#        newcategory=""
#        for newcategorykey,newcategoryvalue in categories.items(): 
#          if newcategoryvalue == int(category):
#            newcategory = newcategorykey
#        if newcategory == "":
#          print("Unrecoverable error, exiting")
#          exit(1)
#        print(newcategory) 
#        #if newpath in lines and lines[newpath]==1:
#        #  print(f"Skipping known entry......... {originalpath} {lines[originalpath]}")
#        #  continue
#        print("Trying to identify album category \033[91m "+newpath.replace(newpath_location,'')+"\033[00m")
#        print('With files: ') 
#        if newcategory not in newplaylist:
#          newplaylist[newcategory] = {}
#        if 'genres' not in newplaylist[newcategory]:
#          newplaylist[newcategory]['genres'] = []
#        if 'files' not in newplaylist[newcategory]:
#          newplaylist[newcategory]['files'] = []
#        for file in sorted(newfiles):
#            newplaylist[newcategory]['files'].append(os.path.join(newpath,file))
#            genre = None 
#            tags = json.loads(ffprobe(os.path.join(newpath,file)))['format']['tags']
#            try:
#              genre = tags['GENRE']
#            except KeyError:
#              try:
#                genre = tags['genre']
#              except KeyError:
#                pass
#            if genre is not None:
#              genres = genre.split(";") 
#              newplaylist[newcategory]['genres'].extend(genre for genre in genres if genre not in newplaylist[newcategory]['genres'])
#        print(newplaylist[newcategory]['genres'])

    
