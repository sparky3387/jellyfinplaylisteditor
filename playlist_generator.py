#!/usr/bin/env python3

import re
import configparser
import os
import sys
import requests
from simple_term_menu import TerminalMenu

# Import the manager classes from their modules
from playlist_manager import PlaylistManager
from jellyfin_manager import JellyfinManager

# Configuration file paths
CONFIG_FILE = "playlist_config.ini"
DB_FILE = "playlists.db"

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

# Load configuration
config = load_or_create_config()
newpath_location = config['Paths']['newpath_location']
ffprobe_path = config['Paths']['ffprobe_path']

# Jellyfin API settings (using defaults if not in config)
jellyfin_server_url = config.get('Jellyfin', 'server_url', fallback='http://localhost:8096')
jellyfin_api_key = config.get('Jellyfin', 'api_key', fallback='')

# Initialize the managers
playlist_manager = PlaylistManager(CONFIG_FILE, DB_FILE, newpath_location, ffprobe_path)
jellyfin_manager = JellyfinManager(DB_FILE, jellyfin_server_url, jellyfin_api_key)

# Show welcome message
print("\n---------Welcome to Jellyfin Playlist Editor---------")
print(f"Connected to Jellyfin server at: {jellyfin_server_url}")
print("Use the menu to manage playlists and Jellyfin integration")

# No wrapper functions - using class methods directly from main menu

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
        "[8] List Jellyfin users",
        "[9] Search Jellyfin paths",
        "[10] Scan Jellyfin music albums",
        "[11] Browse Jellyfin database",
        "[12] Exit"
    ]
    
    main_menu = TerminalMenu(main_menu_items, title="--------Jellyfin Playlist Editor - Main Menu--------", clear_screen=True)
    
    while True:
        menu_index = main_menu.show()
        
        if menu_index == 0:  # Create category
            playlist_manager.create_category()
        elif menu_index == 1:  # Delete category
            playlist_manager.delete_category()
        elif menu_index == 2:  # Assign albums to categories
            # Get selected user name from Jellyfin manager if available
            current_username = getattr(jellyfin_manager, 'selected_user_name', None)
            playlist_manager.assign_albums(current_username)
        elif menu_index == 3:  # Reassign albums
            playlist_manager.reassign_albums()
        elif menu_index == 4:  # Import CSV
            # Get selected user name from Jellyfin manager if available
            current_username = getattr(jellyfin_manager, 'selected_user_name', None)
            playlist_manager.import_csv(current_username)
        elif menu_index == 5:  # Generate playlists
            playlist_manager.write_playlists()
        elif menu_index == 6:  # Prune invalid paths
            playlist_manager.prune_invalid_paths()
        elif menu_index == 7:  # List Jellyfin users
            jellyfin_manager.select_user()
        elif menu_index == 8:  # Search Jellyfin paths
            jellyfin_manager.search_path()
        elif menu_index == 9:  # Scan Jellyfin items
            jellyfin_manager.scan_items()
        elif menu_index == 10:  # Browse Jellyfin database
            jellyfin_manager.browse_database()
        elif menu_index == 11 or menu_index is None:  # Exit
            print("Exiting program.")
            sys.exit(0)

# Start the application
if __name__ == "__main__":
    try:
        # First let the user select a Jellyfin user
        jellyfin_manager.select_user()
        
        # Then show the main menu
        show_main_menu()
    except Exception as e:
        print(f"Warning: Could not show interactive menu: {e}")
