#!/usr/bin/env python3

import os
import sqlite3
import requests
from datetime import datetime
from simple_term_menu import TerminalMenu

class JellyfinManager:
    """Class to manage Jellyfin API interactions and database operations"""
    
    def __init__(self, db_file, server_url, api_key):
        """Initialize with database file, server URL and API key"""
        self.db_file = db_file
        self.server_url = server_url
        self.api_key = api_key
        self.headers = {
            "X-MediaBrowser-Token": self.api_key,
            "Content-Type": "application/json"
        }
        
    def validate_api_key(self):
        """Check if API key is valid"""
        if not self.api_key:
            print("\n---------Jellyfin API Key Required---------")
            print("You need to configure a Jellyfin API key in playlist_config.ini")
            print("1. Log in to your Jellyfin admin dashboard")
            print("2. Go to Admin > API Keys")
            print("3. Create a new API key")
            print("4. Add the key to your playlist_config.ini file under [Jellyfin] section")
            input("Press Enter to Continue")
            return False
        return True
        
    def select_user(self):
        """Connect to Jellyfin API and list all users with option to view their music libraries."""
        if not self.validate_api_key():
            return False
        
        print("\n---------Jellyfin Users---------")
        print(f"Connecting to Jellyfin server at: {self.server_url}")
        
        try:
            # Make the API request to get users
            endpoint = f"{self.server_url}/Users"
            response = requests.get(endpoint, headers=self.headers)
            
            # Check if request was successful
            if response.status_code == 200:
                users = response.json()
                
                if not users:
                    print("No users found.")
                    input("\nPress Enter to Continue")
                    return False
                else:
                    # Create a menu of users
                    user_menu = []
                    for user in users:
                        user_id = user.get('Id', 'N/A')
                        name = user.get('Name', 'N/A')
                        last_login = user.get('LastLoginDate', 'Never')
                        
                        # Format the last login date if it exists
                        if last_login != 'Never':
                            try:
                                # Parse ISO 8601 date format
                                last_login_date = datetime.fromisoformat(last_login.replace('Z', '+00:00'))
                                last_login = last_login_date.strftime('%Y-%m-%d %H:%M')
                            except:
                                pass
                        
                        user_menu.append(f"{name} (Last login: {last_login})")
                    
                    
                    # Show the menu
                    terminal_menu = TerminalMenu(user_menu, title="Select a user to view their music libraries:")
                    menu_index = terminal_menu.show()
                    
                    if menu_index is None:
                        return True
                    
                    # User selected a user, show their views
                    selected_user = users[menu_index]
                    selected_user_id = selected_user.get('Id')
                    selected_user_name = selected_user.get('Name')
                    
                    # Store for later use
                    self.selected_user_id = selected_user_id
                    self.selected_user_name = selected_user_name
                    
                    # Get this user's views
                    return True
            else:
                print(f"Error connecting to Jellyfin API. Status code: {response.status_code}")
                print(f"Response: {response.text}")
        
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Jellyfin server: {e}")
        except ValueError as e:
            print(f"Error parsing response: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        
        input("\nPress Enter to Continue")
        return True
        
    def list_user_libraries(self, user_id, user_name):
        """List music libraries for the given user"""
        # Get this user's views
        view_endpoint = f"{self.server_url}/Users/{user_id}/Views"
        view_response = requests.get(view_endpoint, headers=self.headers)
        
        if view_response.status_code == 200:
            views = view_response.json().get("Items", [])
            
            # Filter to only music libraries
            music_views = []
            for view in views:
                collection_type = view.get("CollectionType", "")
                if collection_type.lower() == "music":
                    music_views.append(view)
            
            if not music_views:
                print(f"No music libraries found for user {user_name}.")
                input("\nPress Enter to Continue")
                return True
            
            # Create menu of music libraries
            library_menu = []
            for view in music_views:
                view_name = view.get("Name", "Unnamed")
                item_count = view.get("ChildCount", 0)
                library_menu.append(f"{view_name} ({item_count} items)")
            
            library_menu.append("Back to User Selection")
            
            # Show the menu
            library_menu_title = f"Music libraries for user {user_name}:"
            library_terminal_menu = TerminalMenu(library_menu, title=library_menu_title)
            library_index = library_terminal_menu.show()
            
            if library_index is None or library_index == len(music_views):
                return self.list_users()  # Back to user selection
            
            # User selected a library, show details
            selected_library = music_views[library_index]
            library_id = selected_library.get("Id")
            library_name = selected_library.get("Name")
            
            # Get stats for this library
            stats_endpoint = f"{self.server_url}/Items/Counts?UserId={user_id}&ParentId={library_id}"
            stats_response = requests.get(stats_endpoint, headers=self.headers)
            
            print(f"\nLibrary: {library_name}")
            
            if stats_response.status_code == 200:
                stats = stats_response.json()
                album_count = stats.get("AlbumCount", 0)
                artist_count = stats.get("ArtistCount", 0)
                song_count = stats.get("SongCount", 0)
                
                print(f"Statistics:")
                print(f"  Albums: {album_count}")
                print(f"  Artists: {artist_count}")
                print(f"  Songs: {song_count}")
            
            # Give options for this library
            options = [
                "Scan this library for music albums",
                "Browse recently added albums",
                "Back to library selection"
            ]
            
            options_menu = TerminalMenu(options, title=f"Options for {library_name}:")
            option_index = options_menu.show()
            
            if option_index == 0:  # Scan library
                self.scan_library(library_id, user_id, library_name)
            elif option_index == 1:  # Browse recent albums
                self.browse_recent_albums(library_id, user_id, library_name)
            
            # Back to library selection
            input("\nPress Enter to Continue")
            return self.list_user_libraries(user_id, user_name)
            
        else:
            print(f"Error getting user views: {view_response.status_code}")
            input("\nPress Enter to Continue")
            
        return True
        
    def scan_library(self, library_id, user_id, library_name):
        """Scan a specific library for music albums"""
        print(f"\nScanning library {library_name}...")
        
        # Clear database first?
        clear_db = input("Clear existing database items first? (y/n): ")
        if clear_db.lower() == 'y':
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM jellyfin_items')
            conn.commit()
            conn.close()
            print("Database cleared.")
        
        # Get albums from this library
        scan_params = {
            "ParentId": library_id,
            "UserId": user_id,
            "Recursive": "true",
            "Fields": "Path,Name,Type,ParentId",
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "IncludeItemTypes": "MusicAlbum",
            "Limit": 2000
        }
        
        album_endpoint = f"{self.server_url}/Items"
        album_response = requests.get(album_endpoint, headers=self.headers, params=scan_params)
        
        if album_response.status_code == 200:
            all_items = album_response.json().get("Items", [])
            # Filter out items of type "Audio"
            albums = [item for item in all_items if item.get("Type", "") == "MusicAlbum"]
            print(f"Found {len(albums)} albums in library {library_name}.")
            
            # Store albums in database
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            albums_stored = 0
            tracks_stored = 0
            
            for album in albums:
                album_id = album.get('Id', 'N/A')
                album_name = album.get('Name', 'Unnamed')
                album_artist = album.get('AlbumArtist', 'Unnamed')
                album_path = album.get('Path', '')
                
                # Store album
                try:
                    # Check if we need to alter the table to add albumartist column
                    cursor.execute("PRAGMA table_info(jellyfin_items)")
                    columns = [column[1] for column in cursor.fetchall()]
                    
                    if 'albumartist' not in columns:
                        cursor.execute('ALTER TABLE jellyfin_items ADD COLUMN albumartist TEXT')
                        conn.commit()
                        print("Added albumartist column to jellyfin_items table")
                    
                    # Now store with albumartist
                    cursor.execute('''
                        INSERT OR REPLACE INTO jellyfin_items 
                        (item_id, title, path, type, parent_id, albumartist) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (album_id, album_name, album_path, "MusicAlbum", library_id, album_artist))
                    conn.commit()
                    albums_stored += 1
                    
                except Exception as e:
                    print(f"Error storing album {album_name}: {e}")
            
            print(f"\nScan complete!")
            print(f"Albums stored: {albums_stored}")
            
            conn.close()
        else:
            print(f"Error fetching albums: {album_response.status_code}")
            
    def browse_recent_albums(self, library_id, user_id, library_name):
        """Browse recently added albums in a library"""
        # Get recently added albums
        recent_params = {
            "ParentId": library_id,
            "UserId": user_id,
            "Recursive": "true",
            "Fields": "Path,Name,DateCreated",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "IncludeItemTypes": "MusicAlbum",
            "Limit": 20
        }
        
        recent_endpoint = f"{self.server_url}/Items"
        recent_response = requests.get(recent_endpoint, headers=self.headers, params=recent_params)
        
        if recent_response.status_code == 200:
            recent_albums = recent_response.json().get("Items", [])
            
            if not recent_albums:
                print("No albums found.")
            else:
                print(f"\nRecently added albums in {library_name}:")
                
                for album in recent_albums:
                    album_name = album.get("Name", "Unnamed")
                    album_path = album.get("Path", "No path")
                    date_created = album.get("DateCreated", "Unknown")
                    
                    # Format date
                    if date_created != "Unknown":
                        try:
                            created_date = datetime.fromisoformat(date_created.replace('Z', '+00:00'))
                            date_str = created_date.strftime('%Y-%m-%d')
                        except:
                            date_str = date_created
                    else:
                        date_str = "Unknown"
                    
                    print(f"{album_name} (Added: {date_str})")
                    if album_path:
                        print(f"  Path: {album_path}")
                        
                        # Check if path exists and is in database
                        if os.path.exists(album_path):
                            # Check if in database
                            conn = sqlite3.connect(self.db_file)
                            cursor = conn.cursor()
                            
                            cursor.execute('SELECT category_id FROM folders WHERE path = ?', (album_path,))
                            folder = cursor.fetchone()
                            
                            if folder:
                                cursor.execute('SELECT name FROM categories WHERE id = ?', (folder[0],))
                                category = cursor.fetchone()
                                print(f"  In category: {category[0]}")
                            else:
                                print("  Not in any playlist category")
                            
                            conn.close()
                    print()
        else:
            print(f"Error fetching recent albums: {recent_response.status_code}")
            
    def scan_items(self):
        """Scan all music albums in Jellyfin and store them in the database."""
        if not self.validate_api_key():
            return False
        
        print("\n---------Scanning Jellyfin Music Albums---------")
        print(f"Connecting to Jellyfin server at: {self.server_url}")
        
        # Set up progress indicators
        total_items_found = 0
        total_items_stored = 0
        
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # First, clear existing items to ensure fresh data (optional)
            clear_existing = input("Clear existing item data before scanning? (y/n): ")
            if clear_existing.lower() == 'y':
                cursor.execute('DELETE FROM jellyfin_items')
                print("Cleared existing item data.")
            
            # Get all music albums with recursive search
            params = {
                "Recursive": "false",
                "Fields": "Path,Name,Type,ParentId",
                "SortBy": "SortName",
                "SortOrder": "Ascending",
                "IncludeItemTypes": "MusicAlbum",
                "Limit": 2000
            }
            
            endpoint = f"{self.server_url}/Items"
            response = requests.get(endpoint, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Error connecting to Jellyfin API. Status code: {response.status_code}")
                print(f"Response: {response.text}")
                conn.close()
                return False
            
            root_items = response.json().get("Items", [])
            print(f"Found {len(root_items)} music albums.")
            
            # Process each album and its tracks
            total_albums = len(root_items)
            total_tracks = 0
            
            print(f"Processing {total_albums} music albums...")
            
            # First, store all albums
            for album_index, album in enumerate(root_items):
                # Extract album details
                album_id = album.get('Id', 'N/A')
                album_name = album.get('Name', 'Unnamed')
                album_path = album.get('Path', '')
                album_type = album.get('Type', 'Unknown')
                parent_id = album.get('ParentId', '')
                
                # Store album in database
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO jellyfin_items 
                        (item_id, title, path, type, parent_id) 
                        VALUES (?, ?, ?, ?, ?)
                    ''', (album_id, album_name, album_path, album_type, parent_id))
                    
                    conn.commit()
                    total_items_stored += 1
                    total_items_found += 1
                    
                    # Print progress every 20 albums
                    if album_index > 0 and album_index % 20 == 0:
                        print(f"Processed {album_index} of {total_albums} albums...")
                    
                except sqlite3.Error as e:
                    print(f"Database error storing album {album_id}: {e}")
                    continue
                
                # Get the album's tracks
                child_params = {
                    "ParentId": album_id,
                    "Recursive": "false",
                    "Fields": "Path,Name,Type,ParentId",
                    "SortBy": "SortName",
                    "SortOrder": "Ascending",
                    "IncludeItemTypes": "Audio",
                    "Limit": 1000
                }
                
                try:
                    child_response = requests.get(endpoint, headers=self.headers, params=child_params)
                    
                    if child_response.status_code == 200:
                        tracks = child_response.json().get("Items", [])
                        album_track_count = len(tracks)
                        total_tracks += album_track_count
                        
                        # Store each track
                        for track in tracks:
                            track_id = track.get('Id', 'N/A')
                            track_name = track.get('Name', 'Unnamed')
                            track_path = track.get('Path', '')
                            track_type = track.get('Type', 'Unknown')
                            
                            try:
                                cursor.execute('''
                                    INSERT OR REPLACE INTO jellyfin_items 
                                    (item_id, title, path, type, parent_id) 
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (track_id, track_name, track_path, track_type, album_id))
                                
                                conn.commit()
                                total_items_stored += 1
                                total_items_found += 1
                            except sqlite3.Error as e:
                                print(f"Database error storing track {track_id}: {e}")
                        
                        if album_track_count > 0:
                            print(f"Album '{album_name}' has {album_track_count} tracks")
                except Exception as e:
                    print(f"Error fetching tracks for album {album_name}: {e}")
            
            print(f"\nScan complete!")
            print(f"Total albums: {total_albums}")
            print(f"Total tracks: {total_tracks}")
            print(f"Total items stored in database: {total_items_stored}")
            
            # Count item types
            cursor.execute('SELECT type, COUNT(*) FROM jellyfin_items GROUP BY type ORDER BY COUNT(*) DESC')
            type_counts = cursor.fetchall()
            
            print("\nItem types in database:")
            for item_type, count in type_counts:
                print(f"  {item_type}: {count} items")
            
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Jellyfin server: {e}")
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            conn.close()
        
        input("\nPress Enter to Continue")
        return True
    
    def search_path(self):
        """Search for a path in Jellyfin using the GetItems API and allow selecting from database paths."""
        if not self.validate_api_key():
            return False
        
        print("\n---------Search Jellyfin Paths---------")
        
        # Step 1: Choose search method
        search_options = [
            "Search by keyword",
            "Browse from database paths",
            "Back to Main Menu"
        ]
        search_menu = TerminalMenu(search_options, title="Select search method:")
        search_index = search_menu.show()
        
        if search_index == 0:  # Search by keyword
            return self.search_by_keyword()
        elif search_index == 1:  # Browse from database
            return self.select_path_from_database()
        else:  # Back or None
            return False
    
    def search_by_keyword(self):
        """Search for items in Jellyfin by keyword."""
        keyword = input("Enter search keyword: ")
        
        if not keyword:
            print("No keyword entered. Returning to main menu.")
            return False
        
        # Ask for path to limit search (optional)
        path_filter = input("Enter path to limit search (optional, press Enter to search all): ")
        
        print(f"\nSearching Jellyfin for: '{keyword}'")
        if path_filter:
            print(f"Limited to path: '{path_filter}'")
        
        try:
            # Make the API request to search
            params = {
                "SearchTerm": keyword,
                "IncludeItemTypes": "MusicAlbum,Folder,Audio",
                "Recursive": "true",
                "Limit": 50,
                "Fields": "Path,Type,Name"  # Specify fields to return
            }
            
            # Add path parameter if provided
            if path_filter:
                params["Path"] = path_filter
            
            endpoint = f"{self.server_url}/Items"
            response = requests.get(endpoint, headers=self.headers, params=params)
            
            # Check if request was successful
            if response.status_code == 200:
                result = response.json()
                items = result.get("Items", [])
                
                if not items:
                    print("No items found matching your search.")
                else:
                    print(f"Found {len(items)} items:")
                    
                    # Create a menu of search results
                    item_menu = []
                    for item in items:
                        item_type = item.get("Type", "Unknown")
                        item_name = item.get("Name", "Unnamed")
                        item_path = item.get("Path", "No path")
                        
                        # Truncate path for display if needed
                        if len(item_path) > 60:
                            display_path = item_path[:57] + "..."
                        else:
                            display_path = item_path
                        
                        item_menu.append(f"[{item_type}] {item_name} - {display_path}")
                    
                    item_menu.append("Back to Search")
                    
                    # Display menu and get user choice
                    terminal_menu = TerminalMenu(item_menu, title="Select an item:")
                    menu_index = terminal_menu.show()
                    
                    if menu_index is None or menu_index == len(items):
                        print("No item selected. Returning to search menu.")
                        return self.search_path()
                    
                    # Process the selected item
                    selected_item = items[menu_index]
                    self.process_selected_item(selected_item)
                    return True
            else:
                print(f"Error searching Jellyfin API. Status code: {response.status_code}")
                print(f"Response: {response.text}")
        
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Jellyfin server: {e}")
        except ValueError as e:
            print(f"Error parsing response: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        
        input("\nPress Enter to Continue")
        return False
    
    def select_path_from_database(self):
        """Select a path from the database to use with Jellyfin."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Get all paths from database
        cursor.execute('''
            SELECT f.path, c.name 
            FROM folders f
            JOIN categories c ON f.category_id = c.id
            ORDER BY c.name, f.path
        ''')
        
        folders = cursor.fetchall()
        conn.close()
        
        if not folders:
            print("No paths found in database. Please add paths first.")
            input("Press Enter to Continue")
            return False
        
        # Create a menu of folder paths grouped by category
        folder_menu = []
        current_category = None
        
        for path, category in folders:
            # Add category header if we've moved to a new category
            if category != current_category:
                if current_category is not None:
                    folder_menu.append("──────────────────────────────────────────")
                folder_menu.append(f"== {category} ==")
                current_category = category
            
            # Truncate path for display
            if len(path) > 60:
                display_path = path[:57] + "..."
            else:
                display_path = path
                
            folder_menu.append(f"{display_path}")
        
        folder_menu.append("──────────────────────────────────────────")
        folder_menu.append("Back to Search Menu")
        
        # Display menu and get user choice
        terminal_menu = TerminalMenu(folder_menu, title="Select a path from database:")
        menu_index = terminal_menu.show()
        
        if menu_index is None or menu_index == len(folder_menu) - 1:
            print("No path selected. Returning to search menu.")
            return self.search_path()
        
        # Skip category headers and separators when determining the selected folder
        selected_index = 0
        real_folders = []
        
        for i, item in enumerate(folder_menu):
            if i == menu_index:
                # Check if selected item is a header or separator
                if item.startswith("==") or item.startswith("──────"):
                    print("Please select a path, not a category header or separator.")
                    return self.select_path_from_database()
                
                selected_index = len(real_folders) - 1
                break
            elif not (item.startswith("==") or item.startswith("──────")):
                real_folders.append(item)
        
        # Get the actual path and category for the selection
        selected_path = folders[selected_index][0]
        selected_category = folders[selected_index][1]
        
        print(f"\nSelected path: {selected_path}")
        print(f"Category: {selected_category}")
        
        # Now use Jellyfin API to get items at this path
        try:
            # Encode the path for URL
            params = {
                "Path": selected_path,
                "Recursive": "true",
                "IncludeItemTypes": "Audio",
                "Limit": 100,
                "Fields": "Path,Type,Name,RunTimeTicks" # Specify fields to return
            }
            
            endpoint = f"{self.server_url}/Items"
            response = requests.get(endpoint, headers=self.headers, params=params)
            
            # Check if request was successful
            if response.status_code == 200:
                result = response.json()
                items = result.get("Items", [])
                
                if not items:
                    print(f"No items found at path: {selected_path}")
                else:
                    print(f"Found {len(items)} items at this path:")
                    
                    # Offer option to browse items or add path to database
                    options = ["Browse items", "Add path to playlist", "Back"]
                    options_menu = TerminalMenu(options, title="What would you like to do?")
                    option_index = options_menu.show()
                    
                    if option_index == 0:  # Browse items
                        print("\nID                                     | Name                          | Type")
                        print("-" * 80)
                        
                        for item in items[:10]:  # Show first 10 items
                            item_id = item.get('Id', 'N/A')
                            name = item.get('Name', 'N/A')
                            item_type = item.get('Type', 'N/A')
                            
                            print(f"{item_id} | {name[:30]:<30} | {item_type}")
                        
                        if len(items) > 10:
                            print(f"... and {len(items) - 10} more items")
                            
                        # Allow selecting an item to view details
                        if input("\nView a specific item? (y/n): ").lower() == 'y':
                            # Create menu of items
                            item_menu = []
                            for item in items:
                                name = item.get('Name', 'N/A')
                                item_type = item.get('Type', 'N/A')
                                item_menu.append(f"[{item_type}] {name}")
                            
                            item_menu.append("Back")
                            
                            item_selector = TerminalMenu(item_menu, title="Select an item to view:")
                            item_index = item_selector.show()
                            
                            if item_index is not None and item_index < len(items):
                                self.process_selected_item(items[item_index])
                    
                    elif option_index == 1:  # Add path to playlist
                        # Path is already in database (we selected it from there)
                        print(f"Path '{selected_path}' is already in the database under category '{selected_category}'.")
                        
                        # Offer to change category
                        if input("Would you like to change the category? (y/n): ").lower() == 'y':
                            conn = sqlite3.connect(self.db_file)
                            cursor = conn.cursor()
                            
                            # Get all categories
                            cursor.execute('SELECT id, name FROM categories ORDER BY name')
                            categories = cursor.fetchall()
                            
                            # Create menu of category options
                            category_menu = []
                            for id, name in categories:
                                category_menu.append(f"ID{id} {name}")
                                
                            # Display menu and get user choice
                            terminal_menu = TerminalMenu(category_menu, title="Select a new category for this path:")
                            category_index = terminal_menu.show()
                            
                            if category_index is not None:
                                # Get the selected category
                                selected_category_id = categories[category_index][0]
                                selected_category_name = categories[category_index][1]
                                
                                # Update in database
                                try:
                                    cursor.execute(
                                        'UPDATE folders SET category_id = ? WHERE path = ?',
                                        (selected_category_id, selected_path)
                                    )
                                    conn.commit()
                                    print(f"Path '{selected_path}' updated to category '{selected_category_name}'.")
                                except sqlite3.Error as e:
                                    print(f"Database error: {e}")
                            
                            conn.close()
            else:
                print(f"Error retrieving items from Jellyfin. Status code: {response.status_code}")
                print(f"Response: {response.text}")
        
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Jellyfin server: {e}")
        except ValueError as e:
            print(f"Error parsing response: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        
        input("\nPress Enter to Continue")
        return True
    
    def process_selected_item(self, item):
        """Process a selected item from Jellyfin search results."""
        item_id = item.get('Id', 'N/A')
        item_name = item.get('Name', 'Unnamed')
        item_path = item.get('Path', '')
        item_type = item.get('Type', 'Unknown')
        
        print(f"\nSelected Item: {item_name}")
        print(f"Type: {item_type}")
        print(f"Path: {item_path}")
        print(f"ID: {item_id}")
        
        # For folders and albums, fetch child items
        if item_type in ["Folder", "MusicAlbum"]:
            try:
                # Make the API request to get child items
                params = {
                    "ParentId": item_id,
                    "Recursive": "false",
                    "Fields": "Path,Name,Type,RunTimeTicks",
                    "SortBy": "Name",
                    "SortOrder": "Ascending"
                }
                
                endpoint = f"{self.server_url}/Items"
                response = requests.get(endpoint, headers=self.headers, params=params)
                
                # Check if request was successful
                if response.status_code == 200:
                    result = response.json()
                    children = result.get("Items", [])
                    
                    if not children:
                        print("No child items found.")
                    else:
                        print(f"\nFound {len(children)} child items:")
                        
                        # Offer option to view children or add path to database
                        options = ["View child items", "Add this path to database", "Back"]
                        options_menu = TerminalMenu(options, title="What would you like to do?")
                        option_index = options_menu.show()
                        
                        if option_index == 0:  # View child items
                            print("\nName                          | Type       | Duration")
                            print("-" * 70)
                            
                            for child in children[:10]:  # Show first 10 children
                                child_name = child.get('Name', 'N/A')
                                child_type = child.get('Type', 'N/A')
                                
                                # Format duration if available
                                duration = child.get('RunTimeTicks', 0)
                                if duration:
                                    # Convert ticks (100-nanosecond units) to seconds
                                    duration_seconds = duration / 10000000
                                    minutes = int(duration_seconds // 60)
                                    seconds = int(duration_seconds % 60)
                                    duration_str = f"{minutes}:{seconds:02d}"
                                else:
                                    duration_str = "N/A"
                                
                                print(f"{child_name[:30]:<30} | {child_type:<10} | {duration_str}")
                            
                            if len(children) > 10:
                                print(f"... and {len(children) - 10} more items")
                                
                            # Offer to view all items or select an item
                            view_all = input("\nView all items? (y/n): ")
                            if view_all.lower() == 'y':
                                print("\nAll items:")
                                print("\nName                          | Type       | Duration")
                                print("-" * 70)
                                
                                for child in children:
                                    child_name = child.get('Name', 'N/A')
                                    child_type = child.get('Type', 'N/A')
                                    
                                    # Format duration if available
                                    duration = child.get('RunTimeTicks', 0)
                                    if duration:
                                        # Convert ticks (100-nanosecond units) to seconds
                                        duration_seconds = duration / 10000000
                                        minutes = int(duration_seconds // 60)
                                        seconds = int(duration_seconds % 60)
                                        duration_str = f"{minutes}:{seconds:02d}"
                                    else:
                                        duration_str = "N/A"
                                    
                                    print(f"{child_name[:30]:<30} | {child_type:<10} | {duration_str}")
                            
                            # Offer to select a child item
                            select_child = input("\nSelect a child item? (y/n): ")
                            if select_child.lower() == 'y':
                                # Create menu of child items
                                child_menu = []
                                for child in children:
                                    child_name = child.get('Name', 'N/A')
                                    child_type = child.get('Type', 'N/A')
                                    child_menu.append(f"[{child_type}] {child_name}")
                                
                                child_menu.append("Back")
                                
                                child_selector = TerminalMenu(child_menu, title="Select a child item:")
                                child_index = child_selector.show()
                                
                                if child_index is not None and child_index < len(children):
                                    self.process_selected_item(children[child_index])
                        
                        elif option_index == 1:  # Add path to database
                            # Continue to path processing below
                            pass
                        else:
                            # Skip path processing
                            input("\nPress Enter to Continue")
                            return True
                else:
                    print(f"Error retrieving child items. Status code: {response.status_code}")
            
            except requests.exceptions.RequestException as e:
                print(f"Error connecting to Jellyfin server: {e}")
            except ValueError as e:
                print(f"Error parsing response: {e}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
        
        # If path exists, offer to add it to the database
        if item_path and os.path.exists(item_path):
            print("\nThis path exists on the filesystem.")
            
            # Check if path is already in the database
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT category_id FROM folders WHERE path = ?', (item_path,))
            existing = cursor.fetchone()
            
            if existing:
                # Get category name
                cursor.execute('SELECT name FROM categories WHERE id = ?', (existing[0],))
                category_name = cursor.fetchone()[0]
                print(f"This path is already in the database under category: {category_name}")
                
                # Offer to change category
                change_category = input("Would you like to change the category? (y/n): ")
                if change_category.lower() == 'y':
                    # Get all categories
                    cursor.execute('SELECT id, name FROM categories ORDER BY name')
                    categories = cursor.fetchall()
                    
                    if not categories:
                        print("No categories found. Please create categories first.")
                        conn.close()
                        return True
                    
                    # Create menu of category options
                    category_menu = []
                    for id, name in categories:
                        category_menu.append(f"ID{id} {name}")
                        
                    # Display menu and get user choice
                    terminal_menu = TerminalMenu(category_menu, title="Select a new category for this path:")
                    category_index = terminal_menu.show()
                    
                    if category_index is not None:
                        # Get the selected category
                        selected_category_id = categories[category_index][0]
                        selected_category_name = categories[category_index][1]
                        
                        # Update in database
                        try:
                            cursor.execute(
                                'UPDATE folders SET category_id = ? WHERE path = ?',
                                (selected_category_id, item_path)
                            )
                            conn.commit()
                            print(f"Path '{item_path}' updated to category '{selected_category_name}'.")
                        except sqlite3.Error as e:
                            print(f"Database error: {e}")
            else:
                # Offer to add to database
                add_to_db = input("Would you like to add this path to the database? (y/n): ")
                if add_to_db.lower() == 'y':
                    # Get all categories
                    cursor.execute('SELECT id, name FROM categories ORDER BY name')
                    categories = cursor.fetchall()
                    
                    if not categories:
                        print("No categories found. Please create categories first.")
                        conn.close()
                        return True
                    
                    # Create menu of category options
                    category_menu = []
                    for id, name in categories:
                        category_menu.append(f"ID{id} {name}")
                        
                    # Display menu and get user choice
                    terminal_menu = TerminalMenu(category_menu, title="Select a category for this path:")
                    category_index = terminal_menu.show()
                    
                    if category_index is not None:
                        # Get the selected category
                        selected_category_id = categories[category_index][0]
                        selected_category_name = categories[category_index][1]
                        
                        # Store in database
                        try:
                            # Add username if known
                            if hasattr(self, 'selected_user_name'):
                                cursor.execute(
                                    'INSERT OR REPLACE INTO folders (path, category_id, user_name) VALUES (?, ?, ?)',
                                    (item_path, selected_category_id, self.selected_user_name)
                                )
                            else:
                                cursor.execute(
                                    'INSERT OR REPLACE INTO folders (path, category_id) VALUES (?, ?)',
                                    (item_path, selected_category_id)
                                )
                            conn.commit()
                            print(f"Path '{item_path}' added to database under category '{selected_category_name}'.")
                        except sqlite3.Error as e:
                            print(f"Database error: {e}")
                    else:
                        print("No category selected. Path not added to database.")
            
            conn.close()
        else:
            print("This path does not exist on the filesystem or is empty.")
        
        input("\nPress Enter to Continue")
        return True
    
    def browse_database(self):
        """Browse Jellyfin items stored in the local database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Check if we have items in the database
        cursor.execute('SELECT COUNT(*) FROM jellyfin_items')
        item_count = cursor.fetchone()[0]
        
        if item_count == 0:
            print("\n---------No Jellyfin Items in Database---------")
            print("You need to scan Jellyfin items first.")
            print("Choose 'Scan Jellyfin Items' from the main menu.")
            input("Press Enter to Continue")
            conn.close()
            return False
        
        print(f"\n---------Browse Jellyfin Items ({item_count} items in database)---------")
        
        # Get some stats on item types
        cursor.execute('SELECT type, COUNT(*) FROM jellyfin_items GROUP BY type ORDER BY COUNT(*) DESC')
        type_counts = cursor.fetchall()
        
        print("Item types in database:")
        for item_type, count in type_counts:
            print(f"  {item_type}: {count} items")
        
        # Options for browsing
        browse_options = [
            "Browse by folder structure",
            "Search by title",
            "Filter by type",
            "Back to Main Menu"
        ]
        
        while True:
            browse_menu = TerminalMenu(browse_options, title="\nSelect a browse method:")
            browse_index = browse_menu.show()
            
            if browse_index == 0:  # Browse by folder structure
                self.browse_by_folder_structure(conn)
            elif browse_index == 1:  # Search by title
                self.search_by_title(conn)
            elif browse_index == 2:  # Filter by type
                self.filter_by_type(conn)
            else:  # Back to Main Menu or None
                break
        
        conn.close()
        return True
    
    def browse_by_folder_structure(self, conn):
        """Browse Jellyfin items by folder structure."""
        cursor = conn.cursor()
        
        # Check if albumartist column exists
        cursor.execute("PRAGMA table_info(jellyfin_items)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'albumartist' in columns:
            # Include albumartist in query
            query = '''
                SELECT item_id, title, type, path, albumartist
                FROM jellyfin_items 
                WHERE parent_id IS NULL OR parent_id = '' 
                ORDER BY title
            '''
        else:
            # Original query without albumartist
            query = '''
                SELECT item_id, title, type, path 
                FROM jellyfin_items 
                WHERE parent_id IS NULL OR parent_id = '' 
                ORDER BY title
            '''
        
        cursor.execute(query)
        
        items = cursor.fetchall()
        current_items = items
        current_path = []  # Stack to track navigation path
        
        while True:
            # Build the menu items
            item_menu = []
            for item in current_items:
                item_id = item[0]
                title = item[1]
                item_type = item[2]
                
                # Check if albumartist exists and is available in this item
                if 'albumartist' in columns and len(item) > 4 and item[4]:
                    albumartist = item[4]
                    item_menu.append(f"[{item_type}] {title} - {albumartist}")
                else:
                    item_menu.append(f"[{item_type}] {title}")
            
            # Add navigation options
            if current_path:  # If we're not at the root
                item_menu.append(".. (Go back)")
            item_menu.append("Back to Browse Menu")
            
            # Create a title showing the current path
            if current_path:
                path_titles = [p[1] for p in current_path]  # Get titles from the path stack
                title_str = " > ".join(path_titles)
                menu_title = f"Current location: {title_str}"
            else:
                menu_title = "Root items"
            
            # Show the menu
            terminal_menu = TerminalMenu(item_menu, title=menu_title)
            menu_index = terminal_menu.show()
            
            if menu_index is None:
                break
            
            # Check if user selected a special option
            if current_path and menu_index == len(current_items):  # Go back
                parent_id, _ = current_path.pop()  # Remove the current location
                
                if current_path:  # If we still have path items, go to the previous level
                    grandparent_id = current_path[-1][0]
                    cursor.execute('''
                        SELECT item_id, title, type, path 
                        FROM jellyfin_items 
                        WHERE parent_id = ? 
                        ORDER BY title
                    ''', (grandparent_id,))
                else:  # We're going back to the root
                    cursor.execute('''
                        SELECT item_id, title, type, path 
                        FROM jellyfin_items 
                        WHERE parent_id IS NULL OR parent_id = '' 
                        ORDER BY title
                    ''')
                
                current_items = cursor.fetchall()
                continue
            
            elif menu_index == len(current_items) + (1 if current_path else 0):  # Back to Browse Menu
                break
            
            # User selected an item
            selected_item = current_items[menu_index]
            selected_id = selected_item[0]
            selected_title = selected_item[1]
            selected_type = selected_item[2]
            selected_path = selected_item[3]
            selected_albumartist = selected_item[4] if 'albumartist' in columns and len(selected_item) > 4 else None
            
            # Check if this item has children
            cursor.execute('SELECT COUNT(*) FROM jellyfin_items WHERE parent_id = ?', (selected_id,))
            child_count = cursor.fetchone()[0]
            
            if child_count > 0:  # This is a folder or container with children
                # Add this item to the path stack
                current_path.append((selected_id, selected_title))
                
                # Get its children
                if 'albumartist' in columns:
                    cursor.execute('''
                        SELECT item_id, title, type, path, albumartist
                        FROM jellyfin_items 
                        WHERE parent_id = ? 
                        ORDER BY title
                    ''', (selected_id,))
                else:
                    cursor.execute('''
                        SELECT item_id, title, type, path 
                        FROM jellyfin_items 
                        WHERE parent_id = ? 
                        ORDER BY title
                    ''', (selected_id,))
                
                current_items = cursor.fetchall()
            else:  # This is a leaf item (like an audio file)
                # Display item details
                print(f"\nItem: {selected_title}")
                print(f"Type: {selected_type}")
                print(f"ID: {selected_id}")
                if selected_albumartist:
                    print(f"Album Artist: {selected_albumartist}")
                
                if selected_path:
                    print(f"Path: {selected_path}")
                    
                    # Check if this path exists on the filesystem
                    if os.path.exists(selected_path):
                        print("This path exists on the filesystem.")
                        
                        # Check if the path is already in our folders database
                        cursor.execute('SELECT category_id FROM folders WHERE path = ?', (os.path.dirname(selected_path),))
                        folder_category = cursor.fetchone()
                        
                        if folder_category:
                            cursor.execute('SELECT name FROM categories WHERE id = ?', (folder_category[0],))
                            category_name = cursor.fetchone()[0]
                            print(f"The folder containing this item is already in the database under category: {category_name}")
                        else:
                            # Offer to add the folder to the database
                            add_to_db = input("\nWould you like to add this item's folder to the database? (y/n): ")
                            if add_to_db.lower() == 'y':
                                folder_path = os.path.dirname(selected_path)
                                
                                # Get all categories
                                cursor.execute('SELECT id, name FROM categories ORDER BY name')
                                categories = cursor.fetchall()
                                
                                if not categories:
                                    print("No categories found. Please create categories first.")
                                    input("Press Enter to Continue")
                                    continue
                                
                                # Create menu of category options
                                category_menu = []
                                for id, name in categories:
                                    category_menu.append(f"ID{id} {name}")
                                    
                                # Display menu and get user choice
                                category_selector = TerminalMenu(category_menu, title="Select a category for this folder:")
                                category_index = category_selector.show()
                                
                                if category_index is not None:
                                    # Get the selected category
                                    selected_category_id = categories[category_index][0]
                                    selected_category_name = categories[category_index][1]
                                    
                                    # Store in database
                                    try:
                                        # Add username if known
                                        if hasattr(self, 'selected_user_name'):
                                            cursor.execute(
                                                'INSERT OR REPLACE INTO folders (path, category_id, user_name) VALUES (?, ?, ?)',
                                                (folder_path, selected_category_id, self.selected_user_name)
                                            )
                                        else:
                                            cursor.execute(
                                                'INSERT OR REPLACE INTO folders (path, category_id) VALUES (?, ?)',
                                                (folder_path, selected_category_id)
                                            )
                                        conn.commit()
                                        print(f"Folder '{folder_path}' added to database under category '{selected_category_name}'.")
                                    except sqlite3.Error as e:
                                        print(f"Database error: {e}")
                    
                input("\nPress Enter to Continue")
    
    def search_by_title(self, conn):
        """Search Jellyfin items by title."""
        cursor = conn.cursor()
        
        search_term = input("\nEnter search term (or press Enter to cancel): ")
        
        if not search_term:
            return
        
        # Check if albumartist column exists
        cursor.execute("PRAGMA table_info(jellyfin_items)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Search the database
        if 'albumartist' in columns:
            cursor.execute('''
                SELECT item_id, title, type, path, albumartist
                FROM jellyfin_items 
                WHERE title LIKE ? 
                ORDER BY title
                LIMIT 100
            ''', (f'%{search_term}%',))
        else:
            cursor.execute('''
                SELECT item_id, title, type, path 
                FROM jellyfin_items 
                WHERE title LIKE ? 
                ORDER BY title
                LIMIT 100
            ''', (f'%{search_term}%',))
        
        items = cursor.fetchall()
        
        if not items:
            print(f"No items found matching '{search_term}'.")
            input("Press Enter to Continue")
            return
        
        print(f"\nFound {len(items)} items matching '{search_term}':")
        
        # Create menu of search results
        item_menu = []
        for item in items:
            item_id = item[0]
            title = item[1]
            item_type = item[2]
            
            # Check if albumartist exists in this item
            if 'albumartist' in columns and len(item) > 4 and item[4]:
                albumartist = item[4]
                item_menu.append(f"[{item_type}] {title} - {albumartist}")
            else:
                item_menu.append(f"[{item_type}] {title}")
        
        item_menu.append("Back to Browse Menu")
        
        # Show the menu
        terminal_menu = TerminalMenu(item_menu, title=f"Search results for '{search_term}':")
        menu_index = terminal_menu.show()
        
        if menu_index is None or menu_index == len(items):
            return
        
        # Display selected item details
        selected_item = items[menu_index]
        print(f"\nItem: {selected_item[1]}")
        print(f"Type: {selected_item[2]}")
        print(f"ID: {selected_item[0]}")
        
        # Display album artist if available
        if 'albumartist' in columns and len(selected_item) > 4 and selected_item[4]:
            print(f"Album Artist: {selected_item[4]}")
        
        if selected_item[3]:  # If path exists
            print(f"Path: {selected_item[3]}")
            
            # Check if this path exists on the filesystem
            if os.path.exists(selected_item[3]):
                print("This path exists on the filesystem.")
                
                # Check if the path is already in our folders database
                cursor.execute('SELECT category_id FROM folders WHERE path = ?', (os.path.dirname(selected_item[3]),))
                folder_category = cursor.fetchone()
                
                if folder_category:
                    cursor.execute('SELECT name FROM categories WHERE id = ?', (folder_category[0],))
                    category_name = cursor.fetchone()[0]
                    print(f"The folder containing this item is already in the database under category: {category_name}")
                else:
                    # Offer to add the folder to the database
                    add_to_db = input("\nWould you like to add this item's folder to the database? (y/n): ")
                    if add_to_db.lower() == 'y':
                        folder_path = os.path.dirname(selected_item[3])
                        
                        # Get all categories
                        cursor.execute('SELECT id, name FROM categories ORDER BY name')
                        categories = cursor.fetchall()
                        
                        if not categories:
                            print("No categories found. Please create categories first.")
                            input("Press Enter to Continue")
                            return
                        
                        # Create menu of category options
                        category_menu = []
                        for id, name in categories:
                            category_menu.append(f"ID{id} {name}")
                            
                        # Display menu and get user choice
                        category_selector = TerminalMenu(category_menu, title="Select a category for this folder:")
                        category_index = category_selector.show()
                        
                        if category_index is not None:
                            # Get the selected category
                            selected_category_id = categories[category_index][0]
                            selected_category_name = categories[category_index][1]
                            
                            # Store in database
                            try:
                                # Add username if known
                                if hasattr(self, 'selected_user_name'):
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO folders (path, category_id, user_name) VALUES (?, ?, ?)',
                                        (folder_path, selected_category_id, self.selected_user_name)
                                    )
                                else:
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO folders (path, category_id) VALUES (?, ?)',
                                        (folder_path, selected_category_id)
                                    )
                                conn.commit()
                                print(f"Folder '{folder_path}' added to database under category '{selected_category_name}'.")
                            except sqlite3.Error as e:
                                print(f"Database error: {e}")
        
        input("\nPress Enter to Continue")
    
    def filter_by_type(self, conn):
        """Filter Jellyfin items by type."""
        cursor = conn.cursor()
        
        # Check if albumartist column exists
        cursor.execute("PRAGMA table_info(jellyfin_items)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Get all available types
        cursor.execute('SELECT DISTINCT type FROM jellyfin_items ORDER BY type')
        types = [t[0] for t in cursor.fetchall()]
        
        # Create menu of types
        type_menu = []
        for item_type in types:
            # Get count for this type
            cursor.execute('SELECT COUNT(*) FROM jellyfin_items WHERE type = ?', (item_type,))
            count = cursor.fetchone()[0]
            type_menu.append(f"{item_type} ({count} items)")
        
        type_menu.append("Back to Browse Menu")
        
        # Show the menu
        terminal_menu = TerminalMenu(type_menu, title="Select an item type to browse:")
        menu_index = terminal_menu.show()
        
        if menu_index is None or menu_index == len(types):
            return
        
        selected_type = types[menu_index]
        
        # Get items of the selected type
        if 'albumartist' in columns:
            cursor.execute('''
                SELECT item_id, title, path, albumartist
                FROM jellyfin_items 
                WHERE type = ? 
                ORDER BY title
                LIMIT 100
            ''', (selected_type,))
        else:
            cursor.execute('''
                SELECT item_id, title, path 
                FROM jellyfin_items 
                WHERE type = ? 
                ORDER BY title
                LIMIT 100
            ''', (selected_type,))
        
        items = cursor.fetchall()
        
        if not items:
            print(f"No items found of type '{selected_type}'.")
            input("Press Enter to Continue")
            return
        
        print(f"\nFound {len(items)} items of type '{selected_type}':")
        
        # Create menu of items
        item_menu = []
        for item in items:
            item_id = item[0]
            title = item[1]
            
            # Check if albumartist exists in this item
            if 'albumartist' in columns and len(item) > 3 and item[3]:
                albumartist = item[3]
                item_menu.append(f"{title} - {albumartist}")
            else:
                item_menu.append(f"{title}")
        
        item_menu.append("Back to Type Selection")
        
        # Show the menu
        terminal_menu = TerminalMenu(item_menu, title=f"Items of type '{selected_type}':")
        menu_index = terminal_menu.show()
        
        if menu_index is None or menu_index == len(items):
            return self.filter_by_type(conn)  # Go back to type selection
        
        # Display selected item details
        selected_item = items[menu_index]
        print(f"\nItem: {selected_item[1]}")
        print(f"Type: {selected_type}")
        print(f"ID: {selected_item[0]}")
        
        # Display album artist if available
        if 'albumartist' in columns and len(selected_item) > 3 and selected_item[3]:
            print(f"Album Artist: {selected_item[3]}")
        
        path_index = 2
        if 'albumartist' in columns and len(selected_item) > 3:
            path_index = 2  # Path is still at index 2 for the extended query
        
        if selected_item[path_index]:  # If path exists
            print(f"Path: {selected_item[path_index]}")
            
            # Check if this path exists on the filesystem
            if os.path.exists(selected_item[path_index]):
                print("This path exists on the filesystem.")
                
                # Check if the path is already in our folders database
                cursor.execute('SELECT category_id FROM folders WHERE path = ?', (os.path.dirname(selected_item[path_index]),))
                folder_category = cursor.fetchone()
                
                if folder_category:
                    cursor.execute('SELECT name FROM categories WHERE id = ?', (folder_category[0],))
                    category_name = cursor.fetchone()[0]
                    print(f"The folder containing this item is already in the database under category: {category_name}")
                else:
                    # Offer to add the folder to the database
                    add_to_db = input("\nWould you like to add this item's folder to the database? (y/n): ")
                    if add_to_db.lower() == 'y':
                        folder_path = os.path.dirname(selected_item[path_index])
                        
                        # Get all categories
                        cursor.execute('SELECT id, name FROM categories ORDER BY name')
                        categories = cursor.fetchall()
                        
                        if not categories:
                            print("No categories found. Please create categories first.")
                            input("Press Enter to Continue")
                            return
                        
                        # Create menu of category options
                        category_menu = []
                        for id, name in categories:
                            category_menu.append(f"ID{id} {name}")
                            
                        # Display menu and get user choice
                        category_selector = TerminalMenu(category_menu, title="Select a category for this folder:")
                        category_index = category_selector.show()
                        
                        if category_index is not None:
                            # Get the selected category
                            selected_category_id = categories[category_index][0]
                            selected_category_name = categories[category_index][1]
                            
                            # Store in database
                            try:
                                # Add username if known
                                if hasattr(self, 'selected_user_name'):
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO folders (path, category_id, user_name) VALUES (?, ?, ?)',
                                        (folder_path, selected_category_id, self.selected_user_name)
                                    )
                                else:
                                    cursor.execute(
                                        'INSERT OR REPLACE INTO folders (path, category_id) VALUES (?, ?)',
                                        (folder_path, selected_category_id)
                                    )
                                conn.commit()
                                print(f"Folder '{folder_path}' added to database under category '{selected_category_name}'.")
                            except sqlite3.Error as e:
                                print(f"Database error: {e}")
        
        input("\nPress Enter to Continue")
