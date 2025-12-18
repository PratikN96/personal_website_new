# generate_index.py
import os
import json
from datetime import datetime

# --- Configuration ---
OUTPUT_DIR = 'output'
LIST_TEMPLATE_PATH = 'templates/list_template.html'
HOME_TEMPLATE_PATH = 'templates/home_template.html'
METADATA_FILE = 'output/metadata.json'
# The format saved in the metadata JSON is YYYY-MM-DD
SORTING_DATE_FORMAT = '%Y-%m-%d' 

# --- Utility Function ---
def create_list_item(title, date, slug):
    """Creates a simple HTML list item for the blog list."""
    # Date is used directly for display
    return f"""
        <li>
            <a href="{slug}">
                <span class="blog-date">{date}</span>
                <span class="blog-title">{title}</span>
            </a>
        </li>
    """

# --- Main Logic ---
print("--- Starting index/list generation ---")

# 1. Load post metadata
with open(METADATA_FILE, 'r') as f:
    all_post_metadata = json.load(f)

# 2. Sort posts by date (newest first)
def sort_key(post):
    try:
        # Use the YYYY-MM-DD format for reliable sorting
        # This will fail gracefully if the date is 'Unknown Date'
        return datetime.strptime(post['date'], SORTING_DATE_FORMAT)
    except ValueError:
        # Pushes posts with 'Unknown Date' or bad format to the end of the list
        return datetime.min 

sorted_posts = sorted(all_post_metadata, key=sort_key, reverse=True)

# 3. Generate the list of blog post HTML links
post_list_items = ""
for post in sorted_posts:
    post_list_items += create_list_item(post['title'], post['date'], post['slug'])

# 4. Generate the Blog List Page (blog.html)
with open(LIST_TEMPLATE_PATH, 'r') as f:
    list_template = f.read()

list_html = list_template.replace('{{ POST_LIST }}', post_list_items)
list_output_path = os.path.join(OUTPUT_DIR, 'blog.html')
with open(list_output_path, 'w', encoding='utf-8') as f:
    f.write(list_html)
    
print(f"Generated blog list page: {list_output_path}")

# 5. Generate the Homepage (index.html)
with open(HOME_TEMPLATE_PATH, 'r') as f:
    home_template = f.read()
    
home_output_path = os.path.join(OUTPUT_DIR, 'index.html')
with open(home_output_path, 'w', encoding='utf-8') as f:
    f.write(home_template)

print(f"Generated homepage: {home_output_path}")
print("--- Index/List generation complete ---")