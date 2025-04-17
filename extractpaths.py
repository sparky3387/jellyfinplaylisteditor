#!/usr/bin/python3
import xml.etree.ElementTree as ET
import sys
import os

def find_playlist_paths(xml_filepath):
    """
    Parses an XML file and prints the text content of elements matching
    the path: Item/PlaylistItems/PlaylistItem/Path.

    Args:
        xml_filepath (str): The path to the XML file.
    """

#    print(f"--- Parsing file: {xml_filepath} ---")
    found_paths = []
    try:
        # Parse the XML file
        tree = ET.parse(xml_filepath)
        root = tree.getroot()

        # Find all 'Item' elements directly under the root
        # Use findall with a relative XPath-like query
        # './' ensures we search from the current node (root)
        # Adjust the path if 'Item' is not directly under the root,
        # e.g., use './/Item/...' to search anywhere below the root.

        # Search for the specific nested structure
        # Note: This assumes 'Item' is a direct child of the root.
        # If 'Item' can be nested deeper, use './/Item/...' instead of './Item/...'
        playlist_path_elements = root.findall('.//PlaylistItem/Path')

        # --- Alternatively, if 'Item' might not be a direct child of root ---
        # playlist_path_elements = root.findall('.//Item/PlaylistItems/PlaylistItem/Path')
        # print("Using './/Item/...' search (finds 'Item' at any level)") # Uncomment if using this

        for path_element in playlist_path_elements:
            if path_element.text:
                # Strip leading/trailing whitespace from the path text
                found_paths.append(path_element.text.strip())
            else:
                # Handle cases where the <Path> tag exists but is empty
                found_paths.append("[Empty Path Tag]")

        if found_paths:
            #print("Found Paths:")
            for path in found_paths:
                print(path)
        #else:
            #print("No paths found matching the structure 'Item/PlaylistItems/PlaylistItem/Path'")

    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

#    print("-" * (len(f"--- Parsing file: {xml_filepath} ---"))) # Print separator matching length


# --- Example Usage ---
if __name__ == "__main__":
    # Check if a filename was provided as a command-line argument
    if len(sys.argv) > 1:
        file_to_parse = sys.argv[1]
        find_playlist_paths(file_to_parse)
    else:
        # --- Create a dummy XML file for demonstration if no argument is given ---
        #print("No file specified. Creating a dummy 'example_playlist.xml' for demonstration.")
        example_xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<PlaylistRoot>
  <Metadata>
    <Version>1.0</Version>
  </Metadata>
  <Item>
    <Name>My Awesome Music</Name>
    <PlaylistItems>
      <PlaylistItem>
        <TrackID>1</TrackID>
        <Path>/music/rock/song1.mp3</Path>
      </PlaylistItem>
      <PlaylistItem>
        <TrackID>2</TrackID>
        <Path>C:\\Users\\Me\\Music\\Classical\\piece2.wav</Path>
      </PlaylistItem>
      <PlaylistItem>
        <TrackID>3</TrackID>
        <!-- Path might be empty -->
        <Path></Path>
      </PlaylistItem>
    </PlaylistItems>
  </Item>
  <Item>
    <Name>Podcast Episodes</Name>
    <PlaylistItems>
      <PlaylistItem>
        <TrackID>101</TrackID>
        <Path>/podcasts/tech/episode_final.ogg</Path>
      </PlaylistItem>
    </PlaylistItems>
  </Item>
  <OtherData>
      <!-- This path should NOT be printed as it's not under Item/PlaylistItems -->
      <Path>/some/other/ignored_path.txt</Path>
  </OtherData>
  <NestedItem>
     <Item> <!-- This Item is nested, it will ONLY be found if using .//Item/... search -->
        <Name>Deeply Nested</Name>
        <PlaylistItems>
            <PlaylistItem>
                <Path>/music/deep/nested/track.flac</Path>
            </PlaylistItem>
        </PlaylistItems>
     </Item>
  </NestedItem>
</PlaylistRoot>
        """
        dummy_filename = "example_playlist.xml"
        try:
            with open(dummy_filename, "w", encoding="utf-8") as f:
                f.write(example_xml_content)
            #print(f"Created '{dummy_filename}'.\n")
            find_playlist_paths(dummy_filename)
            #print("\nTo parse your own file, run:")
            #print(f"python {os.path.basename(__file__)} your_file.xml")
        except IOError as e:
            print(f"Error creating dummy file: {e}")

        # --- End of Dummy File Creation ---
