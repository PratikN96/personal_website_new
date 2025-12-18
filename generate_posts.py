# generate_posts.py
import os
import markdown
import json
from datetime import datetime

# --- Configuration ---
CONTENT_DIR = 'content'
OUTPUT_DIR = 'output'
POST_TEMPLATE_PATH = 'templates/post_template.html'
METADATA_FILE = 'output/metadata.json' 

# Define multiple date formats the script should try for INPUT
DATE_FORMATS_TO_TRY = [
    '%Y-%m-%d',         # 2025-04-05 (Standard sort format)
    '%d-%m-%Y',         # 05-04-2025 (Your preferred input format)
    '%Y-%m-%d %H:%M:%S %z', # 2025-04-05 01:21:23 +0530 (The verbose format)
] 
# Define the date format for internal sorting 
SORTABLE_DATE_FORMAT = '%Y-%m-%d'

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load the post HTML template
with open(POST_TEMPLATE_PATH, 'r') as f:
    post_template = f.read()

all_post_metadata = []
md = markdown.Markdown(extensions=['meta'])

print(f"--- Starting post generation from /{CONTENT_DIR} ---")

for filename in os.listdir(CONTENT_DIR):
    if filename.endswith('.md'):
        input_path = os.path.join(CONTENT_DIR, filename)
        
        with open(input_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()

        html_content = md.convert(markdown_text)
        
        # Metadata keys are often normalized to lowercase by the parser
        metadata = {k: v[0] for k, v in md.Meta.items()} 

        # --- Date Handling Logic ---
        # 1. Try lowercase 'date' key (most reliable with markdown parser)
        raw_date = metadata.get('date') 
        
        # 2. As a fallback, try case-sensitive 'Date' key
        if not raw_date:
            raw_date = metadata.get('Date')
            
        sortable_date = '1970-01-01' 
        display_date = 'Unknown Date'
        
        if raw_date:
            raw_date = raw_date.strip() # Clean whitespace
            display_date = raw_date # Keep the original text for display
            
            for fmt in DATE_FORMATS_TO_TRY:
                try:
                    date_obj = datetime.strptime(raw_date, fmt)
                    sortable_date = date_obj.strftime(SORTABLE_DATE_FORMAT) 
                    break 
                except ValueError:
                    continue 
            
            if sortable_date == '1970-01-01':
                 print(f"!!! CRITICAL WARNING: Failed to parse date '{raw_date}' in {filename}. Sorting will be incorrect.")

        post_title = metadata.get('title', 'Untitled Post')
        url_slug = filename.replace('.md', '.html')
        
        # 3. Create the final post HTML
        final_html = post_template.replace('{{ POST_TITLE }}', post_title)
        final_html = final_html.replace('{{ POST_DATE }}', display_date) 
        final_html = final_html.replace('{{ POST_CONTENT }}', html_content)

        # 4. Write the output file
        output_path = os.path.join(OUTPUT_DIR, url_slug)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
            
        # 5. Store metadata
        all_post_metadata.append({
            'title': post_title,
            'date': sortable_date, # Used for sorting in generate_index.py
            'display_date': display_date, # Used for displaying in generate_index.py
            'slug': url_slug
        })
        
        print(f"Generated post: {output_path} (Display Date: {display_date})")


# Save all metadata to a JSON file
with open(METADATA_FILE, 'w') as f:
    json.dump(all_post_metadata, f, indent=4)
    
print("--- Post generation complete. Metadata saved. ---")